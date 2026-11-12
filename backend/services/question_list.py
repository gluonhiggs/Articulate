"""Find the interview questions in a plain document a client or coach wrote."""

from __future__ import annotations

import re

MAX_QUESTIONS = 20
MIN_WORDS = 3

# "1.", "1)", "(1)", "Q1:", "Q1.", "-", "*" and the bullet a Word export leaves behind.
_BULLETS = "".join(chr(code) for code in (0x2022, 0x25CF, 0x25AA))
_MARKER_RE = re.compile(r"^\s*(?:\(?\d{1,3}[.)]|[Qq]\d{1,3}[:.)]?|[-*" + _BULLETS + r"])\s+")


def _strip_marker(line: str) -> tuple[str, bool]:
    match = _MARKER_RE.match(line)
    return (line[match.end():].strip(), True) if match else (line.strip(), False)


def _continues(items: list[tuple[str, bool]], line: str) -> bool:
    """
    Whether an unmarked line is the rest of the item above it.

    It is when that item is a numbered question still open, or when the line starts in
    lower case, as a wrapped sentence does. A heading followed by a question is neither,
    so the two stay apart.
    """
    if not items or not items[-1][0] or items[-1][0].endswith("?"):
        return False
    previous_marked = items[-1][1]
    return previous_marked or line[:1].islower()


def find_questions(text: str, limit: int = MAX_QUESTIONS) -> list[str]:
    """
    Each question in *text*, in the coach's own wording and order.

    A question is an item that is numbered or bulleted, or that ends with a question
    mark. An item is a numbered or bulleted line plus the unmarked lines under it, so a
    question wrapped over two lines in a PDF stays one question. Headings and notes,
    which are neither marked nor questions, are dropped, as are exact repeats.
    """
    items: list[tuple[str, bool]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            if items and not items[-1][0]:
                continue
            items.append(("", False))
            continue
        line, marked = _strip_marker(raw_line)
        if not marked and _continues(items, line):
            previous, previous_marked = items[-1]
            items[-1] = (f"{previous} {line}", previous_marked)
        else:
            items.append((line, marked))

    questions: list[str] = []
    for item, marked in items:
        item = " ".join(item.split())
        if len(item.split()) < MIN_WORDS or not (marked or item.endswith("?")):
            continue
        if item not in questions:
            questions.append(item)
        if len(questions) >= limit:
            break
    return questions
