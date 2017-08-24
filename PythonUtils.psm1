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

    [Parameter(Mandatory,HelpMessage="Enter tool name")]
    [string]$toolName
) {
    return (Get-ChildItem -Path "$env:HOMEDRIVE\\Python*\**\Scripts\$toolName") + (Get-ChildItem -Path "$env:ProgramFiles\ArcGIS\Pro\bin\Python\envs\*\Scripts\$toolName")
}

class PackageInfo {
    [string]$Package
    [string]$Version
    [System.IO.FileInfo]$PipLocation

    PackageInfo($package,$version,$pip) {
        $this.Package = $package
        $this.Version = $version
        $this.PipLocation = $pip
    }
}

function Get-PythonPackages {
    $pips = Get-PythonTool "pip.exe"
    $output = @()
    $originalLocation = Get-Location
    try {
        foreach ($pip in $pips) {
            Set-Location $pip.Directory
            $moduleList = pip list | Select-String -Pattern "^-" -NotMatch |  Convert-String -Example "xlwt 1.2.0=xlwt,1.2.0" | ConvertFrom-Csv | ForEach-Object {
                return New-Object PackageInfo -ArgumentList $_.Package,$_.Version,$pip
            }
            $output += $moduleList
        }
    } finally {
        Set-Location $originalLocation
    }
    return $output
}

function Install-PythonPackage (
    [Parameter(Mandatory)]
    [string]
    $packageName) {
    $pips = Get-PythonTool "pip.exe"
    if (-not $pips) {
        Write-Error "Could not find any instances of pip.exe"
    } else {
        # $procs = @()
        foreach ($pip in $pips) {
            Start-Process $pip "install $packageName --user" -NoNewWindow -Wait
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
    } else {
        # $procs = @()
        foreach ($pip in $pips) {
            Start-Process $pip "uninstall $packageName --user" -NoNewWindow -Wait
            # $procs += $p
        }
        # Wait-Process $procs
        # return $procs | ForEach-Object { return $($_.Path, $_.ExitCode) }
    }
}