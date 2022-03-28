#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3


def read(filename_or_filelike):
    '''
    Returns a namedtuple or dict or list using Python type equivalents to
    pxd types by parsing the filename_or_filelike.
    '''


def write(filename_or_filelike, data):
    '''
    data is a tuple or namedtuple or list or dict that this function will
    write to the filename_or_filelike using the strictest typing that is
    valid for pxd.
    '''
