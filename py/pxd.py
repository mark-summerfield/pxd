#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

'''
pxd is a plain text human readable storage format that may serve as a
convenient alternative to csv, ini, json, sqlite, toml, xml, or yaml.

pxd's public API provides two functions and five classes.

    def read(filename_or_filelike)

This returns a 2-tuple of (data, custom_header). The data is always a dict
(i.e., a pxd map), list, or pxd.Table.

    def write(filename_or_filelike, data, custom)

This writes the data (and custom header if supplied) into the given file as
pxd data. The data must be a dict, list, or pxd.Table.

    class Error

Used to propagate errors (and warnings if warn_is_error is True).

    class Table

Used to store pxd.Tables. A pxd.Table has a list of fieldnames and a records
list which is a lists of lists with each sublist having the same number of
items as the number of fieldnames.

    namedtuple Pair

Use to store two ints or two floats (e.g., a point). If one_way_conversion
is True then complex numbers are converted to pxd.Pairs.

    namedtuple Triple

Use to store three ints or two floats (e.g., a 3D point).

    namedtuple Quad

Use to store four ints or two floats (e.g., an IPv4 address).
'''

import collections
import datetime
import enum
import gzip
import re
import sys
from xml.sax.saxutils import escape, unescape

try:
    from dateutil.parser import isoparse
except ImportError:
    isoparse = None


__all__ = ('__version__', 'VERSION', 'read', 'Table', 'write')
__version__ = '1.0.0' # pxd module version
VERSION = 1.0 # pxd file format version
UTF8 = 'utf-8'


def read(filename_or_filelike, *, warn_is_error=False):
    '''
    Returns a 2-tuple, the first item of which is a dict (i.e., a pxd map),
    list, or pxd.Table containing all the pxd data read. The second item is
    the custom string (if any) from the file's header.

    filename_or_filelike is sys.stdin or a filename or an open readable file
    (text mode UTF-8 encoded).

    If warn_is_error is True warnings raise Error exceptions.
    '''
    data = None
    tokens, custom, text = _tokenize(
        filename_or_filelike, warn_is_error=warn_is_error)
    data = _parse(tokens, text=text, warn_is_error=warn_is_error)
    return data, custom


def _tokenize(filename_or_filelike, *, warn_is_error=False):
    text = _read_text(filename_or_filelike)
    lexer = _Lexer(warn_is_error=warn_is_error)
    tokens = lexer.tokenize(text)
    return tokens, lexer.custom, text


def _read_text(filename_or_filelike):
    if not isinstance(filename_or_filelike, str):
        return filename_or_filelike.read()
    try:
        with gzip.open(filename_or_filelike, 'rt', encoding=UTF8) as file:
            return file.read()
    except gzip.BadGzipFile:
        with open(filename_or_filelike, 'rt', encoding=UTF8) as file:
            return file.read()


class _ErrorMixin:

    def warn(self, message):
        if self.warn_is_error:
            self.error(message)
        lino = self.text.count('\n', 0, self.pos) + 1
        print(f'warning:{self._what}:{lino}: {message}')


    def error(self, message):
        lino = self.text.count('\n', 0, self.pos) + 1
        raise Error(f'{self._what}:{lino}: {message}')


