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
       read original bytes once, decode UTF-8-sig with universal newlines
       -> build one PositionIndex retaining raw byte offsets
       -> parse once (ast.parse)
       -> walk_once() walks the tree exactly once, producing
          WalkedNodes (function_nodes, assign_nodes,
          call_statement_nodes, class_nodes, parents)
       -> share FindingContext (source, index, file_name, parents)
          and one token stream for signature spans and suppression
       -> every registered checker's find_findings(*, nodes, context)
          runs against those same pre-walked nodes
       -> filter_suppressed() splits results into kept/suppressed,
          based on "# pyrigor CODE # reason" comments above or
          within primary-span lines, excluding function bodies
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
findings.py              (canonical Finding, Span, Fix and PositionIndex;
                           depends only on rules.py)
    ^
finding_builder.py       (FindingContext and make_finding;
                           depends on findings.py + rules.py)
    ^
checkers/_shared.py      (shared traversal and predicate helpers)
    ^
checkers/pyr301_*.py  -+
checkers/pyr401_*.py    |  each depends on _shared.py + rules.py +
checkers/pyr402_*.py    |  findings.py + finding_builder.py,
                      |  never on each other
checkers/pyr403_*.py    |
checkers/pyr405_*.py    |
checkers/pyr406_*.py  -+
    ^
checkers/__init__.py     (aggregates every registered checker into
                           the CHECKERS tuple)

diagnostics.py           (v2 document types and serialisation;
                           depends on findings.py + rules.py)

suppression.py           (depends on findings.py + diagnostics.py;
                           a separate branch of the pipeline)

checkers/cli.py           (top of the graph: imports checkers,
                           checkers._shared, rules, suppression,
                           findings, finding_builder and diagnostics)
```

The individual `pyrXXX` checker modules never importing each other is deliberate, not incidental. A new checker is wired
in by adding one line to `CHECKERS` (see `ADDING_A_RULE.md`), not by any checker knowing about another. This is also why
`checkers/__init__.py`'s `CHECKERS` tuple pairs each `Rule` member with its checker function explicitly by name, rather
than relying on declaration order — see `DECISIONS.md` and `CLAUDE.md` for the positional-coupling bug that motivated
it.

Each finding has a subject-bearing message, one primary span and an enclosing symbol. Function spans cover the signature
through its colon; assignment and call spans cover the statement. The enclosing symbol uses Python's NFKC-normalised
qualified name, or `<module>` at module level. Span columns count Unicode code points in both JSON and human output. Raw
byte offsets preserve BOMs and line endings. Findings currently carry empty fixes. The v2 wrapper includes kept and
suppressed findings, all selected-rule metadata, tool identity, operational errors and a file count.

## Where the "why" lives

This document covers what the system looks like overall. For the reasoning behind a specific structural choice (the
shared walk, explicit checker registration, tokenising-based suppression scanning and more), see `DECISIONS.md`. For the
process of adding a new rule, see `ADDING_A_RULE.md`. For one rule's own scope and rationale, see its own
`guidelines/PYRxxx-*.md` doc.
