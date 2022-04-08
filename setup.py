import pathlib
import re

import setuptools

ROOT = pathlib.Path(__file__).parent

README = (ROOT / 'README.md').read_text()
INIT = (ROOT / 'py/pxd.py').read_text()
match = re.search(r"__version__\s*=\s*'(?P<version>.*?)'", INIT)
VERSION = match.group('version')

setuptools.setup(
    name='pxd1',
    version=VERSION,
    author='Mark Summerfield',
    author_email='mark@qtrac.eu',
    description='A pure Python library supporting pxd, a plain text \
human readable storage format that may serve as a convenient \
alternative to csv, ini, json, sqlite, toml, xml, or yaml.',
    long_description=README,
    long_description_content_type='text/markdown',
    url='https://github.com/mark-summerfield/pxd',
    license='GPLv3',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Libraries',
        ],
    package_dir={'': 'py'},
    py_modules=['pxd'],
    scripts=['py/pxdconvert'],
    python_requires='>=3.8',
    )
