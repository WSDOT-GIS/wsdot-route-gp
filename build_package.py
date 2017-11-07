"""Builds the Python Package
"""

from __future__ import (
    print_function, unicode_literals, division, absolute_import)
import os
import shutil
from subprocess import run, CalledProcessError


def copy_metadata():
    """
    Copies metadata files from toolboxes folder to help folder

    When geoprocessing toolbox metadata is edited in ArcCatalog or ArcMap,
    the resulting XML files are placed into the same folder as the Python
    Toolbox file. However, the ArcGIS Pro "Extending geoprocessing through
    Python modules" document specifies that this documentation should be
    placed in a different location. This script copies the files from where
    ArcGIS Desktop places the files to the recommended location.

    See https://pro.arcgis.com/en/pro-app/arcpy/geoprocessing_and_python/extending-geoprocessing-through-python-modules.htm
    """

    common_root = os.path.join(os.path.dirname(__file__), "wsdotroute", "esri")
    src = os.path.join(common_root, "toolboxes")
    dest = os.path.join(common_root, "help", "gp", "toolboxes")

    if os.path.exists(dest):
        shutil.rmtree(dest)

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("*.pyt"))

    print("Completed copying metadata XML files")


def main():
    """Builds the distribution files.
    """
    # Packaging tools expects either README.txt, README, or README.rst.
    # Convert the README markdown file to ReStructured text.
    try:
        run("pandoc README.md -f markdown -t rst -o README.rst".split(" "), check=True)
    except CalledProcessError:
        print("pandoc does not appear to be installed. Get it from http://pandoc.org/")
        exit(1)

    copy_metadata()

    for item in ("sdist", "bdist_wheel"):
        run(["python", "setup.py", item], check=True)


if __name__ == '__main__':
    main()
