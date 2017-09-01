<#
.SYNOPSIS
    Builds the Python Package
#>

foreach ($argumentSet in @("sdist", "bdist_wheel")) {
    Start-Process python "setup.py  $argumentSet" -Wait -NoNewWindow
}

