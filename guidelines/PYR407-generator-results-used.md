# PYR407 — Use every locally defined generator function’s result

## Rule

A function defined within the codebase being checked, annotated to return `Iterator[X]`, `Generator[X, Y, Z]`, or
`AsyncGenerator[X, Y]`, must have its result used at every call site. Calling it as a bare expression statement and
discarding the result is a violation.

```python
def process_items(items: list[Item]) -> Iterator[Result]:
    for item in items:
        yield transform(item)


# Bad
process_items(items)

# Good
results = list(process_items(items))
```

Same structural, no-decorator design as PYR406, matching every other enforced pyrigor rule.

## Rationale

Calling a generator function and discarding the result is a distinct, and arguably worse, failure mode than discarding a
normal return value. Calling `process_items(items)` creates a generator object and runs none of the function’s body at
all, `yield` never executes until something iterates the result. The call looks identical to a real, working call at the
source level, produces no error, and silently does nothing.

```python
def log_and_yield_results(items: list[Item]) -> Iterator[Result]:
    for item in items:
        logger.info("processing %s", item)
        yield transform(item)


def handle_request(items: list[Item]) -> None:
    log_and_yield_results(items)  # bug: nothing runs at all, no logging, no transforms
```

This is exactly the case PYR406’s own guideline doc identified and deliberately carved out as separate territory,
discarding a normal return value wastes real, already-computed work, discarding a generator call means the work never
happened.

## Fix classification

**Kind:** `guidance`

**Reasoning:** The same reasoning as [PYR406](./PYR406-return-values-used.md): the right fix depends entirely on
developer intent the tool cannot know. Per #105's own adopted classification.

## Severity

**Level:** `error`

**Reasoning:** Worse than [PYR406](./PYR406-return-values-used.md)'s own case — discarding a generator call means the
work never happened at all, not merely computed and thrown away.

## Scope, matching PYR406's own boundaries

- Only functions defined within the codebase pyrigor are checking.
- A function annotated `-> NoReturn` or `-> Never` is excluded automatically (though a generator function cannot be
  annotated this way).

## When this does not apply

- A genuinely legitimate discard, calling a generator purely to trigger a side effect on the first iteration step during
  construction (rare, and usually a sign the function should not be a generator at all). Use a suppression comment,
  `# pyrigor 407 # reason`, rather than expecting the rule to infer the exception automatically.
- Any call into code outside the project being checked.

## Related

PYR406, the sibling rule for non-generator functions. See PYR406’s own guideline doc for why the two are separate rules
rather than one combined rule.

## Enforced by

Not yet implemented.
