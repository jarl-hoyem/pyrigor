# Manual CLI tests

Run these commands from the repository root with `uv run pyrigor`.
Each command is independent and can be copied directly into PowerShell.

## Clean file

```powershell
uv run pyrigor manual-tests/cli/clean.py
```

Expected output contains:

```text
Checked 1 file in
```

The exit code is `0`.

## Human diagnostics

```powershell
uv run pyrigor manual-tests/cli/violations.py
```

Expected output contains `PYR401`, `PYR402`, and `PYR406`, followed by a
summary showing four violations. The exit code is `1`.

## JSON diagnostics

```powershell
uv run pyrigor --output-format=json manual-tests/cli/violations.py
```

Expected stdout is one JSON document containing diagnostics with codes
`PYR401`, `PYR402`, and `PYR406`. The summary reports four diagnostics.
The exit code is `1`.

## Path exclusion

```powershell
uv run pyrigor --exclude manual-tests/cli/violations.py manual-tests/cli
```

Expected output does not mention `violations.py`, but still reports the
diagnostics from `nested/nested_violations.py` and `unicode.py`. The exit code
is `1`.

```powershell
uv run pyrigor --exclude manual-tests/cli/nested manual-tests/cli
```

Expected output does not mention `nested_violations.py`, but still reports the
diagnostics from `violations.py` and `unicode.py`. The exit code is `1`.

```powershell
uv run pyrigor --exclude manual-tests/cli/violations.py --exclude manual-tests/cli/nested manual-tests/cli
```

Expected output excludes both `violations.py` and
`nested/nested_violations.py`, while still checking the clean, suppressed, and
Unicode fixtures. The Unicode fixture produces one diagnostic, so the exit
code is `1`.

## Suppression

```powershell
uv run pyrigor --output-format=json manual-tests/cli/suppressed.py
```

Expected JSON has an empty `diagnostics` array and a summary containing:

```json
"suppressed": 1,
"suppressed_by_rule": {"PYR402": 1}
```

The exit code is `0`.

## Rule selection and ignoring

```powershell
uv run pyrigor --select=PYR402 manual-tests/cli/violations.py
```

Expected human output contains `PYR402` and does not contain `PYR301` or
`PYR406`. The exit code is `1`.

```powershell
uv run pyrigor --output-format=json --ignore=PYR402 manual-tests/cli/violations.py
```

Expected JSON contains `PYR401` and `PYR406`, but not `PYR402`. The summary
reports three diagnostics, and the exit code is `1`.

```powershell
uv run pyrigor --output-format=json --select=PYR401,PYR402 --ignore=PYR402 manual-tests/cli/violations.py
```

Expected JSON contains only `PYR401`. The exit code is `1`.

## Multiple files and recursive directories

```powershell
uv run pyrigor manual-tests/cli/clean.py manual-tests/cli/violations.py
```

Expected human output reports violations from `violations.py`, confirms that
two files were checked, and exits with `1`.

```powershell
uv run pyrigor --output-format=json manual-tests/cli
```

Expected JSON reports diagnostics from `violations.py` and
`nested/nested_violations.py`, plus the clean and suppressed files. The exit code
is `1`.

## Unicode locations

```powershell
uv run pyrigor --output-format=json manual-tests/cli/unicode.py
```

Expected JSON contains a diagnostic whose location uses character columns
after the non-ASCII text. The exit code is `1`.

## Parse errors

```powershell
powershell -ExecutionPolicy Bypass -File manual-tests/cli/parse-error.ps1
```

Expected stdout is valid JSON with an empty `diagnostics` array and an
error whose kind is `parse_error`. A warning is printed to stderr. The
temporary invalid Python file is removed afterward. The exit code is `0`.

## Empty selection

```powershell
uv run pyrigor --select=PYR402 --ignore=PYR402 manual-tests/cli/violations.py
```

Expected stderr says that `--select` and `--ignore` leave no rules to
check. The exit code is `2`.

## Invalid and repeated arguments

```powershell
uv run pyrigor --output-format=xml manual-tests/cli/clean.py
```

Expected argparse usage output reports an invalid choice. The exit code
is `2`.

```powershell
uv run pyrigor --output-format=json --output-format=human manual-tests/cli/clean.py
```

Expected stderr says `--output-format` can only be given once. The exit
code is `2`.
