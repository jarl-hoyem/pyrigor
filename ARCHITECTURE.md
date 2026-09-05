# Architecture

`DECISIONS.md` explains individual design decisions and their reasoning. The `ADDING_A_RULE.md` covers the process for
adding one new rule. Individual `guidelines/PYRxxx-*.md` files document one rule's own scope. Nothing shows how the
system fits together at a glance — that is what this document is for. It covers the: _what it looks like overall_,
pointing to `DECISIONS.md` for the: _why_ behind specific choices rather than duplicating that reasoning here.

## Pipeline

```text
CLI entry (run())
  -> collect .py files (recursing directories, skipping excluded ones)
  -> for each file:
       parse once (ast.parse)
       -> walk_once() walks the tree exactly once, producing
          WalkedNodes (function_nodes, assign_nodes,
          call_statement_nodes, class_nodes)
       -> every registered checker's find_violations(*, nodes)
          runs against those same pre-walked nodes
       -> filter_suppressed() splits results into kept/suppressed,
          based on "# pyrigor CODE # reason" comments
  -> aggregate across every file
  -> print summary
```

See `DECISIONS.md`'s "Shared AST walk instead of per-checker walking" entry for why this is a single shared walk rather
than each checker independently walking the tree.

## Module dependency graph

Confirmed directly from the real import statements, not guessed:

```text
rules.py                 (foundation, no internal dependencies)
    ^
violations.py            (depends only on rules.py)
    ^
checkers/_shared.py      (depends on rules.py + violations.py)
    ^
checkers/pyr301_*.py  -+
checkers/pyr401_*.py    |  each depends on _shared.py + rules.py +
checkers/pyr402_*.py    |  violations.py -- never on each other
checkers/pyr403_*.py    |
checkers/pyr405_*.py    |
checkers/pyr406_*.py  -+
    ^
checkers/__init__.py     (aggregates every registered checker into
                           the CHECKERS tuple)

suppression.py           (depends only on violations.py -- a
                           separate branch, not part of the checker
                           chain above)

checkers/cli.py           (top of the graph: imports checkers,
                           checkers._shared, rules, suppression, and
                           violations -- nothing imports from it)
```

The individual `pyrXXX` checker modules never importing each other is deliberate, not incidental. A new checker is wired
in by adding one line to `CHECKERS` (see `ADDING_A_RULE.md`), not by any checker knowing about another. This is also why
`checkers/__init__.py`'s `CHECKERS` tuple pairs each `Rule` member with its checker function explicitly by name, rather
than relying on declaration order — see `DECISIONS.md` and `CLAUDE.md` for the positional-coupling bug that motivated
it.

## Where the "why" lives

This document covers what the system looks like overall. For the reasoning behind a specific structural choice (the
shared walk, explicit checker registration, tokenizing-based suppression scanning, and more), see `DECISIONS.md`. For
the process of adding a new rule, see `ADDING_A_RULE.md`. For one rule's own scope and rationale, see its own
`guidelines/PYRxxx-*.md` doc.
