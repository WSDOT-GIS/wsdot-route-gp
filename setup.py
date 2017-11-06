"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open as codec_open
from os import path

HERE = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with codec_open(path.join(HERE, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='wsdotroute',
    version='2.0.0-beta.5',
    description="Geoprocessing tools for locating along WA LRS",
    long_description=long_description,
    url="https://github.com/WSDOT-GIS/wsdot-route-gp",
    author='WSDOT',
    author_email='WSDOTGISDevelopers@WSDOT.WA.GOV',
    license="Unlicense",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: Public Domain",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities"
    ],
    keywords="WA Washington WSDOT transportation department state linear referencing route",
    packages=find_packages(),
    package_data={'wsdotroute': ['esri/toolboxes/*', 'esri/help/gp/toolboxes/*']}
)
