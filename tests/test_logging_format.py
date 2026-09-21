"""Every logger call must pass exactly as many arguments as its format string consumes.

A mismatch is invisible until the line actually runs, when logging prints
"--- Logging error ---" instead of the message you needed.
"""

from __future__ import annotations

import ast
import re
import warnings

import pytest

from backend.constants import PROJECT_ROOT

BACKEND = PROJECT_ROOT / "backend"
LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}
# %(name)s style is keyword-based, %% is an escaped percent; neither consumes an argument.
PLACEHOLDER = re.compile(r"%(?:\((?P<key>[^)]*)\))?[-+ #0]*[\d*]*(?:\.[\d*]*)?[hlL]?(?P<kind>[a-zA-Z%])")


def _format_string(node: ast.Call) -> str | None:
    """The literal format string of a logger call, or None when it is not a plain literal."""
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):  # f-string: it formats itself, so it takes no args
        return None
    return None


def _expected_args(fmt: str) -> int:
    count = 0
    for match in PLACEHOLDER.finditer(fmt):
        if match.group("kind") == "%":
            continue
        if match.group("key") is not None:
            return -1  # mapping style takes a single dict argument
        count += 1
        count += match.group(0).count("*")
    return count


def _logger_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in LEVELS:
            continue
        target = node.func.value
        name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
        if name not in {"logger", "logging", "log"}:
            continue
        yield node


@pytest.mark.parametrize("path", sorted(BACKEND.rglob("*.py")), ids=lambda p: str(p.relative_to(BACKEND)))
def test_logger_arguments_match_the_format_string(path) -> None:
    with warnings.catch_warnings():
        # Unrelated escape-sequence warnings from the parsed sources are not this test's business.
        warnings.simplefilter("ignore", DeprecationWarning)
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(path.read_text(encoding="utf-8"))
    problems = []
    for call in _logger_calls(tree):
        fmt = _format_string(call)
        if fmt is None:
            continue
        expected = _expected_args(fmt)
        if expected < 0:
            continue
        supplied = len(call.args) - 1
        if any(isinstance(arg, ast.Starred) for arg in call.args):
            continue
        if supplied != expected:
            problems.append(f"line {call.lineno}: format wants {expected} argument(s), {supplied} passed")
    assert not problems, f"{path.relative_to(BACKEND)}:\n  " + "\n  ".join(problems)
