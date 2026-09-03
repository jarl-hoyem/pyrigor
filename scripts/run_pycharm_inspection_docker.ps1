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

# Mask generated and cached directories with empty tmpfs mounts, then scan the
# whole project with a single -d. Repeating -d does not accumulate: pycharm.sh
# inspect keeps only the last one, which is why the previous per-directory
# approach silently analysed a single directory and reported success (#229).
#
# Patterns, not fixed names. The cache directories are variably named
# (.uv-cache-release, .uv-cache-kpi, .codex-uv-cache, .complexipy_cache), and a
# hand-maintained list is exactly what drifts, per #215.
#
# .venv is deliberately absent: .idea/pyrigor@1.iml already excludes it,
# confirmed by it contributing no analysed files in a real run.
$maskPatterns = @('htmlcov', 'dist', 'build', 'mutants', 'node_modules', 'target', '*cache*', '*.egg-info')
$maskedDirs = @()
foreach ($pattern in $maskPatterns)
{
    Get-ChildItem -Path $project -Directory -Force -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object { $maskedDirs += $_.Name }
}

# Masked unconditionally rather than by discovery: this directory is deleted
# above, so nothing would match it here, but Docker recreates it as the bind
# target and PyCharm then analyses the tool's own output.
$maskedDirs += (Split-Path $output -Leaf)
$maskedDirs = $maskedDirs | Select-Object -Unique | Sort-Object

$dockerArgs = @(
    "run", "--rm",
    "--mount", ("type=bind,source=" + $projectForward + ",target=/project"),
    "--mount", ("type=bind,source=" + $outputForward + ",target=/results")
)
foreach ($dir in $maskedDirs)
{
    $dockerArgs += "--mount"
    $dockerArgs += "type=tmpfs,destination=/project/$dir"
}
$dockerArgs += @(
    $ImageName,
    "/opt/pycharm/bin/pycharm.sh", "inspect", "/project", ".idea/inspectionProfiles/Project_Default.xml", "/results",
    "-format", "json", "-v2", "-d", "/project"
)

Write-Host "Masked from analysis: $( $maskedDirs -join ', ' )"

$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$containerOutput = & docker $dockerArgs 2>&1 | Out-String
$inspectionExitCode = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

Set-Content -Path $log -Value $containerOutput -Encoding utf8

if ($inspectionExitCode -ne 0)
{
    Write-Host $containerOutput
    throw "PyCharm inspection failed with exit code $inspectionExitCode. See $log"
}

# Zero findings from a run that analysed almost nothing looks exactly like a
# clean project. That is how #229 stayed hidden. The floor is derived rather
# than chosen: the run must at least have seen pyrigor's own source and tests.
$analysedCount = ([regex]::Matches($containerOutput, '(?m)^Analyzing code in ')).Count
$ownSources = @(Get-ChildItem -Path (Join-Path $project 'pyrigor'), (Join-Path $project 'tests') `
        -Filter '*.py' -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike '*__pycache__*' })
if ($ownSources.Count -eq 0)
{
    throw "Found no Python files under pyrigor/ or tests/, so the coverage floor cannot be established."
}
if ($analysedCount -lt $ownSources.Count)
{
    throw "Only $analysedCount files were analysed, fewer than the $( $ownSources.Count ) Python files in pyrigor/ and tests/. The inspection did not cover the project. See $log"
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
Write-Host "Files analysed: $analysedCount"
Write-Host "Reports: $( $reports.Count )"
Write-Host "Findings: $total"
Write-Host "Output: $output"
Write-Host "Log: $log"
Write-Host ""
Write-Host "Host PyCharm IDE was not affected"
