# pxd

_pxd_ is a plain text human readable storage format that may serve as a
convenient alternative to csv, ini, json, sqlite, toml, xml, or yaml.

## Datatypes

_pxd_ supports eleven datatypes.

|**Type**   |**Example(s) # notes**|
|-----------|----------------------|
|`null`      |`null`|
|`bool`      |`no` `false` `yes` `true`|
|`int`       |`-192` `+234` `7891409`|
|`real`      |`0.15` `0.7e-9` `2245.389` # standard and scientific with at least one digit before and after the point|
|`date`      |`2022-04-01`  # basic ISO8601 YYYY-MM-DD format|
|`datetime`  |`2022-04-01T16:11:51` # ISO8601 (timezone support is library dependent)|
|`str`       |`<Some text which may include newlines>` # using \&lt; for <, \&gt; for >, and \&amp; for &|
|`bytes`     |`(20AC 65 66 48)` # must be even number of case-insensitive hex digits; whitespace optional|
|`list`      |`[value1 value2 ... valueN]`|
|`dict`      |`{key1 value1 key2 value2 ... keyN valueN}`|
|`table`     |`[= <str1> <str2> ... <strN> = <value0`0> ... <value0`N> ... <valueM`0> ... <valueM`N> =]` |

Dictionary keys may only be of types `int`, `date`, `datetime`, `str`,
and `bytes`.

A `table` starts with a table name, then field names, then values. The
number of values in any given row is equal to the number of field names.
(See the examples below).

## Examples

### Minimal empty _pxd_

    pxd 1.0

### CSV to _pxd_

#### CSV

    Date,Price,Quantity,ID,Description
    "2022-09-21",3.99,2,"CH1-A2","Chisels (pair), 1in & 1¼in"
    "2022-10-02",4.49,1,"HV2-K9","Hammer, 2lb"
    "2022-10-02",5.89,1,"SX4-D1","Eversure Sealant, 13-floz"

#### _pxd_ equivalent

The most obvious translation would be to a `list` of ``list``s:

    pxd 1.0 Price List
    [
      [<Price List> <Date> <Price> <Quantity> <ID> <Description>]
      [2022-09-21 3.99 2 <CH1-A2> <Chisels (pair), 1in &amp; 1¼in>]
      [2022-10-02 4.49 1 <HV2-K9> <Hammer, 2lb>]
      [2022-10-02 5.89 1 <SX4-D1> <Eversure Sealant, 13-floz>]
    ]

This is perfectly valid. However, it has the same problem of `.csv` files:
is the first row data values or column titles? (For software this isn't
always obvious, for example, if all the values are strings.) Not to mention
the fact that we have to use a nested `list` of ``list``s.

The most appropriate _pxd_ equivalent is to use a _pxd_ `table`:

    pxd 1.0 Price List
    [= <Price List> <Date> <Price> <Quantity> <ID> <Description> =
      2022-09-21 3.99 2 <CH1-A2> <Chisels (pair), 1in &amp; 1¼in> 
      2022-10-02 4.49 1 <HV2-K9> <Hammer, 2lb> 
      2022-10-02 5.89 1 <SX4-D1> <Eversure Sealant, 13-floz> 
    =]

Notice that the _first_ `table` `str` is the name of the table itself,
with the rest being the field names. Also note that there's no need to
group rows into lines (although doing so is common and easier for human
readability), since the _pxd_ processor will know how many values go
into each row based on the number of field names.

Although a ``table``'s names are ``str``s, it is perfectly possible to
structure the strings to provide extra data for processing applications.
For example:

    pxd 1.0 Price List
    [= <Price List> <Date|type date min 2022-01-01>
       <Price|type money min 0.0 max 9e6> <Quantity|type int min 0 max 9999>
       <ID|type str picture A(2)9-A9> <Description> =
      2022-09-21 3.99 2 <CH1-A2> <Chisels (pair), 1in &amp; 1¼in> 
      2022-10-02 4.49 1 <HV2-K9> <Hammer, 2lb> 
      2022-10-02 5.89 1 <SX4-D1> <Eversure Sealant, 13-floz> 
    =]

Here we've used a pipe (`|`) to separate field names from field
attributes with attributes given as _name value_ pairs. The attributes
are made up and could be anything you like. Here we've indicated the
type of each field and for some a minimum value, for others both minimum
and maximum values, and in one case a COBOL-style picture (meaning two
alphabetic characters followed by a digit then a hyphen then an
alphabetic character then another digit).

Note that if you need to include `&`, `<` or `>` inside a `str`, you
must use the XML/HTML escapes `&amp;`, `&lt;`, and `&gt;` respectively.

### INI to _pxd_

#### INI

    shapename = Hexagon
    zoom = 150
    showtoolbar = False
    [Window]
    x=615
    y=252
    width=592
    height=636
    scale=1.1
    [Files]
    current=test1.pxd
    recent1=/tmp/test2.pxd
    recent2=C:\Users\mark\test3.pxd

#### _pxd_ equivalent

    pxd 1.0 MyApp 1.2.0 Config
    {
      <General> {
        <shapename> <Hexagon>
        <zoom> 150
        <showtoolbar> no
      }
      <Window> {
        <x> 615
        <y> 252
        <width> 592
        <height> 636
        <scale> 1.1
      }
      <Files> [= <Files> <kind> <filename> =
        <current> <test1.pxd> 
        <recent1> </tmp/test2.pxd> 
        <recent2> <C:\Users\mark\test3.pxd> 
      =]
    }

