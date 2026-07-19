"""Headless tests for ``PuzzleWidget`` and the ``%%puzzle`` magic.

Constructing ``PuzzleWidget`` directly (bypassing IPython/the magic entirely)
is enough to drive it headlessly: setting ``.lines`` is exactly what the
frontend does after a drag/keyboard reorder (``model.set("lines", ...);
model.save_changes()``), which traitlets delivers to Python the same way
either way.
"""
from puzzle_widget import PuzzleWidget
from puzzle_widget.widget import register_puzzle_magic


def test_initial_scrambled_order_is_not_solved():
    w = PuzzleWidget(["a + b", "b = 5", "a = 10"], 15)
    assert w.lines == ["a + b", "b = 5", "a = 10"]
    assert w.success is False
    assert w.last_error is not None  # NameError, expected while scrambled


def test_initial_order_already_correct_is_solved():
    w = PuzzleWidget(["b = 5", "a = 10", "a + b"], 15)
    assert w.success is True


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
