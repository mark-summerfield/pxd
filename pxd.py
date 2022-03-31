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


def read(filename_or_filelike):
    '''
    Returns a PxdData whose Data is a tuple or dict or list using Python
    type equivalents to pxd types by parsing the filename_or_filelike and
    whose Custom is the short user string (if any).
    '''
    custom = None
    data = None
    text = _read_text(filename_or_filelike)
    lexer = _Lexer(text)
    tokens = lexer.scan()

    ### TODO delete
    for token in tokens:
        print(token)
    ### TODO end delete

    # TODO parse tokens
    return PxdData(data, custom)


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

    def __init__(self, text, *, warn_is_error=False):
        self.text = text
        self.warn_is_error = warn_is_error
        self.pos = 0 # current
        self.custom = None
        self.tokens = []
        self.scan_header()


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


    def scan(self):
        while not self.at_end():
            self.scan_next()
        self.add_token(_TokenKind.EOF)
        return self.tokens


    def at_end(self):
        return self.pos >= len(self.text)


    def scan_next(self):
        c = self.getch()
        if c.isspace():
            pass
        elif c == '[':
            if self.peek() == '=':
                self.pos += 1
                self.add_token(_TokenKind.STRLIST_BEGIN)
            else:
                self.add_token(_TokenKind.LIST_BEGIN)
        elif c == ']':
            self.add_token(_TokenKind.LIST_END)
        elif c == '{':
            self.add_token(_TokenKind.DICT_BEGIN)
        elif c == '}':
            self.add_token(_TokenKind.DICT_END)
        elif c == '<':
            self.read_string()
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


    def read_string(self):
        value = self.match_to('>', error_text='unterminated string')
        self.add_token(_TokenKind.STR, unescape(value))


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
        self.tokens.append(_Token(kind, value))


class Error(Exception):
    pass


class _Token:

    def __init__(self, kind, value=None):
        self.kind = kind
        self.value = value # literal, i.e., correctly typed item


    def __str__(self):
        return (f'{self.kind.name}={self.value!r}' if self.value is not None
                else self.kind.name)


    def __repr__(self):
        return (f'{self.__class__.__name__}({self.kind.name}, '
                f'{self.value!r})')


@enum.unique
class _TokenKind(enum.Enum):
    STRLIST_BEGIN = enum.auto()
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
    finally:
        if close:
            file.close()


def _write_header(file, custom):
    file.write(f'pxd {VERSION}')
    if custom:
        file.write(custom)
    file.write('\n')


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2 or sys.argv[1] in {'-h', '--help', 'help'}:
        raise SystemExit('usage: pxd.py <filename.pxd>')
    try:
        data = read(sys.argv[1])
        write(sys.stdout, data=data.data, custom=data.custom)
    except Error as err:
        print(f'Error:{err}')
