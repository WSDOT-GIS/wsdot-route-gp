<#
.SYNOPSIS
    Builds the Python Package
#>

# Packaging tools expects either README.txt, README, or README.rst.
# Copy the markdown file to one of the expected
$readmeCopy = "README.txt"
Copy-Item .\README.md $readmeCopy

try {
    foreach ($argumentSet in @("sdist", "bdist_wheel")) {
        Start-Process python "setup.py  $argumentSet" -Wait -NoNewWindow
    }
} finally {
    Remove-Item $readmeCopy
}
