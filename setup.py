# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='syseventd',
    python_requires='>=3.5.0',
    version='0.1.0',
    install_requires=requirements,
    description='A small daemon reacting on input events from OS and keyboard',
    long_description=readme,
    author='Martin Kjaer Joergensen',
    author_email='mkj@gotu.dk',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    entry_points='''
        [console_scripts]
        syseventd=syseventd:main
    ''',
)
