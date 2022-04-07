import pathlib
import re

import setuptools

ROOT = pathlib.Path(__file__).parent

README = (ROOT / 'README.md').read_text()
INIT = (ROOT / 'pxd/__init__.py').read_text()
match = re.search(r"VERSION\s*=\s*(?P<version>\d+\.\d+?)", INIT)
VERSION = match.group('version')

setuptools.setup(
    name='pxd',
    version=VERSION,
    author='Mark Summerfield',
    author_email='mark@qtrac.eu',
    description='A pure Python library supporting pxd, a plain text human readable storage format that may serve as a convenient alternative to csv, ini, json, sqlite, toml, xml, or yaml.',
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
# TODO
        'Topic :: Software Development :: Libraries',
    ],
    packages=['pxd'],
    python_requires='>=3.8',
)
