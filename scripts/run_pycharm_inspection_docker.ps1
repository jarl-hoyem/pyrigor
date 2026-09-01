param(
    [string]$ImageName = "pyrigor-pycharm-inspector"
)

<#
.DESCRIPTION
PyCharm CLI inspection runner using Docker isolation.

ADVANTAGES:
- Zero impact on host PyCharm IDE or config
- No lock file conflicts
- Repeatable, isolated environment
- No manual recovery needed

REQUIREMENTS:
- Docker installed and running
- Image built: docker build -t pyrigor-pycharm-inspector docker/
#>

$ErrorActionPreference = "Stop"

$project = (Resolve-Path "$PSScriptRoot\..").Path
$inspectionProfile = Join-Path $project ".idea\inspectionProfiles\Project_Default.xml"
$output = Join-Path $project ".pycharm-inspection-results"
$log = Join-Path $project ".pycharm-inspection.log"

if (-not (Test-Path $inspectionProfile))
{
    throw "Inspection profile not found: $inspectionProfile"
}

if (Test-Path $output)
{
    Remove-Item $output -Recurse -Force
}

if (Test-Path $log)
{
    Remove-Item $log -Force
}

Write-Host "Building Docker image if needed..."
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker build -t $ImageName -f docker/pycharm.Dockerfile docker/ > $null 2>&1
$imageBuildExit = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

# Verify image exists (docker build writes to stderr even on success)
$imageExists = docker images --quiet $ImageName 2> $null
if (-not $imageExists -and $imageBuildExit -ne 0)
{
    throw "Docker build failed with exit code $imageBuildExit"
}

Write-Host "Running PyCharm inspection in Docker..."
$projectForward = $project -replace '\\', '/'
$outputForward = $output -replace '\\', '/'

# Generate source directory list dynamically from .py file locations
$exclusions = @('.venv', 'htmlcov', '.git', '__pycache__', '.pytest_cache', '.egg-info', 'node_modules', '.mypy_cache', '.ruff_cache', 'dist', 'build', 'mutants')
$sourceDirs = @()
Get-ChildItem -Path $project -Filter "*.py" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $dir = Split-Path $_.FullName
    $excluded = $false
    foreach ($exclusion in $exclusions)
    {
        if ($dir -like "*$exclusion*")
        {
            $excluded = $true
            break
        }
    }
    if (-not $excluded)
    {
        $sourceDirs += $dir
    }
}
$sourceDirs = $sourceDirs | Select-Object -Unique | Sort-Object

if ($sourceDirs.Count -eq 0)
{
    Write-Host "Warning: No source directories found. Scanning entire project."
    $scanDirs = @("/project")
}
else
{
    $scanDirs = @()
    foreach ($dir in $sourceDirs)
    {
        $dirForward = $dir -replace '\\', '/'
        $relDir = $dirForward -replace [regex]::Escape($projectForward), '/project'
        $scanDirs += $relDir
    }
}

$args = @(
    "run", "--rm",
    "--mount", ("type=bind,source=" + $projectForward + ",target=/project"),
    "--mount", ("type=bind,source=" + $outputForward + ",target=/results"),
    "--mount", "type=tmpfs,destination=/project/mutants",
    $ImageName,
    "/opt/pycharm/bin/pycharm.sh", "inspect", "/project", ".idea/inspectionProfiles/Project_Default.xml", "/results",
    "-format", "json", "-v2"
)

# Add discovered directories
foreach ($dir in $scanDirs)
{
    $args += "-d"
    $args += $dir
}
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$containerOutput = & docker $args 2>&1
$inspectionExitCode = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

if ($inspectionExitCode -ne 0)
{
    Write-Host $containerOutput
    throw "PyCharm inspection failed with exit code $inspectionExitCode"
}

# Parse results
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
Write-Host ""
Write-Host "Host PyCharm IDE was not affected"
