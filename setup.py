#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

from os.path import abspath, dirname, join

with open(join(dirname(abspath(__file__)), 'vistautils', 'version.py')) as version_file:
    exec(compile(version_file.read(), "version.py", 'exec'))

setup(name='vistautils',
      version=version,
      author='Ryan Gabbard <gabbard@isi.edu> and Constantine Lignos <lignos@isi.edu>',
      author_email='gabbard@isi.edu',
      description="Python utilities developed by USC ISI's VISTA center",
      url='https://github.com/isi-vista/vistautils',
      packages=['vistautils'],
      # 3.6 and up, but not Python 4
      python_requires='~=3.6',
      install_requires=[
          'immutablecollections>=0.1.2',
          'attrs>=18.2.0',
          'pyyaml>=3.2',
          'typing_extensions',
          'networkx>=2.2',
      ],
      package_data={'vistautils': ['py.typed']},
      scripts=["scripts/join_key_value_stores.py",
          "scripts/join_binary_key_value_stores.py",
          "scripts/join_character_key_value_stores.py",
          "scripts/split_key_value_store.py",
          "scripts/tar_gz_to_zip.py"],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
      )
