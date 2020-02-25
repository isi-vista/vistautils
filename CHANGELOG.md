Vistautils 0.20.0 (2020-02-24)
==============================

No significant changes.


Vistautils 0.19.0 (2020-02-05)
==============================

New Features
------------

- Adds a script to turn directories into key-value stores. (`#108 <https://github.com/isi-vista/vistautils/issues/108>`_)
- Adds the ability to specify defaults for many parameter accessors. (`#109 <https://github.com/isi-vista/vistautils/issues/109>`_)
- Added `MemoryAmount` class for representing amounts of memory in user input. (`#110 <https://github.com/isi-vista/vistautils/issues/110>`_)


Vistautils 0.18.0 (2020-01-24)
==============================

New Features
------------

- When configuring logging from parameters, timestamps are now included on logging messages by default. (`#106 <https://github.com/isi-vista/vistautils/issues/106>`_)


Vistautils 0.17.0 (2019-10-30)
==============================

Bugfixes
--------

- Fixes a bug where parameters_only_entry_point with user-supplied parameters would fail if sys.argv did not have length 2 (`#96 <https://github.com/isi-vista/vistautils/issues/96>`_)


Vistautils 0.16.0 (2019-10-11)
==============================

No significant changes.


Vistautils 0.15.0 (2019-10-09)
==============================

New Features
------------

- Added `non_none`, which will filter `None` values out of an iterable (`#90 <https://github.com/isi-vista/vistautils/issues/90>`_)


Vistautils 0.14.0 (2019-10-03)
==============================

New Features
------------

- * added binary key-value sources for doc-id-to-file maps
  * added directory-backed binary sinks
  * supported creating binary sources and sinks from parameters (`#84 <https://github.com/isi-vista/vistautils/issues/84>`_)


Vistautils 0.13.0 (2019-09-30)
==============================

Bugfixes
--------

- Eliminates double-logging when logging is configured from parameters. (`#79 <https://github.com/isi-vista/vistautils/issues/79>`_)
- Fixed incorrect loading of second-level included files for parameters (`#81 <https://github.com/isi-vista/vistautils/issues/81>`_)


New Features
------------

- Added `optional_integer`, `optional_creatable_directory`, `optional_creatable_empty_directory`, `optional_string,` `optional_positive_integer`, `optional_floating_point`, and `optional_float` (`#80 <https://github.com/isi-vista/vistautils/issues/80>`_)


Vistautils 0.12.0 (2019-06-04)
==============================

New Features
------------

- Environmental variables are now interpolated into parameters loaded from YAML by default (`#71 <https://github.com/isi-vista/vistautils/issues/71>`_)


Vistautils 0.11.0 (2019-05-23)
==============================

New Features
------------

- Parameters can now optionally interpolate environmental variables (`#68 <https://github.com/isi-vista/vistautils/issues/68>`_)


Vistautils 0.10.0 (2019-05-21)
==============================

No significant changes.


Vistautils 0.9.0 (2019-02-07)
=============================

New Features
------------

- Distribute type information via PEP 561 (`#45 <https://github.com/isi-vista/vistautils/issues/45>`_)


Vistautils 0.8.1 (2019-02-07)
=============================

Bugfixes
--------

- Update for breaking changes in immutablecollections 0.4.0 (`#42 <https://github.com/isi-vista/vistautils/issues/42>`_)


New Features
------------

- Initial implementation of indexing utility for objects with `Span`s (`#42 <https://github.com/isi-vista/vistautils/issues/42>`_)


Vistautils 0.8.0 (2019-02-04)
=============================

New Features
------------

- Add support for getting the closest set to a given value in a RangeSet
  Add support for getting the value associated to the closest key set with a given value in RangeMap (`#40 <https://github.com/isi-vista/vistautils/issues/40>`_)


Vistautils 0.7.0 (2019-01-10)
=============================

New Features
------------

- Allow specifying limited set of valid options to string() in Parameters (`#33 <https://github.com/isi-vista/vistautils/issues/33>`_)


Vistautils 0.6.0 (2018-11-28)
=============================

New Features
------------

- Added `class_utils.fully_qualified_name` to get class names with their packages and modules. (`#30 <https://github.com/isi-vista/vistautils/issues/30>`_)


Vistautils 0.4.0 (2018-11-01)
=============================

New Features
------------

- Adds `windowed` for iterating over sliding windows over a sequence (`#17 <https://github.com/isi-vista/vistautils/issues/17>`_)
- Adds `optional_existing_file`, `optional_existing_directory` to `Parameters` (`#23 <https://github.com/isi-vista/vistautils/issues/23>`_)


Vistautils 0.3.0 (2018-10-17)
=============================

New Features
------------

- Utility to convert .tar.gz files to .zips. This is useful because the LDC likes to distribute corpora
  as .tar.gz, but it doesn't support random access. (`#14 <https://github.com/isi-vista/vistautils/issues/14>`_)
- Adds convenience entry point for scripts which take only a single parameter file.  In addition to saving the boilerplate of loading parameters, this will also automatically
      configure logging from the param file itself and log the contents of the parameter file. In the future, other such conveniences may be added. (`#15 <https://github.com/isi-vista/vistautils/issues/15>`_)


Vistautils 0.2.1 (2018-10-16)
=============================

Bugfixes
--------

- Fixed crash when a RangeSet was asked for the ranges which enclosed a range greater than any contained range (#10) (`#10 <https://github.com/isi-vista/vistautils/issues/10>`_)


New Features
------------

- Towncrier can now be used to generate a changelog (`#3 <https://github.com/isi-vista/vistautils/issues/3>`_)
