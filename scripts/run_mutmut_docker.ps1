param(
    [string]$ImageName = "pyrigor-mutmut",
    [string[]]$MutmutArgs = @("run")
)

$ErrorActionPreference = "Stop"

$project = (Resolve-Path "$PSScriptRoot\..").Path
$projectForward = $project -replace '\\', '/'

Write-Host "Building mutmut Docker image..."
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker build -t $ImageName -f docker/mutmut.Dockerfile . > $null 2>&1
$imageBuildExit = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

$imageExists = docker images --quiet $ImageName 2> $null
if (-not $imageExists -and $imageBuildExit -ne 0)
{
    throw "Docker build failed with exit code $imageBuildExit"
}

Write-Host "Running mutmut..."
$args = @(
    "run", "--rm",
    "--mount", ("type=bind,source=" + $projectForward + ",target=/project"),
    $ImageName
) + $MutmutArgs

$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = & docker $args 2>&1
$mutmutExit = $LASTEXITCODE
$ErrorActionPreference = $prevErrorAction

Write-Host $output

if ($mutmutExit -ne 0)
{
    Write-Host "Mutmut exited with code $mutmutExit" -ForegroundColor Yellow
}

Write-Host "Cleaning up mutants directory..."
$mutantsPath = Join-Path $project "mutants"
if (Test-Path $mutantsPath)
{
    Remove-Item -Recurse -Force $mutantsPath
}

Write-Host "Mutation testing complete."
