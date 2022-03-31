#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import collections
import enum
import gzip
import re
from xml.sax.saxutils import unescape

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
    lexer = Lexer(text)
    tokens = lexer.scan()
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


class Lexer:

    def __init__(self, text, *, warn_is_error=False):
        self.text = text
        self.warn_is_error = warn_is_error
        self.start = 0
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
            self.start = self.pos
            self.scan_next()
        self.add_token(_TokenKind.EOF)
        for token in self.tokens: # TODO delete
            print(token) # TODO delete
        return self.tokens


    def at_end(self):
        return self.pos >= len(self.text)


    def scan_next(self):
        c = self.advance()
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
        elif c == '-' and self.peek().isdigit():
            c = self.advance()
            self.read_number_or_date(c, minus=True)
        elif c.isdigit():
            self.read_number_or_date(c)
        elif c.isalpha():
            self.read_const()
        else:
            self.error(f'invalid character encountered: {c!r}')


    def read_string(self):
        value = self.advance_to_closing('>')
        if value is None:
            self.error('unterminated string')
        self.add_token(_TokenKind.STR, value=unescape(value))


    def read_bytes(self):
        value = self.advance_to_closing(')')
        if value is None:
            self.error('unterminated bytes')
        self.add_token(_TokenKind.BYTES, value=bytes.fromhex(value))


    def read_const(self):
        match = self.advance_to_match('no', 'yes', 'null', 'true', 'false')
        if match == 'null':
            self.add_token(_TokenKind.NULL)
        elif match in {'no', 'false'}:
            self.add_token(_TokenKind.BOOL, value=False)
        elif match in {'yes', 'true'}:
            self.add_token(_TokenKind.BOOL, value=True)


    def read_number_or_date(self, c, *, minus=False):
        match = re.match(r'[-+.:etz\d]+', self.text[self.pos - 1:],
                         re.IGNORECASE | re.DOTALL)
        if match is not None:
            text = match.group()
            self.pos += match.end()
            # TODO match date/datetime else float else int
            print((text,))
        ######### TODO ##################


    def peek(self):
        return '\0' if self.at_end() else self.text[self.pos]


    def advance(self):
        c = self.text[self.pos]
        self.pos += 1
        return c


    def advance_to_match(self, *targets):
        if self.at_end():
            return None
        for target in targets:
            if self.text.startswith(target, self.pos):
                self.pos += len(target)
                return target


    def advance_to_closing(self, c):
        if self.at_end():
            return None
        i = self.text.find(c, self.pos)
        if i > -1:
            text = self.text[self.pos:i]
            self.pos = i + 1 # skip closing c
            return text


    def add_token(self, kind, *, value=None, text=None):
        self.tokens.append(_Token(kind, value=value, text=text))


class Error(Exception):
    pass


class _Token:

    def __init__(self, kind, *, value=None, text=None):
        self.kind = kind
        self.value = value # literal, i.e., correctly typed item
        self.text = text # lexeme, i.e., the original text


    def __repr__(self):
        return (f'{self.__class__.__name__}({self.kind.name}, '
                f'value={self.value!r}, text={self.text!r})')


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
