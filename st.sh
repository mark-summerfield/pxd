#!/bin/bash
tokei -f -tPython -esetup.py -eepd2pxd.py -eregression.py
unrecognized.py -q
python3 -m flake8 --ignore=W504,E261,E303 .
python3 -m vulture . 
git st
