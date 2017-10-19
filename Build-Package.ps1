<#
.SYNOPSIS
    Builds the Python Package
#>

# Packaging tools expects either README.txt, README, or README.rst.
# Convert the README markdown file to ReStructured text.
try {
    pandoc .\README.md -f markdown -t rst -o README.rst
}
catch [System.Management.Automation.CommandNotFoundException] {
    Write-Host "pandoc does not appear to be installed. Get it from http://pandoc.org/" -ForegroundColor Red
    exit 1
}


.\Copy-Metadata.ps1

foreach ($argumentSet in @("sdist", "bdist_wheel")) {
    Start-Process python "setup.py  $argumentSet" -Wait -NoNewWindow
}
