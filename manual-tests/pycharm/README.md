# Manual PyCharm integration tests

This exercise the File Watcher described in the repository README under
"Seeing violations in your editor". Configure it before starting. Every
check is performed by editing a file and watching the Problems view, so
none of them can run in CI.

Fixture names must be unique across every `manual-tests` subfolder. The
folders are not packages, so mypy maps each file to a top-level module and
rejects two of the same name. A file called `clean.py` or `violations.py`
here would collide with the CLI fixtures.

## Why no check expects an empty Problems view

A file with no violations shows nothing. So does a watcher that never ran.
The two are indistinguishable, and that exact confusion hid a broken
`just inspect` behind a green result (#229).

So every check below is either a transition or pairs an expected marker
with an expected absence. Something visible always proves the watcher ran.

## The watcher fires, and labels are not empty

Open `manual-tests/pycharm/watcher.py`, make a trivial edit, and save.

Expected: four problems for this file. Each row begins with a rule code,
such as `PYR406`. A row with a blank label means the output filter lost
`$MESSAGE$`, which happens when the expression matches without capturing.

## The caret lands on the right line and column

Double-click the `PYR406` row naming `apply_correction`.

Expected: the caret sits on the first character of `apply_correction`, not
at the start of the line and not one character to either side. Repeat with
the `discard_result` row, which is one indent level deeper. Both must
land, since a column error shows only at one of the two depths.

## No console window opens

Expected: saving `watcher.py` opens no Run tool window and does not take
focus. This can only fail on a file that has violations because pyrigor
exits 1 whenever it reports anything, so a clean file proves nothing here.

## Markers clear when the violation goes

In `watcher.py`, change `apply_correction(1, 2)` to
`_ = apply_correction(1, 2)` and save. Then undo and save again.

Expected: the count drops to three, then returns to four. The drop is what
proves the watcher ran against the corrected content.

## Suppressed violations do not appear

Open `manual-tests/pycharm/watcher_suppressed.py` and save. Expected: no
problems.

That alone proves nothing, so delete the `# pyrigor PYR402 # manual test`
comment and save again. Expected: one `PYR402` problem appears. Restore the
comment and save. Expected: it goes.

The appearance and disappearance prove both that the watcher ran and that
the suppression comment is what silences it.

## A syntax error produces no spurious problem

In `watcher.py`, delete the colon ending a `def` line and save. Undo
afterwards.

Expected: pyrigor contributes no problem for the file, and no console
appears. It writes a parse-error warning to stderr and exits 0, and the
watcher surfaces neither. PyCharm reports the syntax error itself, which
is the correct source for it. A half-written file is the normal state
during editing, so this path runs constantly in real use.

## Severity is not conveyed, by design

Expected: all four rows in `watcher.py` carry the same icon and weight,
even though `--output-format=json` reports `PYR401` and `PYR402` as
`warning` and both `PYR406` rows as `error`.

This is a known limitation of parsing the text line rather than the JSON,
recorded on #152, not a misconfiguration. When #152 lands, this check
inverts and the rows should differ.

## Not covered

- Columns after non-ASCII text. Every violation pyrigor reports begins a
  statement, so no non-ASCII character ever precedes one on its own line.
  There is no divergence to construct with the current rules.
- Tab indentation, which would show whether PyCharm expands a tab when
  interpreting `$COLUMN$`. A tab-indented file cannot be committed here,
  since `ruff format` rewrites it.
- Files outside the Project Files scope, such as those under `.venv`.
- The four other editors in the repository README. Only PyCharm has been
  exercised.
