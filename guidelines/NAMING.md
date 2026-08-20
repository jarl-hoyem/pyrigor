# Rule naming convention

Every guideline’s filename slug (the part after `PYRxxx-`) is also its
symbolic name — the token used in suppression comments
(`# pyrigor SYMBOLIC-NAME # reason`) and as a `Rule` enum value. This
document is the convention for choosing that slug, so it does not need
re-deciding at every new rule.

## The rule

**Name the mandated pattern or type, not what is banned.** Keep it as
short as possible — "mandated" naming is often shorter than
"banned" naming, since it does not need a `no-`/`not-` qualifier.

```
PYR402-keyword-only-arguments   (mandates keyword-only)
PYR401-namedtuple-returns       (mandates NamedTuple, for returns)
```

## The exception

Add a `-not-X` qualifier only when the mandate-only name would be
genuinely ambiguous about what it is replacing — when the mandated
thing alone does not imply what is wrong.

```
PYR202-enum-not-magic-strings
```

"Enum" alone says nothing about the problem being solved. The
qualifier earns its place here. Contrast with `keyword-only-arguments`,
where "instead of positional" is already implied — no qualifier
needed.

## Family resemblance counts

A name that would be ambiguous in isolation can still work
mandate-only if it clearly belongs to an established family of rules.
`PYR301-namedtuple-values` and `PYR405-namedtuple-parameters` both
lean on `PYR401-namedtuple-returns` already existing — "NamedTuple
for X" reads as an obvious pattern once one member of the family is
established, even though "values" or "parameters" alone would not
necessarily imply "instead of a bare tuple" on their own.

## Why mandate-naming, not just short-naming

This is not purely a style choice — it reflects what pyrigor actually
is meant to do. Every guideline written so far pairs
"here is what is wrong" with
"here is specifically what to do instead," including a worked `# Good`
example. Pyrigor is a prescriptive tool: it does not just flag risky
patterns and leave the fix to the reader, it commits to one specific,
verified answer. Mandate-based naming is honest about that — the name
says what the tool actually tells you to do.

The one legitimate exception: if a future rule has multiple
equally valid fixes depending on context (not one dominant correct
answer), forcing a mandate-name would overclaim certainty the rule
does not have. In that case a more neutral or ban-oriented name is the
honest choice — but that is a property of the rule itself, decided
case by case, not a reason to abandon mandate-naming as the default.

## When adding a new rule

1. Try the mandate-only name first.
2. Ask: does this name, read cold with no other context, imply what
   it is replacing? If yes, done.
3. If genuinely ambiguous and there is no existing family to lean on,
   add a `-not-X` qualifier.
4. Keep it short — this string appears in every suppression comment
   for this rule.

## Enforced automatically

`tests/test_rules_docs_sync.py` checks that every `Rule` enum member
has a matching `guidelines/PYRxxx-<symbolic-name>.md` file — a
mismatch (wrong filename, wrong symbolic name) fails the test suite,
not just a manual review.
