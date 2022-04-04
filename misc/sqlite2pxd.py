#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import gzip
import sys
from xml.sax.saxutils import escape


def main():
    # 'biller2.bdb' use sqlite3 module
    with gzip.open(sys.argv[1], 'rt', encoding='utf-8') as reader:
        pass


if __name__ == '__main__':
    main()

