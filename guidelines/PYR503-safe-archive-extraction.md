# PYR503 — Verify extracted archive members stay within the target directory

## Rule

When extracting a `tarfile`/`zipfile` archive, verify each member's resolved path stays within the intended extraction
directory before writing it, or use `tarfile.extractall`'s own `filter="data"` argument where it applies.

```python
# Bad
with tarfile.open("upload.tar") as tar:
    tar.extractall("/safe/output/dir")

# Good
with tarfile.open("upload.tar") as tar:
    tar.extractall("/safe/output/dir", filter="data")
```

## Rationale

A crafted archive can contain a member path like `../../etc/passwd` or an absolute path. A naive `extractall()` call
writes it there directly, escaping the intended output directory entirely, a real, well-documented vulnerability class
("Zip Slip") that has affected many real, production projects. The code type-checks and runs cleanly. Nothing about it
looks wrong until a malicious archive is actually extracted.

## Detection scope

PYR503 detects direct `extractall()` calls on recognized `tarfile` and `zipfile` objects.

Recognised forms include:

- `import tarfile`
- `import tarfile as tf`
- `from tarfile import TarFile`
- `import zipfile`
- `import zipfile as zf`
- `from zipfile import ZipFile`

Straightforward import aliases may be recognised.

The checker does not perform general type inference, interprocedural analysis, or data-flow analysis. Unknown objects
such as `archive.extractall(...)` are therefore ignored.

For `tarfile`, `filter="data"` is recognised as safe.

For `zipfile`, an explicit path-validation pattern may be recognised when the validation is directly visible in the same
function. Beyond that, pyrigor does not attempt to prove arbitrary helper functions or external validation code safe.

The checker does not attempt to determine whether an archive is trustworthy. Trusted archives may therefore still
produce a finding and can use the normal pyrigor suppression mechanism.

The checker does not flag `extract()`, custom extraction functions, or unknown objects calling `extractall()`.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** For `tarfile`, adding `filter="data"` (available on Python 3.12+, and backported to 3.11.4+, 3.10.12+,
3.9.17+, 3.8.17+) is close to mechanically safe. For `zipfile`, no equivalent built-in filter exists. The real fix
requires custom path-resolution validation, genuine, context-dependent code the tool cannot construct confidently. Given
the two archive types need different real fixes, this sits at `suggestion`, not `safe_fix`, for the rule.

## Severity

**Level:** `error`

**Reasoning:** A real, confirmed vulnerability class (Zip Slip), not just a code-quality concern. See `DECISIONS.md`'s
"Severity" entry for the full per-rule reasoning.

## When this does not apply

- Extracting an archive whose contents are fully, verifiably trusted (built by the same pipeline, never accepting user
  upload).
- Any call already validated by an equivalent, explicit path check performed elsewhere in the same function.

## Related

None yet.

## Enforced by

Not yet implemented.
