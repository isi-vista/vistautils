#!/usr/bin/env python

from distutils.core import setup
from os.path import abspath, dirname, join

from setuptools import find_packages

with open(join(dirname(abspath(__file__)), 'vistautils', 'version.py')) as version_file:
    exec(compile(version_file.read(), "version.py", 'exec'))

setup(name='vistautils',
      version=version,
      author='Ryan Gabbard <gabbard@isi.edu> and Constantine Lignos <lignos@isi.edu>',
      author_email='gabbard@isi.edu',
      description="Python utilities developed by USC ISI's VISTA center",
      url='https://github.com/isi-vista/vistautils',
      packages=['vistautils', 'vistautils.scripts'],
      # 3.8 and up, but not Python 4
      python_requires='~=3.8',
      install_requires=[
          'immutablecollections>=0.12.0',
          'attrs>=21.4.0',
          'PyYAML>=6.0',
          'types-PyYAML==6.0.8',
          'typing_extensions',
          'sortedcontainers>=2.4.0',
          'deprecation>=2.1.0'
      ],
      package_data={'vistautils': ['py.typed']},
    scripts=["vistautils/scripts/join_key_value_stores.py",
          "vistautils/scripts/split_key_value_store.py",
          "vistautils/scripts/tar_gz_to_zip.py",
             "vistautils/scripts/downsample_key_value_store.py"],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
      )
