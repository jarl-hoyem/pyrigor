"""Shared AST helpers used by more than one pyrigor checker."""

import ast


def is_bare_multi_value_tuple(*, annotation: ast.expr | None) -> bool:
    """Check whether a type annotation is a bare tuple[...] with 2+ elements.

    Args:
        annotation: The annotation to check (a return annotation or a
            parameter annotation), or None.

    Returns:
        True if the annotation is tuple[A, B, ...]. With two or more
        type arguments.
    """
    if not isinstance(annotation, ast.Subscript):
        return False

    if not (isinstance(annotation.value, ast.Name) and annotation.value.id == "tuple"):
        return False

    return isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 2
