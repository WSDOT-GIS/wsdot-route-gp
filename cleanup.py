"""Cleans up built files.
"""

from __future__ import absolute_import, division, print_function, unicode_literals
from os import walk, remove
from os.path import abspath, dirname, exists, join
from shutil import rmtree
import re


def main():
    """Removes the following files / directories
    * *.pyc files
    * build,dist, and *.egg-info directories
    * wsdotroute/esri/help directory.
    """
    script_dir = abspath(dirname(__file__))

    for dirpath, dirnames, filenames in walk(script_dir):
        for filename in filter(lambda fn: re.search(r".pyc$", fn, re.I), filenames):
            remove(join(dirpath, filename))

        for directory_name in filter(lambda dn: re.match(r"^((build)|(dist)|(wsdotroute\.egg-info))$", dn, re.I), dirnames):
            rmtree(join(dirpath, directory_name))

    help_dir = join(script_dir, "wsdotroute", "esri", "help")
    if exists(help_dir):
        rmtree(help_dir)


if __name__ == '__main__':
    main()
