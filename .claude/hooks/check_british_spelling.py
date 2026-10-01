"""Block an Edit or Write that introduces American spelling in prose.

A context reminder is not enough: the agent has repeatedly slipped American spelling into prose
despite AGENTS.md's explicit British-spelling rule. This hook makes that a hard gate.

Only newly added lines in Markdown files, Python comments and plain docstring sentences are checked.
A Python identifier that happens to use American spelling ('normalize', serialize, and the like, as
AGENTS.md itself allows) is left alone, since code lines and lines holding Python syntax are not
treated as prose.

Several American/British word pairs are deliberately left out because the American-looking spelling
is also correct British English in ordinary software prose, or is an unrelated word: program (itself
the standard British spelling for a computer program), dialog/analog (both spellings are standard UI
and electronics terminology), check (overwhelmingly a verb/noun with no link to "cheque"),
practice/practise (a noun/verb pair, not a plain misspelling), draft and curb (correct British
spellings for their common senses; only a rarer sense takes "draught"/"kerb"), tire (the "become
tired" verb, spelled the same in both dialects; only the wheel-related "tyre" differs), meter (a
measuring instrument, spelled the same in both dialects; only the unit of length "metre" differs),
license (the same spelling in British English when used as a verb; only the noun is "licence"), and
judgment/acknowledgment, which British English itself accepts alongside the -e- spelling.
"""

from __future__ import annotations

import json
import re
import sys

from hook_shared import added_lines, deny_if, is_within_repo, old_and_new_text, repo_root

_OPEN_PAREN = "("

# Every American spelling in this section is deliberate pattern data, not prose: a detector must
# contain the exact spelling it matches against. Confirmed neither codespell nor
# scripts/check_text_hygiene.py flags it. See DECISIONS.md.
_IZE_PATTERN = re.compile(r"\b[a-z]+iz(?:e|es|ed|ing|ation|ations|er|ers)\b", re.IGNORECASE)
_YZE_PATTERN = re.compile(r"\b[a-z]+yz(?:e|es|ed|ing|ation|ations|er|ers)\b", re.IGNORECASE)
_IZE_EXCEPTIONS = frozenset(
    {
        "size",
        "sizes",
        "sized",
        "sizing",
        "resize",
        "resized",
        "resizes",
        "resizing",
        "downsize",
        "downsized",
        "downsizes",
        "downsizing",
        "capsize",
        "capsized",
        "capsizes",
        "capsizing",
        "prize",
        "prizes",
        "prized",
        "prizing",
        "seize",
        "seizes",
        "seized",
        "seizing",
        "seizure",
        "seizures",
    }
)

# Unambiguous American/British word families in ordinary prose. See the module docstring for the
# families deliberately left out.
_WORD_FAMILIES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcolor(?:s|ed|ing|ful|less)?\b",
        r"\bbehavior(?:s|al|ally)?\b",
        r"\bfavor(?:s|ed|ing|ite|ites|able|ably)?\b",
        r"\bhonor(?:s|ed|ing|able)?\b",
        r"\blabor(?:s|ed|ing)?\b",
        r"\bneighbor(?:s|hood|ing)?\b",
        r"\bcenter(?:s|ed|ing|piece|pieces)?\b",
        r"\bfibers?\b",
        r"\bliters?\b",
        r"\btheaters?\b",
        r"\bdefenses?\b",
        r"\boffenses?\b",
        r"\btravel(?:ed|ing|er|ers)\b",
        r"\bcancel(?:ed|ing|er|ers)\b",
        r"\bmodel(?:ed|ing|er|ers)\b",
        r"\blabel(?:ed|ing|er|ers)\b",
        r"\bsignal(?:ed|ing)\b",
        r"\bfuel(?:ed|ing)\b",
        r"\bdial(?:ed|ing)\b",
        r"\bcounselors?\b",
        r"\bjewelry\b",
        r"\bmold(?:s|ed|ing)?\b",
        r"\bgray(?:s|ish)?\b",
        r"\bsulfur\b",
        r"\bplow(?:s|ed|ing)?\b",
        r"\baluminum\b",
        r"\bspecialt(?:y|ies)\b",
        r"\bskillful(?:ly)?\b",
        r"\bwillful(?:ly)?\b",
        r"\benroll\b",
        r"\bfulfill\b",
    )
)

