#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import gzip
import sys
from xml.sax.saxutils import escape
import xml.dom.minidom


def main():
    with gzip.open(sys.argv[1], 'rt', encoding='utf-8') as file:
        text = file.read()
    tree = xml.dom.minidom.parseString(text)
    with gzip.open('timelog.pxd', 'wt', encoding='utf-8') as out:
        out.write(f'pxd 1.0 Timelog 1.0\n{')
        for element in tree.getElementsByTagName('PROJECT'):
            # TODO pxd data design???
            # write <project name> { <done> done <tasks> [
            #   [#<Tasks>
            print(element)
        out.write('}\n')


if __name__ == '__main__':
    main()
