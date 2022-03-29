#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import os
from xml.sax.saxutils import unescape

import regex as re

os.chdir(os.path.dirname(__file__))

FILES = ('../eg/tlm-ini-u.pxd', '../eg/tlm-ini-t.pxd')


def main():
    for filename in FILES:
        config = Config()
        try:
            with open(filename, 'rt', encoding='utf-8') as file:
                text = file.read()
            custom, text = pxd_read_header(text)
            if custom is None:
                print(f'opened {filename!r} with no custom text')
            else:
                print(f'opened {filename!r} custom text is {custom!r}')
            definitions, text = pxd_read_defs(text)
            read_config(config, definitions, text)
            print()
        except Error as err:
            print(err)


def read_config(config, definitions, text):
    print('Definitions', definitions)
    print()
    print(config)
    print()
    # TODO read the data and populate the config


def pxd_read_header(text):
    i = text.find('\n')
    if i == -1:
        raise Error('unrecognized as .pxd file')
    custom = _pxd_check_header(text[:i])
    return custom, text[i + 1:]


def _pxd_check_header(line):
    match = re.match(r'pxd\s+(?P<version>\d+\.\d+)(?P<custom>.*)?', line)
    if match is None:
        raise Error('invalid .pxd file')
    try:
        version = float(match['version'])
        if version > 1.0:
            raise Error('.pxd version too high')
    except ValueError:
        raise Error('unrecognized .pxd version')
    custom = match['custom']
    return custom.strip() if custom else None


def pxd_read_defs(text):
    definitions = {}
    offset = 0
    for match in re.finditer(
            r'def\s+(?P<id>\p{Lu}\w{,32})\s*[{](?P<keyvals>.*?)[}]', text,
            re.DOTALL):
        offset = match.end()
        id = match['id']
        definitions[id] = {}
        for name, kind in re.findall(r'<([^<>]+)>\s+(\p{L}\w*)',
                                     match['keyvals'], re.DOTALL):
            definitions[id][unescape(name)] = kind
    return definitions, text[offset:]


class Error(Exception):
    pass


class Window:

    def __init__(self, *, x=0, y=0, width=640, height=480, scale=1.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.scale = scale


    def __repr__(self):
        return (f'{self.__class__.__name__}(x={self.x!r}, y={self.y!r}, '
                f'width={self.width!r}, height={self.height!r}, '
                f'scale={self.scale!r})')


class Config:

    def __init__(self, *, autosave=False, historysize=35, volume=1.0):
        self.autosave = autosave
        self.historysize = historysize
        self.volume = volume
        self.files = {}
        self.window = Window()


    def __repr__(self):
        return (f'{self.__class__.__name__}(autosave={self.autosave!r}, '
                f'historysize={self.historysize!r}, '
                f'volume={self.volume!r}) + files={self.files!r} + '
                f'{self.window!r}')



if __name__ == '__main__':
    main()
