* make sure the version number in `vistautils/version.py` matches the desired release version
* run `towncrier` and commit the updated changelog
* be sure `dist` is empty
* `python setup.py sdist bdist_wheel`
* `twine upload dist/*`