For configuration data it is often convenient to use ``dict``s with name
keys and data values. In this case the overall data is a `dict` which
contains each configuration section. The values of each of the first two of
the ``dict``'s keys are themselves ``dict``s. But for the third key's value
we use a `table`. Notice that we don't have to explicitly distinguish
between one row and the next (although it is common to start new rows on new
lines) since the number of fields (here, two, `kind` and `filename`),
indicate how many values each row has.

Of course, we can nest as deep as we like and mix ``dict``s and ``list``s.
For example, here's an alternative:

    pxd 1.0 MyApp 1.2.0 Config
    {
      <General> {
        <shapename> <Hexagon>
        <zoom> 150
        <showtoolbar> no
        <Files> {
          <current> <test1.pxd>
          <recent> [</tmp/test2.pxd> <C:\Users\mark\test3.pxd>]
        }
      }
      <Window> {
        <x> 615
        <y> 252
        <width> 592
        <height> 636
        <scale> 1.1
      }
    }

Here, we've moved the _Files_ into _General_ and changed the recent
files from per-file `dict` items into a `list` of filenames.

### Database to _pxd_

Data-wise a database normally consists of one or more tables. A _pxd_
equivalent using a `list` of ``tables``s is easily made.

    pxd 1.0 MyApp Data
    [
      [= <Customers> <CID> <Company> <Address> <Contact> <Email> =
        50 <Best People> <123 Somewhere> <John Doe> <j@doe.com> 
        19 <Supersuppliers> null <Jane Doe> <jane@super.com> 
      =]
      [= <Invoices> <INUM> <CID> <Raised Date> <Due Date> <Paid> <Description> =
        152 50 2022-01-17 2022-02-17 no <COD> 
        153 19 2022-01-19 2022-02-19 yes <> 
      =]
      [= <Items> <IID> <INUM> <Delivery Date> <Unit Price> <Quantity> <Description> =
        1839 152 2022-01-16 29.99 2 <Bales of hay> 
        1840 152 2022-01-16 5.98 3 <Straps> 
        1620 153 2022-01-19 11.5 1 <Washers (1-in)> 
      =]
    ]

Here we have a `list` of ``table``s representing three database tables.

Notice that the second customer has a `null` address and the second
invoice has an empty description.

What if we wanted to add some extra configuration data to the database?

One solution would be to make the first item in the `list` a `dict`,
with the remainder ``table``s as now. Another solution would be to use a
`dict` for the container, something like:

    pxd 1.0 MyApp Data
    {
        <config> { <key1> _value1_ ... }
        <tables> [
            _list of tables as above_
        ]
    }

## BNF

A `.pxd` file consists of a mandatory header followed by a single
optional `dict`, `list`, or `table`.

    PXD      ::= 'pxd' RWS REAL CUSTOM? '\n' DATA?
    CUSTOM   ::= RWS [^\n]+ # user-defined data e.g. filetype and version
    DATA     ::= (DICT | LIST | TABLE)
    DICT     ::= '{' OWS (KEY RWS ANYVALUE)? (RWS KEY RWS ANYVALUE)* OWS '}'
    LIST     ::= '[' OWS ANYVALUE? (RWS ANYVALUE)* OWS ']'
    TABLE    ::= '[=' (OWS STR){2,} '=' (RWS VALUE)* '=]'
    KEY      ::= (INT | DATE | DATETIME | STR | BYTES)
    ANYVALUE ::= (VALUE | LIST | DICT | TABLE)
    VALUE    ::= (NULL | BOOL | INT | REAL | DATE | DATETIME | STR | BYTES)
    NULL     ::= 'null'
    BOOL     ::= 'no' | 'false' | 'yes' | 'true'
    INT      ::= /[-+]?\d+/
    REAL     ::= # standard or scientific (but must contain decimal point)
    DATE     ::= /\d\d\d\d-\d\d-\d\d/ # basic ISO8601 YYYY-MM-DD format
    DATETIME ::= /\d\d\d\d-\d\d-\d\dT\d\d:\d\d(:\d\d)?(Z|[-+]\d\d(:?[:]?\d\d)?)?/ # see note below
    STR      ::= /[<][^<>]*[>]/ # newlines allowed, and &amp; &lt; &gt; supported i.e., XML
    BYTES    ::= '(' (OWS [A-Fa-f0-9]{2})* OWS ')'
    OWS      ::= /[\s\n]*/
    RWS      ::= /[\s\n]+/ # in some cases RWS is actually optional

For a `table` the first `str` is the table's name and the second and
subsequent strings are field names. After the bare `=` come the table's
values. There's no need to distinguish between one row and the next
(although it is common to start new rows on new lines) since the number
of fields indicate how many values each row has.

As the BNF shows, `dict` values and `list` items may be of _any_ type.

However, table values may only be scalars (i.e., of type `null`, `bool`,
`int`, `real`, `date`, `datetime`, `str`, or `bytes`), not ``dict``s,
``list``s, or ``table``s.

For ``datetime``s, support may vary across different _pxd_ libraries and
might _not_ include timezone support. For example, the Python library
only supports timezones as time offsets; for `Z` etc, the `dateutil`
module must be installed, but even that doesn't necessarily support the full
ISO8601 specification.

Note that a _pxd_ reader must be able to read a plain text or gzipped plain
text `.pxd` file containing UTF-8 encoded text. Note also that pxd readers
and writers should not care about the actual file extension since users are
free to use their own.

![pxd logo](pxd.svg)
