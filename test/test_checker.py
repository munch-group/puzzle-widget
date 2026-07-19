"""Headless tests for the pure exec-and-check engine (no anywidget/IPython)."""
from puzzle_widget.checker import run_puzzle


def test_correct_order_bare_expression():
    result = run_puzzle(["b = 5", "a = 10", "a + b"], 15)
    assert result.success is True
    assert result.value == 15
    assert result.error is None


def test_scrambled_order_reports_name_error_not_success():
    result = run_puzzle(["a + b", "b = 5", "a = 10"], 15)
    assert result.success is False
    assert result.value is None
    assert "NameError" in result.error


def test_correct_lines_but_wrong_expected_value():
    result = run_puzzle(["b = 5", "a = 10", "a + b"], 999)
    assert result.success is False
    assert result.value == 15
    assert result.error is None


def test_last_line_simple_assignment_is_the_result():
    result = run_puzzle(["a = 10", "b = 5", "total = a + b"], 15)
    assert result.success is True
    assert result.value == 15


def test_last_line_augmented_assignment_is_the_result():
    result = run_puzzle(["x = 10", "x += 5"], 15)
    assert result.success is True
    assert result.value == 15


def test_single_line_puzzle():
    result = run_puzzle(["1 + 1"], 2)
    assert result.success is True


def test_string_result():
    result = run_puzzle(["b = 'World'", "a = 'Hello, '", "a + b"], "Hello, World")
    assert result.success is True


def test_list_result():
    result = run_puzzle(["a = [1, 2]", "b = [3]", "a + b"], [1, 2, 3])
    assert result.success is True


def test_unparseable_order_reports_syntax_error_not_success():
    # A dangling ":" is not valid as a standalone top-level statement in any
    # order -- exercising the SyntaxError path without needing an indented
    # multi-line block (which puzzles aren't meant to contain in the first
    # place, see checker.py's module docstring).
    result = run_puzzle(["if x:"], True)
    assert result.success is False
    assert "SyntaxError" in result.error


def test_each_check_runs_in_a_fresh_namespace():
    # A previous (wrong) order's leftover bindings must not leak into the
    # next check -- each call to run_puzzle gets its own empty namespace.
    first = run_puzzle(["leaked = 123", "leaked"], 999)
    assert first.success is False
    second = run_puzzle(["leaked"], 999)
    assert second.success is False
    assert "NameError" in second.error
