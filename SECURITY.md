# Security Policy

## Tool pyrigor — Python Coding-Discipline Guideline Collection & Linter

This is a small, part-time personal project. Reports are handled in good faith and on a best-effort basis. Please read
this document before reporting.

---

## Supported Versions

Only the latest tagged release is supported. The `main` branch is a work in progress and not eligible for reports.

---

## Scope

### In scope

- Incorrect or unsafe behaviour in pyrigor’s checkers (false negatives that miss a documented rule, false positives that
  flag correct code)
- Any code path where running pyrigor against untrusted source files could execute arbitrary code (relevant once the
  AST-based checker/pylint plugin stages exist)
- Dependency vulnerabilities (in `pyproject.toml`/`uv.lock`)
- Packaging and release pipeline issues
- Reproducibility issues across supported Python versions/OSes

### Out of scope

- The GitHub platform itself
- Third-party tools pyrigor wraps or integrates with (mypy, pyright, ty, ruff, pylint) — report those upstream.
- Feature requests framed as bugs
- Performance optimisation suggestions
- Theoretical or unproven issues without a reproducer
- Issues found by automated scanners run without prior permission

---

## How to Report

### Security-sensitive issues

Use GitHub’s built-in private disclosure: **Security → Report a vulnerability** (top of the repository page).

### Non-security bugs

Open a regular GitHub Issue.

### What to include

1. **A minimal reproducer** — the smallest Python snippet that demonstrates the issue against a specific tagged version
   of pyrigor.
2. **Expected behaviour** — what pyrigor should do, with a reference to the relevant `PYRxxx` guideline if applicable.
3. **Actual behaviour** — what pyrigor does instead.
4. **Environment details** — Python version, OS, pyrigor version.

Reports without a working reproducer may not be considered.

---

## Timelines

This is a part-time personal project. Please set expectations accordingly.

| Milestone                                     | Target                |
| --------------------------------------------- | --------------------- |
| Initial acknowledgement                       | 30 days               |
| Triage decision (valid / invalid / duplicate) | 90 days               |
| Fix or published workaround                   | 180 days              |
| Public disclosure (security issues)           | After fix is released |

If a milestone is missed, feel free to send a polite follow-up on the issue or advisory thread.

**Please do not disclose security-sensitive findings publicly before a fix is released.**

---

## Pull Request Review Process

PRs are reviewed on a best-effort basis. Expect the same timelines as bug reports. A fix PR should reference the
original issue. The maintainer may rewrite or close PRs without notice.

---

## Rules

- This policy is not a legal contract. It operates entirely on mutual good faith.
- The maintainer reserves the right to adjust this policy or its scope at any time, with a notice posted in this file.
- By participating you agree not to exploit any vulnerability beyond what is strictly necessary to demonstrate it.
- Valid reporters are credited by name (or handle) in the changelog and release notes, unless they request otherwise.

---

## Contribution Policy

- **No malicious contributions.** Any PR introducing intentional vulnerabilities, backdoors, or sabotage will be
  rejected and reported.
