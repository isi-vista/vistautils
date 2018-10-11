#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

setup(name='vistautils',
      version='0.1.2',
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
          'pyyaml>=3.2'
      ],
      scripts=["scripts/join_key_value_stores.py",
          "scripts/join_binary_key_value_stores.py",
          "scripts/join_character_key_value_stores.py",
          "scripts/split_key_value_store.py"],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
      )
