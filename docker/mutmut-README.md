# Mutmut Mutation Testing via Docker

Run mutation tests reproducibly in an isolated Docker environment.

## Setup

```powershell
docker build -t pyrigor-mutmut -f docker/mutmut.Dockerfile .
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
.\scripts\run_mutmut_docker.ps1 -MutmutArgs @("run", "pyrigor.checkers.cli.*")
```

## CI Integration

Mutation testing runs automatically in GitHub Actions on every push and pull request to `main`:

- **Job**: `mutation-test` (blocking)
- **Trigger**: Push/PR to `main`, manual trigger via `workflow_dispatch`
- **Environment**: Ubuntu latest (Docker pre-installed)
- **Behavior**: Fails CI when the mutation score drops below the floor in `scripts/check_mutation_score.py`. Timeouts
  are excluded from the score because they track the machine load rather than test quality.

See `.github/workflows/ci.yaml` for the workflow definition.

## Benefits

- Isolated Python/mutmut environment
- No system Python conflicts
- Same reproducible results across machines and CI
- No IDE interference
- Continuous quality validation via GitHub Actions
