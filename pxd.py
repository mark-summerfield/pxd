#!/usr/bin/env python3
# Copyright © 2022 Mark Summerfield. All rights reserved.
# License: GPLv3

import collections


VERSION = 1.0


class Error(Exception):
    pass


class RecordDef:

    def __init__(self, **kwargs):
        '''
        Each key should be the name of a field and each value one of these
        type objects: none, bool, int, float (for read), datetime.date (for
        date), datetime.datetime (for datetime), str (for text), bytes,
        list, dict, or a custom record, recordlist, or recorddict type.
        '''
        self._kind_for_name = kwargs


    def __getattr__(self, name):
        return self._kind_for_name[name]


    def __setattr__(self, *_):
        raise Error('cannot change a recorddef')


class Record:

    def __init__(self, recorddef, *values):
        self._recorddef = recorddef
        self._data = []
        for (name, kind), value in zip(self._recorddef.items(), values):
            self._data[name] = kind(value)


    def __getattr__(self, name):
        return self._data[name]


    def __setattr__(self, name, value):
        kind = self._recorddef[name]
        self._data[name] = kind(value)


class RecordDict(collections.UserDict):

    def __init__(self, recorddef: RecordDef):
        super().__init__()
        self.recorddef = recorddef


class RecordList(collections.UserList):

    def __init__(self, recorddef: RecordDef):
        super().__init__()
        self.recorddef = recorddef


class Pxd:

    def __init__(self):
        '''
        recorddefs should be None or a list of one or more RecordDefs
        data should be None or a list, dict, RecordList, RecordDict, or
        Record
        '''
        self.recorddefs = None
        self.data = None
