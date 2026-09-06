"""Headless tests for ``PuzzleWidget`` and the ``%%puzzle`` magic.

Constructing ``PuzzleWidget`` directly (bypassing IPython/the magic entirely)
is enough to drive it headlessly: setting ``.lines`` is exactly what the
frontend does after a drag/keyboard reorder (``model.set("lines", ...);
model.save_changes()``), which traitlets delivers to Python the same way
either way. Note that ``.lines`` right after construction is the *scramble*
of the lines passed in, not those lines -- see ``scramble_lines``.
"""
from puzzle_widget import PuzzleWidget
from puzzle_widget.widget import register_puzzle_magic


SOLVED = ["b = 5", "a = 10", "a + b"]


def test_lines_are_scrambled_and_not_solved_even_when_written_in_order():
    w = PuzzleWidget(SOLVED, 15)
    assert sorted(w.lines) == sorted(SOLVED)  # same lines...
    assert w.lines != SOLVED  # ...but not the order they were written in
    assert w.success is False  # and not an order that already solves it


def test_scramble_is_deterministic_across_widgets():
    a = PuzzleWidget(SOLVED, 15)
    b = PuzzleWidget(SOLVED, 15)
    assert a.lines == b.lines


def test_a_different_seed_can_give_a_different_scramble():
    default = PuzzleWidget(["a = 1", "b = 2", "c = 3", "d = 4", "a + b + c + d"], 10)
    other = PuzzleWidget(["a = 1", "b = 2", "c = 3", "d = 4", "a + b + c + d"], 10, seed=1)
    assert default.lines != other.lines
    assert not default.success and not other.success


def test_reordering_lines_rechecks_and_flips_success():
    w = PuzzleWidget(["a + b", "b = 5", "a = 10"], 15)
    assert w.success is False

    # simulate the frontend committing a reorder after a drag
    w.lines = ["b = 5", "a = 10", "a + b"]
    assert w.success is True
    assert w.last_error is None


def test_expected_repr_reflects_the_literal_passed_in():
    w = PuzzleWidget(["1 + 1"], 2)
    assert w.expected_repr == "2"

    w = PuzzleWidget(["a = 'x'", "a"], "x")
    assert w.expected_repr == "'x'"


def test_register_puzzle_magic_without_a_live_shell_returns_false():
    assert register_puzzle_magic(ipython=None) is False
