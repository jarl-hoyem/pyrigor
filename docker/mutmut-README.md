# Mutmut Mutation Testing via Docker

Run mutation tests reproducibly in an isolated Docker environment.

## Setup

```powershell
docker build -t pyrigor-mutmut -f docker/mutmut.Dockerfile docker/
```

## Run

Via justfile (recommended):

```powershell
just mutmut
```

Or directly:

```powershell
.\scripts\run_mutmut_docker.ps1
```

Custom arguments:

```powershell
.\scripts\run_mutmut_docker.ps1 -MutmutArgs @("run", "--tests", "tests/checkers/")
```

## Benefits

- Isolated Python/mutmut environment
- No system Python conflicts
- Same reproducible results across machines
- No IDE interference
