rm -rf build/ dist/ pxd.egg-info/
py setup.py sdist bdist_wheel
twine upload dist/* && rm -rf build/ dist/ pxd.egg-info/
