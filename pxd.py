#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import collections
import datetime
import enum
import gzip
from xml.sax.saxutils import unescape

try:
    from dateutil.parser import isoparse
except ImportError:
    isoparse = None


VERSION = 1.0
UTF8 = 'utf-8'


PxdData = collections.namedtuple('PxdData', ('data', 'custom'))


def read(filename_or_filelike, *, warn_is_error=False, _debug=False):
    '''
    Returns a PxdData whose Data is a tuple or dict or list using Python
    type equivalents to pxd types by parsing the filename_or_filelike and
    whose Custom is the short user string (if any).
    '''
    data = None
    tokens, custom = _tokenize(filename_or_filelike,
                               warn_is_error=warn_is_error, _debug=_debug)
    data = _parse(tokens, warn_is_error=warn_is_error, _debug=_debug)
    return PxdData(data, custom)


def _tokenize(filename_or_filelike, *, warn_is_error=False, _debug=False):
    text = _read_text(filename_or_filelike)
    lexer = _Lexer(warn_is_error=warn_is_error, _debug=_debug)
    tokens = lexer.tokenize(text)
    return tokens, lexer.custom


def _read_text(filename_or_filelike):
    if not isinstance(filename_or_filelike, str):
        return filename_or_filelike.read()
    try:
        with gzip.open(filename_or_filelike, 'rt', encoding=UTF8) as file:
            return file.read()
    except gzip.BadGzipFile:
        with open(filename_or_filelike, 'rt', encoding=UTF8) as file:
            return file.read()


