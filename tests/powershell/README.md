# PowerShell Tests

## Manual Testing

The PowerShell script `scripts/run_pycharm_inspection_docker.ps1` should be tested manually to verify:

**Script runs successfully:**

```powershell
cd C:\Users\jarl\smallgig\pyrigor
.\scripts\run_pycharm_inspection_docker.ps1
```

**Verify output:**

- Script completes without errors
- Output directory created: `C:\Users\jarl\smallgig\pycharm-inspection-results`
- JSON reports generated with violations found
- Message: "Host PyCharm IDE was not affected"

**Verify Docker integration:**

- Docker image builds (if not already cached)
- Source directories are discovered automatically
- `.venv` excluded from scanning
- All findings parsed correctly

## Automated Testing

Full Pester test suite is complex due to Docker mocking requirements. Manual testing is enough for validating the
script's core functionality.

## Future Work

- Consider refactoring the script for better testability
- Add Pester unit tests with proper mocking
- Integration tests with real Docker
