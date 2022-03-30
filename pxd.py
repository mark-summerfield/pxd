#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import collections
import enum
import gzip
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
        self.current = 0
        self.lino = 1
        self.custom = None
        self.tokens = []
        self.scan_header()


    def scan_header(self):
        i = self.text.find('\n')
        if i == -1:
            self.error('missing pxd file header or empty file')
        self.current = i
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
            return self.error(message)
        print(f'warning:#{self.lino}: {message}')


    def error(self, message):
        raise Error(f'#{self.lino}: {message}')


    def scan(self):
        while not self.at_end():
            self.start = self.current
            self.scan_next()
        self.add_token(_TokenKind.EOF)
        for token in self.tokens: # TODO delete
            print(token) # TODO delete
        return self.tokens


    def at_end(self):
        return self.current >= len(self.text)


    def scan_next(self):
        c = self.advance()
        if c.isspace():
            if c == '\n':
                self.lino += 1
            #if self.tokens[-1].kind != _TokenKind.SPACE:
            #    self.add_token(_TokenKind.SPACE)
        elif c == '=':
            self.add_token(_TokenKind.EQUAL)
        elif c == '[':
            self.add_token(_TokenKind.BRACKET_OPEN)
        elif c == ']':
            self.add_token(_TokenKind.BRACKET_CLOSE)
        elif c == '{':
            self.add_token(_TokenKind.BRACE_OPEN)
        elif c == '}':
            self.add_token(_TokenKind.BRACE_CLOSE)
        elif c == '<':
            self.read_string()
        elif c == '(':
            self.read_bytes()
        elif c.isdigit():
            pass # TODO self.read_number_or_date()
        elif c.isupper():
            pass # TODO self.read_recdef_name()
        elif c.isalpha():
            pass # TODO self.read_const_or_typename()
        else:
            self.error(f'invalid character encountered: {c!r}')


    def read_string(self):
        while self.peek() != '>' and not self.at_end():
            if self.peek() == '\n':
                self.lino += 1
            self.advance()
        if self.at_end():
            self.error('unterminated string')
        else:
            self.advance() # over the closing '>'
            value = self.text[self.start + 1:self.current - 1]
            self.add_token(_TokenKind.STR, value=unescape(value))


    def read_bytes(self):
        while self.peek() != ')' and not self.at_end():
            if self.peek() == '\n':
                self.lino += 1
            self.advance()
        if self.at_end():
            self.error('unterminated string')
        else:
            self.advance() # over the closing ')'
            value = self.text[self.start + 1:self.current - 1]
            self.add_token(_TokenKind.BYTES, value=bytes.fromhex(value))


    def advance(self):
        c = self.text[self.current]
        self.current += 1
        return c


    def match(self, c):
        if self.at_end() or self.text[self.current] != c:
            return False
        self.current += 1
        return True


    def peek(self):
        if self.at_end():
            return '\0'
        return self.text[self.current]


    def add_token(self, kind, *, value=None, text=None):
        self.tokens.append(_Token(self.lino, kind, value=value, text=text))


class Error(Exception):
    pass


class _Token:

    def __init__(self, lino, kind, *, value=None, text=None):
        self.lino = lino
        self.kind = kind
        self.value = value # literal, i.e., correctly typed item
        self.text = text # lexeme, i.e., the original text


    def __repr__(self):
        return (f'{self.__class__.__name__}({self.lino!r}, '
                f'{self.kind.name}, value={self.value!r}, '
                f'text={self.text!r})')


@enum.unique
class _TokenKind(enum.Enum):
    EQUAL = enum.auto()
    BRACKET_OPEN = enum.auto()
    BRACKET_CLOSE = enum.auto()
    BRACE_OPEN = enum.auto()
    BRACE_CLOSE = enum.auto()
    NONE = enum.auto()
    BOOL = enum.auto()
    INT = enum.auto()
    REAL = enum.auto()
    DATE = enum.auto()
    DATETIME = enum.auto()
    STR = enum.auto()
    BYTES = enum.auto()
    EOF = enum.auto()
    #LIST = enum.auto()
    #RECORDS = enum.auto()
    #DICT = enum.auto()


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
        print(f'Error: {err}')
