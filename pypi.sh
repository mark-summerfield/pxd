rm -rf build/ dist/ pxd1.egg-info/
py setup.py sdist bdist_wheel
twine upload dist/* && rm -rf build/ dist/ pxd1.egg-info/
