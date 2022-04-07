#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import filecmp
import os
import subprocess

os.chdir(os.path.dirname(__file__))


def main():
    pxd = '../pxd.py'
    total = ok = 0
    cleanup()
    for name in sorted(os.listdir('.')):
        if os.path.isfile(name) and name.endswith('.pxd'):
            total += 1
            actual = f'actual/{name}'
            expected = f'expected/{name}'
            subprocess.call([pxd, name, actual])
            if filecmp.cmp(actual, expected, False):
                print(f'{name} OK')
                ok += 1
            else:
                print(f'{name} FAIL {actual} != {expected}')
    print(f'{ok}/{total}', 'OK' if total == ok else 'FAIL')
    if total == ok:
        cleanup()


def cleanup():
    for name in os.listdir('actual'):
        name = f'actual/{name}'
        if os.path.isfile(name) and name.endswith('.pxd'):
            os.remove(name)


if __name__ == '__main__':
    main()
