# PyCharm Inspection via Docker

Run PyCharm inspections in an isolated Docker container without affecting your IDE.

## Why Docker?

The native PyCharm CLI inspection approach has fundamental limitations:

- Corrupts project state (interpreter selection, GitHub connection)
- Creates lock file conflicts
- Requires manual recovery after interrupted runs

Docker solves this by running inspection in a completely isolated environment.

## Setup

### 1. Install Docker

Download from <https://www.docker.com/products/docker-desktop>

### 2. Build the image

```powershell
docker build -t pyrigor-pycharm-inspector -f docker/pycharm.Dockerfile docker/
```

This creates an image (approximately 5.4GB, 1.4GB compressed) with PyCharm CLI pre-installed.

### 3. Run inspection

Via justfile (recommended):

```powershell
just inspect
```

Or directly:

```powershell
.\scripts\run_pycharm_inspection_docker.ps1
```

The script automatically:

- Discovers all source directories (excluding .venv, build artifacts, etc.)
- Mounts the project and output directories
- Runs PyCharm inspection with optimal settings
- Parses and reports findings

For manual invocation, see the script source for current PyCharm CLI arguments.

## Benefits

✓ Zero impact on host PyCharm IDE
✓ No config corruption
✓ No lock file conflicts
✓ Repeatable, isolated environment
✓ Can run parallel inspections
✓ No manual recovery needed

## Trade-offs

- Docker must be installed and running
- First run downloads image (1.4GB compressed, expands to approximately 5.4GB)
- Later runs are fast (no download, quick startup)

## Troubleshooting

### "docker: command not found"

- Install Docker Desktop or ensure it's in PATH

### "No such file or directory: .idea/inspectionProfiles/Project_Default.xml"

- Ensure paths use forward slashes inside the container (C:/ not C:\)
- Check volume mount `-v` syntax

### "Out-of-disk space"

- Docker image is approximately 5.4GB (1.4GB compressed)
- Result directory size depends on the project
- Clean Docker cache: `docker builder prune`
- Remove unused images: `docker image prune -a`

## Other Docker tools

See [mutmut-README.md](mutmut-README.md) for mutation testing via Docker.
