"""puzzle_widget.checker
=======================

Pure-Python engine behind the ``%%puzzle`` widget: given the student's current
line order, run it and decide whether it produces the expected result. No
``anywidget``/``traitlets``/IPython dependency, so it's directly unit-testable.

A puzzle is a flat sequence of independent, non-indented statements (no
``if``/``for``/``def``/... blocks spanning multiple lines) -- any permutation
of complete statements is syntactically valid Python, so a wrong order can
only fail at *runtime* (a ``NameError`` from referencing a not-yet-defined
name being the common case while the student is still arranging the lines),
never with a ``SyntaxError``. See ``run_puzzle``'s docstring for how "the
result" is determined from the last line.
"""

from __future__ import annotations

import ast

__all__ = ["PuzzleResult", "run_puzzle"]


class PuzzleResult:
    """The outcome of running one candidate line order.

    Attributes
    ----------
    success : bool
        Whether the produced value equals the expected one.
    value : object or None
        The value produced by the last line, or ``None`` if nothing could be
        determined (empty input, or an exception before it was reached).
    error : str or None
        A short ``"ExceptionType: message"`` description if running the
        lines raised, else ``None``. Common and *expected* while the student
        is still arranging a scrambled puzzle (e.g. ``NameError`` from a line
        that references a name defined further down) -- not a bug.
    """

    __slots__ = ("success", "value", "error")

    def __init__(self, success, value=None, error=None):
        self.success = success
        self.value = value
        self.error = error

    def __repr__(self):
        return f"PuzzleResult(success={self.success!r}, value={self.value!r}, error={self.error!r})"


def _last_line_value(tree, namespace):
    """Run every statement in ``tree`` except the last, then return the
    result associated with the last one:

    - if it's a bare expression (``ast.Expr``), the expression's value
      (mirroring what a REPL/notebook would display for it);
    - if it's a simple assignment/augmented assignment to a single name
      (``x = ...`` / ``x += ...``), the value bound to that name afterward;
    - otherwise (e.g. the puzzle's last line has some other statement shape),
      ``None`` -- authors should end puzzles with an expression or a
      single-name assignment so there is a value to check.
    """
    if not tree.body:
        return None
    *body, last = tree.body
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), "<puzzle>", "exec"), namespace)
    if isinstance(last, ast.Expr):
        return eval(compile(ast.Expression(body=last.value), "<puzzle>", "eval"), namespace)
    exec(compile(ast.Module(body=[last], type_ignores=[]), "<puzzle>", "exec"), namespace)
    if isinstance(last, ast.Assign) and len(last.targets) == 1 and isinstance(last.targets[0], ast.Name):
        return namespace.get(last.targets[0].id)
    if isinstance(last, ast.AugAssign) and isinstance(last.target, ast.Name):
        return namespace.get(last.target.id)
    return None


def run_puzzle(lines, expected):
    """Run ``lines`` (joined with newlines) in a fresh, isolated namespace and
    check whether the value of the last line equals ``expected``.

    Never raises: a ``SyntaxError`` from an unparseable order, or any
    exception raised while running the lines, is caught and reported via
    ``PuzzleResult.error`` with ``success=False`` -- both are routine while a
    puzzle is still scrambled, not something callers need to guard against.

    Parameters
    ----------
    lines : list of str
        The current candidate order, one statement per line.
    expected : object
        The target value (typically a literal parsed from the ``%%puzzle``
        magic's argument).

    Returns
    -------
    PuzzleResult
    """
    code = "\n".join(lines)
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return PuzzleResult(False, error=f"SyntaxError: {e.msg}")

    try:
        value = _last_line_value(tree, {})
    except Exception as e:
        return PuzzleResult(False, error=f"{type(e).__name__}: {e}")

    try:
        success = bool(value == expected)
    except Exception:
        success = False
    return PuzzleResult(success, value=value)
