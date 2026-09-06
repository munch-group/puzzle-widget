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

``scramble_lines`` handles the other half of a puzzle's life: turning the
lines an author wrote (usually in the correct order) into the scrambled
starting order the student is shown -- deterministically, and never one that
already solves the puzzle.
"""

from __future__ import annotations

import ast
import random

__all__ = ["PuzzleResult", "run_puzzle", "scramble_lines", "DEFAULT_SEED"]

#: Seed for ``scramble_lines``, so a given puzzle always scrambles the
#: same way -- every student sees the same starting order, and a failing
#: puzzle is reproducible from its lines alone.
DEFAULT_SEED = 7

#: How many shuffles ``scramble_lines`` tries before giving up on finding
#: an unsolved order. One is almost always enough; the loop only matters for
#: tiny/degenerate puzzles where many permutations happen to be solutions.
_MAX_SCRAMBLE_ATTEMPTS = 100


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
    result associated with the last one -- mirroring how a Jupyter cell only
    ever displays an *output* for a bare trailing expression, never for a
    statement like an assignment:

    - if it's a bare expression (``ast.Expr``), the expression's value
      (mirroring what a REPL/notebook would display for it);
    - otherwise (e.g. an assignment), the line is still executed -- so a
      runtime error there is still caught by ``run_puzzle`` -- but there is
      no "cell output" to compare against `expected`, so this returns
      ``None``. Authors who want a variable's value checked should end the
      puzzle with that variable's bare name on its own line, exactly as
      they'd need a trailing bare expression to see it printed in a real
      notebook cell.
    """
    if not tree.body:
        return None
    *body, last = tree.body
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), "<puzzle>", "exec"), namespace)
    if isinstance(last, ast.Expr):
        return eval(compile(ast.Expression(body=last.value), "<puzzle>", "eval"), namespace)
    exec(compile(ast.Module(body=[last], type_ignores=[]), "<puzzle>", "exec"), namespace)
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


def scramble_lines(lines, expected, seed=DEFAULT_SEED):
    """Return a shuffled copy of ``lines`` that does not already solve the puzzle.

    The lines an author writes are usually in (or near) the correct order,
    and a puzzle whose starting order is already solved -- or simply the
    order it was written in -- isn't a puzzle. This shuffles them with a
    fixed seed, so the scramble is random-looking but deterministic (the
    same puzzle always starts the same way), and rejects any candidate that

    - equals the order that was passed in, or
    - already produces ``expected`` (checked with ``run_puzzle``),

    reshuffling until one qualifies.

    Parameters
    ----------
    lines : list of str
        The puzzle's lines, in any order.
    expected : object
        The target value, used to reject an already-solved shuffle.
    seed : int, optional
        Seed for the shuffle. Defaults to ``DEFAULT_SEED`` (7), so the same
        puzzle always starts in the same scrambled order.

    Returns
    -------
    list of str
        A scrambled order. Degenerate puzzles where no such order exists
        (fewer than two lines, all lines identical, or every permutation
        solving the puzzle) fall back to a copy of ``lines`` unchanged --
        there is nothing better to show, and raising would be worse than
        displaying an unscrambled puzzle.
    """
    original = list(lines)
    if len(original) < 2:
        return original

    rng = random.Random(seed)
    candidate = list(original)
    for _ in range(_MAX_SCRAMBLE_ATTEMPTS):
        rng.shuffle(candidate)
        if candidate != original and not run_puzzle(candidate, expected).success:
            return candidate
    return original
