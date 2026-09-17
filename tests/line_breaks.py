"""The characters str.splitlines() break a line on and Python's parser does not.

The set is derived from `LINE_BREAK`, the rule pyrigor uses, so it follows any change to that rule instead of
restating it. Every such character is below U+2030.
"""

from pyrigor.findings import LINE_BREAK

_SEARCH_LIMIT = 0x2030

NON_PYTHON_LINE_BREAKS = tuple(
    character
    for character in (chr(code_point) for code_point in range(_SEARCH_LIMIT))
    if len(f"a{character}b".splitlines()) > 1 and not LINE_BREAK.search(character.encode())
)
LINE_BREAK_IDS = tuple(f"U+{ord(character):04X}" for character in NON_PYTHON_LINE_BREAKS)
