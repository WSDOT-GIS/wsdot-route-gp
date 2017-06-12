"""For use with python packaging tools.
"""
from distutils.core import setup

setup(
    name='wsdotroute',
    version='1.0',
    packages=['wsdotroute'],
    package_dir={'wsdotroute': 'wsdotroute'},
    package_data={'wsdotroute': ['esri/toolboxes/*.*']}
)
