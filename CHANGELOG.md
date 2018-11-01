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