class _Lexer(_ErrorMixin):

    def __init__(self, *, warn_is_error=False):
        self.warn_is_error = warn_is_error
        self._what = 'lexer'


    def clear(self):
        self.text_kind = _Kind.STR
        self.pos = 0 # current
        self.custom = None
        self.tokens = []


    def tokenize(self, text):
        self.clear()
        self.text = text
        self.scan_header()
        while not self.at_end():
            self.scan_next()
        self.add_token(_Kind.EOF)
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


    def at_end(self):
        return self.pos >= len(self.text)


    def scan_next(self):
        c = self.getch()
        if c.isspace():
            pass
        elif c == '[':
            if self.peek() == '=':
                self.pos += 1
                self.add_token(_Kind.TABLE_BEGIN)
                self.text_kind = _Kind.TABLE_NAME
            else:
                self.add_token(_Kind.LIST_BEGIN)
        elif c == '=':
            if self.peek() == ']':
                self.pos += 1
                self.add_token(_Kind.TABLE_END)
                self.text_kind = _Kind.STR
            elif self.text_kind is _Kind.TABLE_FIELD_NAME:
                self.add_token(_Kind.TABLE_ROWS)
                self.text_kind = _Kind.STR
            else:
                self.error(f'unexpected character encountered: {c!r}')
        elif c == ']':
            self.add_token(_Kind.LIST_END)
        elif c == '{':
            self.add_token(_Kind.DICT_BEGIN)
        elif c == '}':
            self.add_token(_Kind.DICT_END)
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
        self.add_token(self.text_kind, unescape(value))
        if self.text_kind is _Kind.TABLE_NAME:
            self.text_kind = _Kind.TABLE_FIELD_NAME


    def read_bytes(self):
        value = self.match_to(')', error_text='unterminated bytes')
        self.add_token(_Kind.BYTES, bytes.fromhex(value))


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
            self.add_token(_Kind.REAL if is_real else _Kind.INT,
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
            token = _Kind.DATE_TIME
        elif hyphens == 2:
            convert = (datetime.date.fromisoformat if isoparse is None
                       else isoparse)
            token = _Kind.DATE
        elif is_real:
            convert = float
            token = _Kind.REAL
        else:
            convert = int
            token = _Kind.INT
        try:
            value = convert(text)
            if token is _Kind.DATE and isoparse is not None:
                value = value.date()
            self.add_token(token, value)
        except ValueError as err:
            self.error(f'invalid number or date/time: {text}: {err}')


    def read_const(self):
        match = self.match_any_of('no', 'yes', 'null', 'true', 'false')
        if match == 'null':
            self.add_token(_Kind.NULL)
        elif match in {'no', 'false'}:
            self.add_token(_Kind.BOOL, False)
        elif match in {'yes', 'true'}:
            self.add_token(_Kind.BOOL, True)
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
                self.pos += len(target) - 1 # skip past target
                return target


    def add_token(self, kind, value=None):
        self.tokens.append(_Token(kind, value, self.pos))


class Error(Exception):
    pass


class _Token:

    def __init__(self, kind, value=None, pos=-1):
        self.kind = kind
        self.value = value # literal, i.e., correctly typed item
        self.pos = pos


    def __str__(self):
        parts = [self.kind.name]
        if self.value is not None:
            parts.append(f'={self.value!r}')
        return ''.join(parts)


    def __repr__(self):
        parts = [f'{self.__class__.__name__}({self.kind.name}']
        if self.value is not None:
            parts.append(f', {self.value!r}')
        parts.append(')')
        return ''.join(parts)


@enum.unique
class _Kind(enum.Enum):
    TABLE_BEGIN = enum.auto()
    TABLE_NAME = enum.auto()
    TABLE_FIELD_NAME = enum.auto()
    TABLE_ROWS = enum.auto()
    TABLE_END = enum.auto()
    LIST_BEGIN = enum.auto()
    LIST_END = enum.auto()
    DICT_BEGIN = enum.auto()
    DICT_END = enum.auto()
    NULL = enum.auto()
    BOOL = enum.auto()
    INT = enum.auto()
    REAL = enum.auto()
    DATE = enum.auto()
    DATE_TIME = enum.auto()
    STR = enum.auto()
    BYTES = enum.auto()
    EOF = enum.auto()


class Table:

    def __init__(self, *, name=None, fieldnames=None, items=None):
        '''Used to store a pxd.Table.

        A pxd.Table has a list of fieldnames and a records list which is a
        lists of lists with each sublist having the same number of items as
        the number of fieldnames.

        items can be a flat list of values (which will be put into a list
        of lists with each sublist being len(fieldnames) long), or a list of
        lists in which case each list is _assumed_ to be len(fieldnames)
        long.

        When a pxd.Table is iterated each row is returned as a namedtuple.
        '''
        self.name = name
        self._Class = None
        self.fieldnames = [] if fieldnames is None else fieldnames
        self.records = []
        if items:
            if isinstance(items, list):
                if self._Class is None:
                    self._make_class()
                self.records = items
            else:
                for value in items:
                    self.append(value)


    def append_fieldname(self, name):
        self.fieldnames.append(name)


    def append(self, value):
        if self._Class is None:
            self._make_class()
        if (not self.records or
                len(self.records[-1]) >= len(self.fieldnames)):
            self.records.append([])
        self.records[-1].append(value)


    def _make_class(self):
        if not self.name:
            raise Error('can\'t use an unnamed Table')
        if not self.fieldnames:
            raise Error('can\'t create a Table with no field names')
        self._Class = collections.namedtuple(
            _canonicalize(self.name, 'Table'),
            [_canonicalize(name, f'Field{i}')
             for i, name in enumerate(self.fieldnames, 1)])


    def __iadd__(self, value):
        if not self.name:
            raise Error('can\'t append to an unnamed Table')
        if not self.fieldnames:
            raise Error('can\'t append to a Table with no field names')
        if isinstance(value, (list, tuple)): # or: collections.abc.Sequence?
            for v in value:
                self.append(v)
        else:
            self.append(value)
        return self


    def __iter__(self):
        if self._Class is None:
            self._make_class()
        for record in self.records:
            yield self._Class(*record)


    def __len__(self):
        return len(self.records)


    def __str__(self):
        return (f'Table {self.name!r} {self.fieldnames!r} with '
                f'{len(self.records)} records')


def _canonicalize(s, prefix):
    s = re.sub(r'\W+', '', s)
    if not s:
        s = f'{prefix}{id(s):X}'
    elif not s.isalpha():
        s = prefix + s
    return s


def _parse(tokens, *, text, warn_is_error=False):
    parser = _Parser()
    return parser.parse(tokens, text)


class _Parser(_ErrorMixin):

    def __init__(self, *, warn_is_error=False):
        self.warn_is_error = warn_is_error
        self._what = 'parser'


    def clear(self):
        self.keys = []
        self.stack = []
        self.pos = -1
        self.states = [_Expect.COLLECTION]


    def parse(self, tokens, text):
        self.clear()
        self.tokens = tokens
        self.text = text
        data = None
        for token in tokens:
            if token.kind is _Kind.EOF:
                break
            self.pos = token.pos
            state = self.states[-1]
            if state is _Expect.COLLECTION:
                if not self._is_collection_start(token.kind):
                    self.error(f'expected dict (pxd map), list, or '
                               f'pxd.Table, got {token}')
                self.states.pop() # _Expect.COLLECTION
                self._on_collection_start(token.kind)
                data = self.stack[0]
            elif state is _Expect.TABLE_NAME:
                self._handle_table_name(token)
            elif state is _Expect.TABLE_FIELD_NAME:
                self._handle_field_name(token)
            elif state is _Expect.TABLE_VALUE:
                self._handle_table_value(token)
            elif state is _Expect.DICT_KEY:
                self._handle_dict_key(token)
            elif state is _Expect.DICT_VALUE:
                self._handle_dict_value(token)
            elif state is _Expect.EOF:
                if token.kind is not _Kind.EOF:
                    self.error(f'expected EOF, got {token}')
                break # should be redundant
            elif state is _Expect.ANY_VALUE:
                if token.kind is not _Kind.EOF:
                    self._handle_any_value(token)
        return data


    def _is_collection_start(self, kind):
        return kind in {_Kind.DICT_BEGIN, _Kind.LIST_BEGIN,
                        _Kind.TABLE_BEGIN}


    def _is_collection_end(self, kind):
        return kind in {_Kind.DICT_END, _Kind.LIST_END,
                        _Kind.TABLE_END}


    def _on_collection_start(self, kind):
        if kind is _Kind.DICT_BEGIN:
            self.states.append(_Expect.DICT_KEY)
            self._on_collection_start_helper(dict)
        elif kind is _Kind.LIST_BEGIN:
            self.states.append(_Expect.ANY_VALUE)
            self._on_collection_start_helper(list)
        elif kind is _Kind.TABLE_BEGIN:
            self.states.append(_Expect.TABLE_NAME)
            self._on_collection_start_helper(Table)
        else:
            self.error('expected to create dict (pxd map), list, or '
                       f'pxd.Table, not {kind}')


    def _on_collection_start_helper(self, Class):
        if self.stack and isinstance(self.stack[-1], list):
            self.stack[-1].append(Class())
            self.stack.append(self.stack[-1][-1])
        else:
            self.stack.append(Class())


    def _on_collection_end(self, token):
        self.states.pop()
        self.stack.pop()
        if self.stack:
            if isinstance(self.stack[-1], list):
                self.states.append(_Expect.ANY_VALUE)
            elif isinstance(self.stack[-1], dict):
                self.states.append(_Expect.DICT_KEY)
            elif isinstance(self.stack[-1], Table):
                self.states.append(_Expect.TABLE_VALUE)
            else:
                self.error(f'unexpected token, {token}')
        else:
            self.states.append(_Expect.EOF)


    def _handle_table_name(self, token):
        if token.kind is not _Kind.TABLE_NAME:
            self.error(f'expected Table name, got {token}')
        self.stack[-1].name = token.value
        self.states[-1] = _Expect.TABLE_FIELD_NAME


    def _handle_field_name(self, token):
        if token.kind is _Kind.TABLE_ROWS:
            self.states[-1] = _Expect.TABLE_VALUE
        else:
            if token.kind is not _Kind.TABLE_FIELD_NAME:
                self.error(f'expected Table field name, got {token}')
            self.stack[-1].append_fieldname(token.value)


    def _handle_table_value(self, token):
        if token.kind is _Kind.TABLE_END:
            self._on_collection_end(token)
        elif token.kind in {
                _Kind.NULL, _Kind.BOOL, _Kind.INT,
                _Kind.REAL, _Kind.DATE, _Kind.DATE_TIME,
                _Kind.STR, _Kind.BYTES}:
            self.stack[-1] += token.value
        else:
            self.error('Table values may only be null, bool, int, real, '
                       f'date, datetime, str, or bytes, got {token}')


    def _handle_dict_key(self, token):
        if token.kind is _Kind.DICT_END:
            self._on_collection_end(token)
        elif token.kind in {
                _Kind.INT, _Kind.DATE, _Kind.DATE_TIME,
                _Kind.STR, _Kind.BYTES}:
            self.keys.append(token.value)
            self.states[-1] = _Expect.DICT_VALUE
        else:
            self.error('dict (pxd map) keys may only be int, date, '
                       f'datetime, str, or bytes, got {token}')


    def _handle_dict_value(self, token):
        if self._is_collection_start(token.kind):
            # this adds a new list, dict, or Table to the stack
            self._on_collection_start(token.kind)
            # this adds a key-value item to the dict that contains the above
            # list, dict, or Table, the key being the key acquired earlier,
            # the value being the new list, dict, or Table
            self.stack[-2][self.keys[-1]] = self.stack[-1]
        elif self._is_collection_end(token.kind):
            self.states[-1] = _Expect.DICT_KEY
            self.stack.pop()
            if self.stack and isinstance(self.stack[-1], dict):
                self.keys.pop()
        else: # a scalar
            self.states[-1] = _Expect.DICT_KEY
            self.stack[-1][self.keys.pop()] = token.value


    def _handle_any_value(self, token):
        if self._is_collection_start(token.kind):
            # this adds a new list, dict, or Table to the stack
            self._on_collection_start(token.kind)
        elif self._is_collection_end(token.kind):
            self.states.pop()
            if self.states and self.states[-1] is _Expect.DICT_VALUE:
                self.states[-1] = _Expect.DICT_KEY
            self.stack.pop()
        else: # a scalar
            self.stack[-1].append(token.value)


@enum.unique
class _Expect(enum.Enum):
    COLLECTION = enum.auto()
    DICT_KEY = enum.auto()
    DICT_VALUE = enum.auto()
    ANY_VALUE = enum.auto()
    TABLE_NAME = enum.auto()
    TABLE_FIELD_NAME = enum.auto()
    TABLE_VALUE = enum.auto()
    EOF = enum.auto()


def write(filename_or_filelike, *, data, custom='', compress=False,
          indent=2, one_way_conversion=False):
    '''
    filename_or_filelike is sys.stdout or a filename or an open writable
    file (text mode UTF-8 encoded).

    data is a list, dict (i.e., pxd map), or pxd.Table that this function
    will write to the filename_or_filelike in pxd format.

    custom is an optional short user string (with no newlines), e.g., a file
    type description.

    If compress is True and the filename_or_filelike is a file (not stdout)
    then gzip compression is used.

    Set indent to 0 to minimize the file size.
    '''
    pad = ' ' * indent
    close = False
    if isinstance(filename_or_filelike, str):
        opener = gzip.open if compress else open
        file = opener(filename_or_filelike, 'wt', encoding=UTF8)
        close = True
    else:
        file = filename_or_filelike
    try:
        _Writer(file, custom, data, pad, one_way_conversion)
    finally:
        if close:
            file.close()


class _Writer:

    def __init__(self, file, custom, data, pad, one_way_conversion):
        self.file = file
        self.one_way_conversion = one_way_conversion
        self.write_header(custom)
        self.write_value(data, pad=pad)


    def write_header(self, custom):
        self.file.write(f'pxd {VERSION}')
        if custom:
            self.file.write(f' {custom}')
        self.file.write('\n')


    def write_value(self, item, indent=0, *, pad, dict_value=False):
        if self.one_way_conversion and isinstance(item, (
                set, frozenset, tuple, collections.deque)):
            item = list(item)
        if isinstance(item, list):
            return self.write_list(item, indent, pad=pad,
                                   dict_value=dict_value)
        if isinstance(item, dict):
            return self.write_dict(item, indent, pad=pad,
                                   dict_value=dict_value)
        if isinstance(item, Table):
            return self.write_table(item, indent, pad=pad,
                                    dict_value=dict_value)
        return self.write_scalar(item, indent=indent, pad=pad,
                                 dict_value=dict_value)


    def write_list(self, item, indent=0, *, pad, dict_value=False):
        tab = '' if dict_value else pad * indent
        if len(item) == 0:
            self.file.write(f'{tab}[]')
            return False
        self.file.write(f'{tab}[')
        indent += 1
        is_scalar = _is_scalar(item[0])
        if is_scalar:
            kwargs = dict(indent=0, pad=' ', dict_value=False)
        else:
            self.file.write('\n')
            kwargs = dict(indent=indent, pad=pad, dict_value=False)
        for value in item:
            self.write_value(value, **kwargs)
            if is_scalar:
                kwargs['indent'] = 1 # 0 for first item
        tab = pad * (indent - 1)
        self.file.write(']\n' if is_scalar else f'{tab}]\n')
        return True


    def write_dict(self, item, indent=0, *, pad, dict_value=False):
        tab = '' if dict_value else pad * indent
        if len(item) == 0:
            self.file.write(f'{tab}{{}}')
            return False
        elif len(item) == 1:
            self.file.write(f'{tab}{{')
            key, value = list(item.items())[0]
            self.write_scalar(key, 1, pad=' ')
            self.file.write(' ')
            self.write_value(value, 1, pad=' ', dict_value=True)
            self.file.write('}}')
            return False
        self.file.write(f'{tab}{{\n')
        indent += 1
        for key, value in item.items():
            self.write_scalar(key, indent, pad=pad)
            self.file.write(' ')
            if not self.write_value(value, indent, pad=pad,
                                    dict_value=True):
                self.file.write('\n')
        tab = pad * (indent - 1)
        self.file.write(f'{tab}}}\n')
        return True


    def write_table(self, item, indent=0, *, pad, dict_value=False):
        tab = '' if dict_value else pad * indent
        self.file.write(f'{tab}[= <{escape(item.name)}>')
        for name in item.fieldnames:
            self.file.write(f' <{escape(name)}>')
        if len(item) == 0:
            self.file.write(' = =]')
            return False
        self.file.write(' =\n')
        indent += 1
        for record in item:
            self.file.write(pad * indent)
            for value in record:
                self.write_scalar(value, pad=pad)
                self.file.write(' ')
            self.file.write('\n')
        tab = pad * (indent - 1)
        self.file.write(f'{tab}=]\n')
        return True


    def write_scalar(self, item, indent=0, *, pad, dict_value=False):
        if not dict_value:
            self.file.write(pad * indent)
        if item is None:
            self.file.write('null')
        elif isinstance(item, bool):
            self.file.write('yes' if item else 'no')
        elif isinstance(item, int):
            self.file.write(str(item))
        elif isinstance(item, float):
            self.file.write(_realstr(item))
        elif isinstance(item, (datetime.date, datetime.datetime)):
            self.file.write(item.isoformat())
        elif isinstance(item, str):
            self.file.write(f'<{escape(item)}>')
        elif isinstance(item, bytes) or (self.one_way_conversion and
                                         isinstance(item, bytearray)):
            self.file.write(f'({item.hex().upper()})')
        else:
            print(f'error: ignoring unexpected item of type {type(item)}: '
                  f'{item!r}', file=sys.stderr)
        return False


def _realstr(s):
    value = str(s)
    if '.' not in value:
        i = value.find('e')
        if i == -1:
            i = value.find('E')
        if i == -1:
            value += '.0'
        else:
            value = value[:i] + '.0' + value[i:]
    return value


def _is_scalar(x):
    return x is None or isinstance(
        x, (bool, int, float, datetime.date, datetime.datetime, str, bytes,
            bytearray))


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in {'-h', '--help', 'help'}:
        raise SystemExit('''\
usage: pxd.py [-z|--compress] [-iN|--indent=N] <infile.pxd> [<outfile.pxd>]

gzip compression is ignored if no outfile (i.e., for stdout).
indent defaults to 2 (range 0-8) e.g., -i0 or --indent=0 (with no space)
''')
    compress = False
    indent = 2
    args = sys.argv[1:]
    infile = outfile = None
    for arg in args:
        if arg in {'-z', '--compress'}:
            compress = True
        elif arg.startswith(('-i', '--indent=')):
            if arg[1] == 'i':
                indent = int(arg[2:])
            else:
                indent = int(arg[9:])
            if not 0 <= indent <= 9:
                indent = 2
        elif infile is None:
            infile = arg
        else:
            outfile = arg
    try:
        data, custom = read(infile)
        outfile = sys.stdout if outfile is None else outfile
        write(outfile, data=data, custom=custom, compress=compress,
              indent=indent)
    except Error as err:
        print(f'Error:{err}')
