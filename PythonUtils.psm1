<#
.SYNOPSIS
    Module for working with multiple Python environments.
.DESCRIPTION
    Module for working with multiple Python environments.
.EXAMPLE
    PS C:\> <example usage>
    Explanation of what the example does
.INPUTS
    Inputs (if any)
.OUTPUTS
    Output (if any)
.NOTES
    General notes
#>

class PythonVersionInfo {
    [version]$Version;
    [int]$Bit;
    [string]$VersionText;

    PythonVersionInfo([string]$versionInfo) {
        $this.VersionText = $versionInfo
        [regex]$versionRe = [regex]::new("^(?<version>(\d+\.?)*).+?((?<bit>\d+) bit)", [System.Text.RegularExpressions.RegexOptions]::ExplicitCapture)
        $match = $versionRe.Match($versionInfo)
        if (-not $match) {
            throw [System.FormatException]::new($versionInfo)
        }
        $this.Version = New-Object version $match.Groups["version"].Value
        $this.Bit = [int]::Parse($match.Groups["bit"])
    }
}

class PythonExeInfo {
    [System.IO.FileInfo]$Path;
    [version]$Version;
    [int]$Bit;

    PythonExeInfo($path, $version) {
        $this.Path = $path
        $versionInfo = New-Object PythonVersionInfo $version
        $this.Version = $versionInfo.Version
        $this.Bit = $versionInfo.Bit
    }
}

<#
.SYNOPSIS
    Lists the Python executables found on the system.
.DESCRIPTION
    Lists the Python executables found on the system.
.EXAMPLE
    PS C:\> Get-Pythons
    Path                                                                 Version Bit
    ----                                                                 ------- ---
    C:\Python27\ArcGIS10.5\python.exe                                    2.7.13   32
    C:\Python27\ArcGISx6410.5\python.exe                                 2.7.13   64
    C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe 3.5.3    64

.OUTPUTS
    List of objects with the following properties:
    * Path - Path to Python executable
    * Version - Python version number
    * Bit - Integer: either 32 or 64.
.NOTES
    General notes
#>
function Get-Pythons() {
    Write-Host "Searching for Python environments..."
    # The the paths to the python.exe files in expected ArcGIS software installation locations.
    $pythons = (Get-ChildItem -Path "$env:HOMEDRIVE\\Python*\**\python.exe") + (Get-ChildItem -Path "$env:ProgramFiles\ArcGIS\Pro\bin\Python\envs\**\python.exe")
    # Create temporary python code file.
    $tempCommandFile = New-TemporaryFile
    # Create the python command text string.
    $verCommand = [string]::Join([System.Environment]::NewLine, $(
            "from __future__ import print_function, unicode_literals",
            "from sys import version, executable",
            "print('`"%s`", `"%s`"' % (executable, version))"))
    # Write the Python command to the temp script file.
    Write-Output $verCommand | Out-File $tempCommandFile -Encoding utf8

    # Add CSV header
    [string]$versionInfo = "Path,Version"
    # Initialize list of temp files containing version information.
    $versionTempFiles = @()
    $processes = @()
    try {
        foreach ($py in $pythons) {
            # Create a temp. file to write output to and append to list of temp files.
            $tempVersionFile = New-TemporaryFile
            $versionTempFiles += $tempVersionFile
            # Run python script to print version info, redirecting output to the temp file.
            $processes += Start-Process $py $tempCommandFile.FullName -NoNewWindow -PassThru -RedirectStandardOutput $tempVersionFile
        }

        # Wait for all the Python processes to run before attempting to read from the temp files.
        Wait-Process -InputObject $processes

        # Combine the contents of the temp files to the versionInfo string.
        # This string will contain a CSV table.
        foreach ($tempFile in $versionTempFiles) {
            $versionInfo += [System.Environment]::NewLine + (Get-Content -Path $tempFile)
        }
    }
    finally {
        Remove-Item $tempCommandFile
    }

    # Convert the version from CSV to objects, then from generic objects to PythonExeInfo objects.
    return $versionInfo | ConvertFrom-Csv | ForEach-Object {
        New-Object PythonExeInfo @($_.Path, $_.Version)
    }
}


<#
.SYNOPSIS
    Short description
.DESCRIPTION
    Long description
.EXAMPLE
    PS C:\> <example usage>
    Explanation of what the example does
.INPUTS
    Inputs (if any)
.OUTPUTS
    Output (if any)
.NOTES
    General notes
#>
function Get-PythonTool (

    [Parameter(Mandatory, HelpMessage = "Enter tool name")]
    [string]$toolName
) {
    return (Get-ChildItem -Path "$env:HOMEDRIVE\\Python*\**\Scripts\$toolName") + (Get-ChildItem -Path "$env:ProgramFiles\ArcGIS\Pro\bin\Python\envs\*\Scripts\$toolName")
}

class PackageInfo {
    [string]$Package
    [string]$Version
    [System.IO.FileInfo]$PipLocation

    PackageInfo($package, $version, $pip) {
        $this.Package = $package
        $this.Version = $version
        $this.PipLocation = $pip
    }
}

function Get-PythonPackages {
    $pips = Get-PythonTool "pip.exe"
    $output = New-Object [System.Collections.Generic.List[PackageInfo]]
    $originalLocation = Get-Location
    try {
        foreach ($pip in $pips) {
            Set-Location $pip.Directory
            $moduleList = pip list | Select-String -Pattern "^-" -NotMatch | Convert-String -Example "xlwt 1.2.0 =xlwt,1.2.0" | ConvertFrom-Csv
            foreach ($module in $moduleList) {
                $pkInfo = New-Object PackageInfo @($module.Package, $module.Version, $pip)
                $output.Add($pkInfo)
            }
            # $output += $moduleList
        }
    }
    finally {
        Set-Location $originalLocation
    }
    return $output
}

function Install-PythonPackage (
    [Parameter(Mandatory)]
    [string]
    $packageName,
    [switch]
    $User,
    [switch]
    $Editable
) {
    $pips = Get-PythonTool "pip.exe"
    if (-not $pips) {
        Write-Error "Could not find any instances of pip.exe"
    }
    else {
        # $procs = @()
        $procParams = "install"
        if ($Editable) {
            $procParams += " -e"
        }
        $procParams += " $packageName"
        if ($User) {
            $procParams += " --user"
        }
        foreach ($pip in $pips) {
            Write-Host "Installing to $pip..." -ForegroundColor Yellow
            Start-Process $pip $procParams -NoNewWindow -Wait
            # $procs += $p
        }
        # Wait-Process $procs
        # return $procs | ForEach-Object { return $($_.Path, $_.ExitCode) }
    }
}

function Uninstall-PythonPackage (
    [Parameter(Mandatory)]
    [string]
    $packageName) {
    $pips = Get-PythonTool "pip.exe"
    if (-not $pips) {
        Write-Error "Could not find any instances of pip.exe"
    }
    else {
        # $procs = @()
        foreach ($pip in $pips) {
            Start-Process $pip "uninstall $packageName" -NoNewWindow -Wait
            # $procs += $p
        }
        # Wait-Process $procs
        # return $procs | ForEach-Object { return $($_.Path, $_.ExitCode) }
    }
}
