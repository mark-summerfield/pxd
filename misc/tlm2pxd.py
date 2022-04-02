#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import gzip
import sys
from xml.sax.saxutils import escape


def main():
    custom = ''
    in_tracks = False
    in_list = False
    end = ''
    with open('playlists-tlm.pxd', 'wt', encoding='utf-8') as outfile:
        with gzip.open(sys.argv[1], 'rt', encoding='utf-8') as infile:
            for line in infile:
                if line.startswith('\f'):
                    line = line.strip()
                    if line.startswith('TLM'):
                        custom = line.strip().replace('\t', ' ')
                        outfile.write(f'pxd 1.0 {custom}')
                        outfile.write('\n{\n<items> [\n')
                        outfile.write(
                            ' [= <Items> <indent> <leaf> <tracks> =]\n')
                    elif line == 'TRACKS':
                        in_tracks = True
                    elif line == 'HISTORY':
                        if in_list:
                            outfile.write('  ]\n ]\n')
                            in_list = False
                        outfile.write(']\n') # end of items
                        in_tracks = False
                        outfile.write('<history> [\n')
                        end = ' ]\n'
                elif line.startswith('\v'):
                    if in_list:
                        outfile.write('  ]\n ]\n')
                        in_list = False
                    in_list = True
                    indent = line.count('\v')
                    text = escape(line[indent:].strip())
                    outfile.write(f' [{indent} <{text}> [\n')
                    outfile.write('  [= <Tracks> <filename> <secs> =]\n')
                elif in_tracks:
                    parts = line.strip().split('\t', 1)
                    filename = escape(parts[0])
                    outfile.write(f'  [<{filename}> {parts[1]}]\n')
                else: # in history
                    text = escape(line.strip())
                    outfile.write(f'   <{text}>\n')
        outfile.write(end)
        outfile.write('}\n')


if __name__ == '__main__':
    main()
