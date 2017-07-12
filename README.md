wsdot.route module
=================

Python module for locating points or line segments along WSDOT LRS route layers.

Compatibility
-------------

This toolbox is designed to work with ArcGIS Pro (Python 3.X) as well as ArcMap / ArcCatalog (Python 2.X).


Running toolbox from ArcCatalog
-------------------------------

If you want to run the `wsdotroute.pyt` toolbox from ArcCatalog without installing the module (e.g., when you are a developer modifying the code), you will need to do the following to ensure the toolbox can find the `wsdot.route` module.

1. Open the Python Window
2. Type the following in the window (replacing the path given here with the actual path to the `src` folder on your computer)
    ```python
    import sys
    sys.path.append(r'C:\Users\YourUserName\Documents\GitHub\wsdot-route-gp\src')
    ```
3. Open the toolbox file

Notes
-----
Functions are documented using the [Google Python Style Guide] format.

Folder layout is as recommended by ArcGIS Pro documentation: [Extending geoprocessing through Python modules].


[Google Python Style Guide]:https://google.github.io/styleguide/pyguide.html
[Extending geoprocessing through Python modules]:https://pro.arcgis.com/en/pro-app/arcpy/geoprocessing_and_python/extending-geoprocessing-through-python-modules.htm