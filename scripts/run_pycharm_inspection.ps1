$ErrorActionPreference = "Stop"

$project = (Resolve-Path "$PSScriptRoot\..").Path
$inspectionProfile = Join-Path $project ".idea\inspectionProfiles\Project_Default.xml"
$output = Join-Path (Split-Path $project) "pycharm-inspection-results"
$log = Join-Path (Split-Path $project) "pycharm-inspection.log"
$inspector = "C:\Program Files\JetBrains\PyCharm 2024.3.5\bin\pycharm64.exe"
$normalConfig = Join-Path $env:APPDATA "JetBrains\PyCharm2025.2"
$normalOptions = Join-Path $normalConfig "options"
$optionsBackup = Join-Path $env:TEMP "pyrigor-pycharm-options-$([guid]::NewGuid().ToString('N') )"

if (Get-Process pycharm64 -ErrorAction SilentlyContinue)
{
    throw "Close PyCharm before running the command-line inspector."
}

if (-not (Test-Path $normalOptions))
{
    throw "Cannot protect the PyCharm configuration: $normalOptions does not exist."
}

if (Test-Path $output)
{
    Remove-Item $output -Recurse -Force
}

if (Test-Path $log)
{
    Remove-Item $log -Force
}

$inspectionExitCode = 0
New-Item $output -ItemType Directory -Force | Out-Null
$stdout = New-TemporaryFile
$stderr = New-TemporaryFile
New-Item $optionsBackup -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $normalOptions "*") -Destination $optionsBackup -Recurse -Force
try
{
    $process = Start-Process -FilePath $inspector `
        -ArgumentList @("inspect", $project, $inspectionProfile, $output, "-format", "json", "-v2", "-d", $project) `
        -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdout.FullName `
        -RedirectStandardError $stderr.FullName
}
finally
{
    Remove-Item $normalOptions -Recurse -Force
    Copy-Item (Join-Path $optionsBackup "*") -Destination $normalOptions -Recurse -Force
    Remove-Item $optionsBackup -Recurse -Force
}
Get-Content $stdout.FullName, $stderr.FullName | Add-Content -Path $log -Encoding utf8
Remove-Item $stdout.FullName, $stderr.FullName -Force
$inspectionExitCode = $process.ExitCode

if ($inspectionExitCode -ne 0)
{
    Get-Content $log -Tail 20
    throw "PyCharm inspection failed with exit code $inspectionExitCode."
}

$reports = Get-ChildItem $output -Filter "*.json" -Recurse |
    Where-Object Name -ne ".descriptions.json"

$total = 0
foreach ($report in $reports)
{
    $data = Get-Content $report.FullName -Raw | ConvertFrom-Json
    $total += @($data.problems).Count
}

Write-Host "PyCharm inspection completed."
Write-Host "Reports: $( $reports.Count )"
Write-Host "Findings: $total"
Write-Host "Output: $output"