class _Lexer:

    def __init__(self, *, warn_is_error=False, _debug=False):
        self.warn_is_error = warn_is_error
        self._debug = _debug


    def clear(self):
        self.text_token_type = _TokenKind.STR
        self.pos = 0 # current
        self.custom = None
        self.tokens = []


    def tokenize(self, text):
        self.clear()
        self.text = text
        self.scan_header()
        while not self.at_end():
            self.scan_next()
        self.add_token(_TokenKind.EOF)
        return self.tokens


    def scan_header(self):
        i = self.text.find('\n')
        if i == -1:
            self.error('missing pxd file header or empty file')
        self.pos = i
        parts = self.text[:i].split(None, 2)
        if len(parts) < 2:
            self.error('invalid pxd file header')
        if parts[0] != 'pxd':
            self.error('not a pxd file')
        try:
            version = float(parts[1])
            if version > VERSION:
                self.warn(f'version ({version}) > current ({VERSION})')
        except ValueError:
            self.warn('failed to read pxd file version number')
        if len(parts) > 2:
            self.custom = parts[2]


    def warn(self, message):
        if self.warn_is_error:
            self.error(message)
        lino = self.text.count('\n', 0, self.pos) + 1
        print(f'warning:{lino}: {message}')


    def error(self, message):
        lino = self.text.count('\n', 0, self.pos) + 1
        raise Error(f'{lino}: {message}')


    def at_end(self):
        return self.pos >= len(self.text)


    def scan_next(self):
        c = self.getch()
        if c.isspace():
            pass
        elif c == '[':
            if self.peek() == '=':
                if (self.tokens and self.tokens[-1].kind is
                        _TokenKind.LIST_BEGIN):
                    self.pos += 1
                    self.add_token(_TokenKind.TABLENAMES_BEGIN)
                    self.text_token_type = _TokenKind.TABLENAME
                else:
                    self.error('fieldnames may only occur as the first '
                               'item in a list of lists')
            else:
                self.add_token(_TokenKind.LIST_BEGIN)
        elif c == '=' and self.peek() == ']':
            self.pos += 1
            self.add_token(_TokenKind.TABLENAMES_END)
            self.text_token_type = _TokenKind.STR
        elif c == ']':
            self.add_token(_TokenKind.LIST_END)
        elif c == '{':
            self.add_token(_TokenKind.DICT_BEGIN)
        elif c == '}':
            self.add_token(_TokenKind.DICT_END)
        elif c == '<':
            self.read_string_or_name()
        elif c == '(':
            self.read_bytes()
        elif c == '-' and self.peek().isdecimal():
            c = self.getch() # skip the - and get the first digit
            self.read_negative_number(c)
        elif c.isdecimal():
            self.read_positive_number_or_date(c)
        elif c.isalpha():
            self.read_const()
        else:
            self.error(f'invalid character encountered: {c!r}')


    def read_string_or_name(self):
        value = self.match_to('>', error_text='unterminated string or name')
        self.add_token(self.text_token_type, unescape(value))
        if self.text_token_type is _TokenKind.TABLENAME:
            self.text_token_type = _TokenKind.FIELDNAME


    def read_bytes(self):
        value = self.match_to(')', error_text='unterminated bytes')
        self.add_token(_TokenKind.BYTES, bytes.fromhex(value))


    def read_negative_number(self, c):
        is_real = False
        start = self.pos - 1
        while not self.at_end() and (c in '.eE' or c.isdecimal()):
            if c in '.eE':
                is_real = True
            c = self.text[self.pos]
            self.pos += 1
        convert = float if is_real else int
        text = self.text[start:self.pos]
        try:
            value = convert(text)
            self.add_token(_TokenKind.REAL if is_real else _TokenKind.INT,
                           -value)
        except ValueError as err:
            self.error(f'invalid number: {text}: {err}')


    def read_positive_number_or_date(self, c):
        is_real = is_datetime = False
        hyphens = 0
        start = self.pos - 1
        while not self.at_end() and (c in '-+.:eETZ' or c.isdecimal()):
            if c in '.eE':
                is_real = True
            elif c == '-':
                hyphens += 1
            elif c in ':TZ':
                is_datetime = True
            c = self.text[self.pos]
            self.pos += 1
        self.pos -= 1 # wind back to terminating non-numeric non-date char
        text = self.text[start:self.pos]
        if is_datetime:
            if isoparse is None:
                convert = datetime.datetime.fromisoformat
                if text.endswith('Z'):
                    text = text[:-1] # Py std lib can't handle UTC 'Z'
            else:
                convert = isoparse
            convert = (datetime.datetime.fromisoformat if isoparse is None
                       else isoparse)
            token = _TokenKind.DATETIME
        elif hyphens == 2:
            convert = (datetime.date.fromisoformat if isoparse is None
                       else isoparse)
            token = _TokenKind.DATE
        elif is_real:
            convert = float
            token = _TokenKind.REAL
        else:
            convert = int
            token = _TokenKind.INT
        try:
            value = convert(text)
            if token is _TokenKind.DATE and isoparse is not None:
                value = value.date()
            self.add_token(token, value)
        except ValueError as err:
            self.error(f'invalid number or date/time: {text}: {err}')


    def read_const(self):
        match = self.match_any_of('no', 'yes', 'null', 'true', 'false')
        if match == 'null':
            self.add_token(_TokenKind.NULL)
        elif match in {'no', 'false'}:
            self.add_token(_TokenKind.BOOL, False)
        elif match in {'yes', 'true'}:
            self.add_token(_TokenKind.BOOL, True)
        else:
            i = self.text.find('\n', self.pos)
            text = self.text[self.pos - 1:i if i > -1 else self.pos + 8]
            self.error(f'expected const got: {text!r}')


    def peek(self):
        return '\0' if self.at_end() else self.text[self.pos]


    def getch(self): # advance
        c = self.text[self.pos]
        self.pos += 1
        return c


    def match_to(self, c, *, error_text):
        if not self.at_end():
            i = self.text.find(c, self.pos)
            if i > -1:
                text = self.text[self.pos:i]
                self.pos = i + 1 # skip past target c
                return text
        self.error(error_text)


    def match_any_of(self, *targets):
        if self.at_end():
            return None
        start = self.pos - 1
        for target in targets:
            if self.text.startswith(target, start):
                self.pos += len(target) # skip past target
                return target


    def add_token(self, kind, value=None):
        lino = ((self.text.count('\n', 0, self.pos) + 1) if self._debug
                else 0)
        self.tokens.append(_Token(kind, value, lino))


class Error(Exception):
    pass


class _Token:

    def __init__(self, kind, value=None, lino=None):
        self.kind = kind
        self.value = value # literal, i.e., correctly typed item
        self.lino = lino


    def __str__(self):
        parts = [self.kind.name]
        if self.lino:
            parts.append(f'#{self.lino}')
        if self.value is not None:
            parts.append(f'={self.value!r}')
        return ''.join(parts)


    def __repr__(self):
        parts = [f'{self.__class__.__name__}({self.kind.name}']
        if self.value is not None:
            parts.append(f', {self.value!r}')
        if self.lino is not None:
            parts.append(f', {self.lino!r}')
        parts.append(')')
        return ''.join(parts)


