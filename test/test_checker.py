"""Headless tests for the pure exec-and-check engine (no anywidget/IPython)."""
from puzzle_widget.checker import run_puzzle, scramble_lines


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


def test_last_line_simple_assignment_is_not_the_result():
    # An assignment produces no "cell output" in a real notebook either --
    # `expected` must match a bare trailing expression, not an assignment's
    # target, even though the assignment itself still runs.
    result = run_puzzle(["a = 10", "b = 5", "total = a + b"], 15)
    assert result.success is False
    assert result.value is None
    assert result.error is None


def test_last_line_augmented_assignment_is_not_the_result():
    result = run_puzzle(["x = 10", "x += 5"], 15)
    assert result.success is False
    assert result.value is None
    assert result.error is None


def test_bare_expression_after_assignment_is_the_result():
    result = run_puzzle(["a = 10", "b = 5", "total = a + b", "total"], 15)
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


# --------------------------------------------------------------------------- #
# scramble_lines                                                              #
# --------------------------------------------------------------------------- #

SOLVED = ["b = 5", "a = 10", "a + b"]


def test_scramble_keeps_the_same_lines():
    assert sorted(scramble_lines(SOLVED, 15)) == sorted(SOLVED)


def test_scramble_never_returns_the_order_it_was_given():
    assert scramble_lines(SOLVED, 15) != SOLVED
    already_scrambled = ["a + b", "b = 5", "a = 10"]
    assert scramble_lines(already_scrambled, 15) != already_scrambled


def test_scramble_never_returns_an_already_solved_order():
    # The one guarantee that matters: whatever comes back, the student still
    # has a puzzle to solve.
    assert run_puzzle(scramble_lines(SOLVED, 15), 15).success is False


def test_scramble_is_deterministic_for_a_given_seed():
    assert scramble_lines(SOLVED, 15) == scramble_lines(SOLVED, 15)
    assert scramble_lines(SOLVED, 15, seed=3) == scramble_lines(SOLVED, 15, seed=3)


def test_scramble_of_every_solvable_puzzle_stays_unsolved():
    # Sweep a range of puzzle sizes: every scramble must be a permutation of
    # the input that doesn't already produce the expected value.
    for n in range(2, 9):
        names = [chr(ord("a") + i) for i in range(n - 1)]
        lines = [f"{name} = {i + 1}" for i, name in enumerate(names)] + [" + ".join(names)]
        expected = sum(range(1, n))
        assert run_puzzle(lines, expected).success is True  # the puzzle is solvable
        scrambled = scramble_lines(lines, expected)
        assert sorted(scrambled) == sorted(lines)
        assert scrambled != lines
        assert run_puzzle(scrambled, expected).success is False


def test_scramble_of_a_single_line_is_returned_unchanged():
    # Nothing to shuffle -- a degenerate puzzle is shown as-is rather than
    # raising (see scramble_lines' docstring).
    assert scramble_lines(["1 + 1"], 2) == ["1 + 1"]
    assert scramble_lines([], 2) == []


def test_scramble_falls_back_to_the_original_when_no_order_qualifies():
    # Identical lines: every permutation is the input order *and* solves the
    # puzzle, so no candidate can qualify -- scramble_lines gives up after
    # its bounded retries and returns the input rather than raising.
    lines = ["7", "7"]
    assert scramble_lines(lines, 7) == lines
