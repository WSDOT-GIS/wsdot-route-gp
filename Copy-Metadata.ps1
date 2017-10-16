<#
.SYNOPSIS
    Copies metadata files from toolboxes folder to help folder
.DESCRIPTION
    When geoprocessing toolbox metadata is edited in ArcCatalog or ArcMap,
    the resulting XML files are placed into the same folder as the Python
    Toolbox file. However, the ArcGIS Pro "Extending geoprocessing through
    Python modules" document specifies that this documentation should be
    placed in a different location. This script copies the files from where
    ArcGIS Desktop places the files to the recommended location.
.NOTES
    See https://pro.arcgis.com/en/pro-app/arcpy/geoprocessing_and_python/extending-geoprocessing-through-python-modules.htm
#>

$commonRoot = ".\src\wsdotroute\esri"
$src = "$commonRoot\toolboxes"
$dest = "$commonRoot\help\gp\toolboxes"
Write-Host "Copying metadata files"
if (-not (Resolve-Path $dest -ErrorAction Ignore)) {
    Write-Host "Creating output directory"
    New-Item $dest -ItemType Directory
}
Get-ChildItem "$src\*.xml" | Copy-Item -Destination $dest
Write-Host "Completed copying metadata XML files" -ForegroundColor Green
