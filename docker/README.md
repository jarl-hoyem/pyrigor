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
docker build -t pyrigor-pycharm-inspector docker/
```

This creates a lightweight image (~1.5GB) with PyCharm CLI pre-installed.

### 3. Run inspection

```powershell
.\scripts\run_pycharm_inspection_docker.ps1
```

Or manually:

```powershell
docker run --rm `
  -v "C:\path\to\project:C:/project" `
  -v "C:\path\to\results:C:/results" `
  pyrigor-pycharm-inspector `
  inspect C:/project ".idea/inspectionProfiles/Project_Default.xml" "C:/results" `
  -format json -v2 -d "C:/project"
```

## Benefits

✓ Zero impact on host PyCharm IDE
✓ No config corruption
✓ No lock file conflicts
✓ Repeatable, isolated environment
✓ Can run parallel inspections
✓ No manual recovery needed

## Trade-offs

- Docker must be installed and running
- Slower first run (image download ~800MB, extraction ~700MB)
- Later runs are fast (~5–10 seconds overhead)

## Troubleshooting

### "docker: command not found"

- Install Docker Desktop or ensure it's in PATH

### "No such file or directory: .idea/inspectionProfiles/Project_Default.xml"

- Ensure paths use forward slashes inside the container (C:/ not C:\)
- Check volume mount `-v` syntax

### "Out-of-disk space"

- Docker image is ~1.5GB
- Result directory size depends on the project
- Clean with `docker image prune -a` if needed
