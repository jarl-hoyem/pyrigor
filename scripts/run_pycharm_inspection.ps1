$ErrorActionPreference = "Stop"

$project = (Resolve-Path "$PSScriptRoot\..").Path
$inspectionProfile = Join-Path $project ".idea\inspectionProfiles\Project_Default.xml"
$output = Join-Path (Split-Path $project) "pycharm-inspection-results"
$log = Join-Path (Split-Path $project) "pycharm-inspection.log"
$inspector = "C:\Program Files\JetBrains\PyCharm 2024.3.5\bin\pycharm64.exe"

if (Get-Process pycharm64 -ErrorAction SilentlyContinue)
{
    throw "Close PyCharm before running the command-line inspector."
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
$process = Start-Process -FilePath $inspector `
    -ArgumentList @("inspect", $project, $inspectionProfile, $output, "-format", "json", "-v2", "-d", $project) `
    -Wait -PassThru -NoNewWindow `
    -RedirectStandardOutput $stdout.FullName `
    -RedirectStandardError $stderr.FullName
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