@enum.unique
class _TokenKind(enum.Enum):
    TABLENAMES_BEGIN = enum.auto()
    TABLENAME = enum.auto()
    FIELDNAME = enum.auto()
    TABLENAMES_END = enum.auto()
    LIST_BEGIN = enum.auto()
    LIST_END = enum.auto()
    DICT_BEGIN = enum.auto()
    DICT_END = enum.auto()
    NULL = enum.auto()
    BOOL = enum.auto()
    INT = enum.auto()
    REAL = enum.auto()
    DATE = enum.auto()
    DATETIME = enum.auto()
    STR = enum.auto()
    BYTES = enum.auto()
    EOF = enum.auto()


########################### TODO ########################
def _parse(tokens, *, warn_is_error=False, _debug=False):
    if not tokens:
        raise Error('no tokens to parse')
    first = tokens[0]
    depth = 0
    if first.kind is _TokenKind.LIST_BEGIN:
        data = parent = []
        states = [_State.IN_LIST]
        depth += 1
    elif first.kind is _TokenKind.DICT_BEGIN:
        data = parent = {}
        states = [_State.IN_DICT]
    else:
        raise Error(f'expected list or dict, got {first}')
    tupletype = None
    depth_for_tupletype = None
    fieldnames = []
    tablename = None
    for token in tokens[1:]:
        if token.kind is _TokenKind.TABLENAMES_BEGIN:
            depth_for_tupletype = depth
            fieldnames = []
            tablename = None
            states.append(_State.IN_TABLENAMES)
        elif token.kind is _TokenKind.TABLENAME:
            if states[-1] is not _State.IN_TABLENAMES:
                raise Error(f'tablename outside tablenames: {token}')
            tablename = token.value
        elif token.kind is _TokenKind.FIELDNAME:
            if states[-1] is not _State.IN_TABLENAMES:
                raise Error(f'fieldname outside tablenames: {token}')
            fieldnames.append(token.value)
        elif token.kind is _TokenKind.TABLENAMES_END:
            if states[-1] is not _State.IN_TABLENAMES:
                raise Error(
                    f'end of tablenames outside tablenames: {token}')
            states.pop()
            tupletype = collections.namedtuple(tablename, fieldnames)
        elif token.kind is _TokenKind.LIST_BEGIN:
            depth += 1
            print(token) ### TODO delete
        elif token.kind is _TokenKind.LIST_END:
            if depth == depth_for_tupletype:
                depth_for_tupletype = None
            depth -= 1
            print(token) ### TODO delete
        elif token.kind is _TokenKind.DICT_BEGIN:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.DICT_END:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.NULL:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.BOOL:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.INT:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.REAL:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.DATE:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.DATETIME:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.STR:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.BYTES:
            print(token) ### TODO delete
        elif token.kind is _TokenKind.EOF:
            print(token) ### TODO delete
        else:
            raise Error(r'invalid token: {token}')
    return data

@enum.unique
class _State(enum.Enum):
    IN_LIST = enum.auto()
    IN_DICT = enum.auto()
    IN_TABLENAMES = enum.auto()


def write(filename_or_filelike, *, data, custom='', compress=False):
    '''
    custom is a short user string (with no newlines), e.g., a file
    description.
    data is a tuple or namedtuple or list or dict that this function will
    write to the filename_or_filelike using the strictest typing that is
    valid for pxd.
    '''
    close = False
    if isinstance(filename_or_filelike, str):
        opener = gzip.open if compress else open
        file = opener(filename_or_filelike, 'wt', encoding=UTF8)
        close = True
    else:
        file = filename_or_filelike
    try:
        _write_header(file, custom)
        # TODO write the data!
        # For a list of namedtuples output a fieldnames followed by lists of
        # items
    finally:
        if close:
            file.close()


def _write_header(file, custom):
    file.write(f'pxd {VERSION}')
    if custom:
        file.write(f' {custom}')
    file.write('\n')


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2 or sys.argv[1] in {'-h', '--help', 'help'}:
        raise SystemExit(
            'usage: pxd.py [-z|--compress] <infile.pxd> [<outfile.pxd>]')
    compress = False
    args = sys.argv[1:]
    infile = outfile = None
    for arg in args:
        if arg in {'-z', '--compress'}:
            compress = True
        elif infile is None:
            infile = arg
        else:
            outfile = arg
    try:
        data = read(infile)
        outfile = sys.stdout if outfile is None else outfile
        write(outfile, data=data.data, custom=data.custom,
              compress=compress)
    except Error as err:
        print(f'Error:{err}')
