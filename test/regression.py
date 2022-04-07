#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import filecmp
import os
import re
import subprocess
import sys

os.chdir(os.path.dirname(__file__))


def main():
    exe = '../py/pxd/__init__.py'
    if len(sys.argv) > 1:
        if sys.argv[1] in {'-h', '--help'}:
            raise SystemExit('usage: regression.py [path/to/pxd-exe]')
        exe = sys.argv[1]
    total = ok = 0
    cleanup()
    for name in sorted(os.listdir('.'), key=by_number):
        if os.path.isfile(name) and name.endswith('.pxd'):
            total += 1
            actual = f'actual/{name}'
            expected = f'expected/{name}'
            subprocess.call([exe, name, actual])
            if filecmp.cmp(actual, expected, False):
                print(f'{name} OK')
                ok += 1
            else:
                print(f'{name} FAIL {actual} != {expected}')
    print(f'{ok}/{total}', 'All OK' if total == ok else 'FAIL')
    if total == ok:
        cleanup()


def cleanup():
    if os.path.exists('actual'):
        for name in os.listdir('actual'):
            name = f'actual/{name}'
            if os.path.isfile(name) and name.endswith('.pxd'):
                os.remove(name)
    else:
        os.mkdir('actual')


def by_number(s):
    match = re.match(r'(?P<name>\D+)(?P<number>\d+)', s)
    if match is not None:
        return match['name'], int(match['number'])
    return s, 0


if __name__ == '__main__':
    main()
