<#
.SYNOPSIS
    Runs Pylint on *.py and *.pyt files.
.DESCRIPTION
    Runs Pylint on *.py and *.pyt files.
.OUTPUTS
    Table of Pylint result messages, grouped by module / filename.
.NOTES
    The reason for this script is that Pylint will not automatically recognize *.pyt files as Python scripts and will skip them.
    This script explicitly states the list of files.
.EXAMPLE
    .\Run-Pylint.ps1 | Format-Table -GroupBy module  -Property path,line,column,type,symbol,message
    Displays output in tables grouped by module
#>

<#
Pylint should leave with following status code:
* 0 if everything went fine
* 1 if a fatal message was issued
* 2 if an error message was issued
* 4 if a warning message was issued
* 8 if a refactor message was issued
* 16 if a convention message was issued
* 32 on usage error
status 1 to 16 will be bit-ORed so you can know which different
categories has been issued by analysing pylint output status code
#>
[Flags()] enum StatusCodes {
    OK = 0
    FatalMessage = 1
    ErrorMessage = 2
    WarningMessage = 4
    RefactorMessage = 8
    ConventionMessage = 16
    UsageError = 32
}

<#
.SYNOPSIS
    Gets a list of Python file paths
.DESCRIPTION
    Long description
.OUTPUTS
    List of relative Python script file paths
#>
function GetPythonFiles () {
    # Get list of files
    $pyscripts = Get-ChildItem "src" -Recurse -Include *.py, *.pyt -Exclude "test*"
    # Make them relative paths
    $currentFolder = [System.IO.Path]::GetFullPath(".")
    $pyscripts = $pyscripts | ForEach-Object {
        return $_.ToString().Replace($currentFolder, "").TrimStart('\', '/')
    }
    return $pyscripts
}

class PyLintMessage {
    [string]$path
    [int]$line
    [string]$module
    [string]$obj
    [string]$message
    [int]$column
    [string]$type
    [string]$symbol
}

$fileList = [string]::Join(" ", (GetPythonFiles))

[PyLintMessage[]]$output = $null

try {
    $tempfile = New-TemporaryFile

    Write-Host "Running pylint on $fileList..."

    # Start the Pylint process and wait
    $process = Start-Process pylint ($fileList + " --output-format=json") -PassThru -NoNewWindow -RedirectStandardOutput $tempfile

    Wait-Process -InputObject $process

    # Get the exit code
    [StatusCodes]$exitcode = $process.ExitCode

    # Write an error if exit code was due to Usage Error.
    # Otherwise, convert the output into objects.
    if ($exitcode -eq [StatusCodes]::UsageError) {
        Write-Error Get-Content $tempfile
    }
    else {
        Write-Host "Completed running PyLint"
        Get-Content $tempfile | ConvertFrom-Json | Sort-Object module, path | Format-Table -GroupBy path -Property line,column,type,symbol,message
    }
}
catch [System.InvalidOperationException] {
    Write-Host "Error running pylint. Is it installed?" -ForegroundColor Red
    pip list pylint | Select-String -NotMatch "^-" | Convert-String -Example "abc 1.2.3=abc,1.2.3" | ConvertFrom-Csv | Where-Object { $_.Package -eq "pylint" }
}
finally {
    if (Resolve-Path $tempfile -ErrorAction Ignore) {
        Remove-Item $tempfile
    }
}


