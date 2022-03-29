#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import collections


PxdData = collections.namedtuple('PxdData', ('Data', 'Custom'))


def read(filename_or_filelike):
    '''
    Returns a PxdData whose Data is a namedtuple or dict or list using
    Python type equivalents to pxd types by parsing the filename_or_filelike
    and whose Custom is the short user string (if any).
    '''


def write(filename_or_filelike, *, data, custom=''):
    '''
    custom is a short user string (with no newlines), e.g., a file
    description.
    data is a tuple or namedtuple or list or dict that this function will
    write to the filename_or_filelike using the strictest typing that is
    valid for pxd.
    '''