_CODE_MARKERS = ("def ", "class ", "import ", "return ", "raise ", "= ", "(", ")", "{", "}", "[", "]", "@", "->")
_QUOTE_MARKER_PATTERN = re.compile(r'"""|\'\'\'')

_REPO_ROOT = repo_root(hook_file=__file__)


def _is_prose_line(*, line: str, is_markdown: bool) -> bool:
    """Return whether a line should be checked for American spelling.

    Markdown files are prose throughout. In Python files, only comments and plain docstring
    sentences count; a line holding Python syntax is left alone, since AGENTS.md explicitly allows a
    Python identifier to keep its own spelling.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if is_markdown:
        return True
    return _is_python_prose_line(stripped=stripped)


def _is_python_prose_line(*, stripped: str) -> bool:
    """Return whether a stripped Python source line reads as a comment or a plain docstring sentence."""
    if stripped.startswith("#"):
        return True
    if _QUOTE_MARKER_PATTERN.search(stripped):
        return False
    if any(marker in stripped for marker in _CODE_MARKERS):
        return False
    return bool(re.match(r"^[A-Za-z]", stripped))


def _is_real_hit(*, pattern: re.Pattern[str], word: str, text: str, end: int) -> bool:
    """Return whether one regex match should count as a genuine American-spelling hit."""
    if pattern in (_IZE_PATTERN, _YZE_PATTERN) and word.lower() in _IZE_EXCEPTIONS:
        return False
    return text[end : end + 1] != _OPEN_PAREN


def _spelling_hits(*, line: str) -> list[str]:
    """Return the American-spelling words found in one prose line.

    An inline code span is stripped first, and a match immediately followed by '(' is treated as a
    reference to a real identifier rather than a plain-English word, so neither is flagged.
    """
    text = re.sub(r"`[^`]*`", "", line)
    return [
        match.group()
        for pattern in (_IZE_PATTERN, _YZE_PATTERN, *_WORD_FAMILIES)
        for match in pattern.finditer(text)
        if _is_real_hit(pattern=pattern, word=match.group(), text=text, end=match.end())
    ]


def _deny_reason(*, hits: list[tuple[str, list[str]]]) -> str | None:
    """Return the reason to deny this edit, or None when there is nothing to deny."""
    if not hits:
        return None
    examples = "; ".join(f"{line!r} ({', '.join(words)})" for line, words in hits[:5])
    return (
        f"This edit introduces American spelling in prose: {examples}. "
        "AGENTS.md requires British spelling in prose (a Python identifier keeps its own "
        "spelling, e.g. normalize/serialize as real stdlib or API names; a direct "
        "quotation keeps the source's own spelling too). Rewrite the prose with British "
        "spelling, or if this word is a genuine code identifier reference, keep it as code "
        "or wrap it in backticks."
    )


def _checkable_file_path(*, request: dict[str, object]) -> str | None:
    """Return the file path to check, or None when this request should be left alone entirely."""
    tool_name = request.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return None
    tool_input = request.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    file_path = str(tool_input.get("file_path", ""))
    if not is_within_repo(file_path=file_path, root=_REPO_ROOT):
        return None
    if not file_path.endswith((".md", ".py")):
        return None
    return file_path


def _prose_spelling_hits(*, old_text: str, new_text: str, is_markdown: bool) -> list[tuple[str, list[str]]]:
    """Return each newly added prose line that contains American spelling, with the words found."""
    hits: list[tuple[str, list[str]]] = []
    for line in added_lines(old_text=old_text, new_text=new_text):
        if not _is_prose_line(line=line, is_markdown=is_markdown):
            continue
        words = _spelling_hits(line=line)
        if words:
            hits.append((line.strip(), words))
    return hits


def main() -> None:
    """Check an Edit or Write request and block one that introduces American spelling in prose."""
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    file_path = _checkable_file_path(request=request)
    if file_path is None:
        return

    tool_input = request.get("tool_input", {})
    old_new = old_and_new_text(tool_name=str(request.get("tool_name")), tool_input=tool_input)
    hits = _prose_spelling_hits(old_text=old_new.old, new_text=old_new.new, is_markdown=file_path.endswith(".md"))
    deny_if(reason=_deny_reason(hits=hits))


if __name__ == "__main__":
    main()
