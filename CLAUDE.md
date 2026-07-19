# CLAUDE.md

Project context for `puzzle-widget` -- a Jupyter widget where students drag
scrambled code lines into the correct order, built on
[anywidget](https://anywidget.dev).

## What this is

Tag a cell `%%puzzle <result>` and its lines become a reorderable list below
the cell: drag a row (or focus it and press the arrow keys) to move it up or
down. After every reorder, the widget re-runs the current line order in an
isolated namespace and checks whether it produces `<result>` -- showing a
"✓ Correct!" banner once it does.

The repo was scaffolded from the `munch-group` Python-library template (pixi
environment, quartodoc docs, conda/PyPI release automation) -- the same
template `steps-widget`/`turtle-widget`/`codelens-widget` use. Unlike
`steps-widget`, there is no separate console-script entry point here (no
CLI use case) -- the whole package is the widget + magic, mirroring
`turtle-widget`'s single-`widget.py` shape, except the exec/check logic is
split out into its own `checker.py` (see below) since it's independently
useful and easily unit-tested without any `anywidget`/IPython dependency.

## Package layout

The package is `puzzle_widget` under `src/`:

- `src/puzzle_widget/checker.py` -- the pure engine. `run_puzzle(lines,
  expected)` joins `lines` with newlines, `ast.parse`s them, execs every
  statement but the last in a **fresh, empty namespace**, then reads "the
  result" off the last one: a bare expression's value, mirroring the one
  case a real notebook cell shows output for -- an assignment as the last
  line still runs (so a runtime error there is still caught) but produces no
  comparable value, same as it produces no cell output for real. Returns a
  `PuzzleResult(success, value, error)` -- it never raises; a `SyntaxError`
  or any runtime exception from a still-scrambled order is caught and
  reported via `.error` with `success=False`, since that's the *expected*
  state for most orders while the student is still arranging the puzzle, not
  a bug to guard against upstream.
- `src/puzzle_widget/widget.py` -- `PuzzleWidget` (the `anywidget.AnyWidget`)
  + the embedded `_ESM`/`_CSS` frontend strings + `register_puzzle_magic()`.
  `PuzzleWidget.__init__` calls `_check()` once immediately (so the initial
  scrambled order's state is correct before the widget ever renders); a
  `@traitlets.observe("lines")` handler calls `_check()` again every time the
  frontend commits a reorder.
- `src/puzzle_widget/__init__.py` -- re-exports `PuzzleWidget`/
  `register_puzzle_magic` from `widget.py` (mirrors `turtle_widget`'s
  `from .widget import Turtle`). Importing `puzzle_widget` therefore both
  exposes the public API and registers the cell magic as a side effect.
- `test/` -- headless pytest suite: `test_checker.py` (the pure engine, no
  anywidget dependency at all), `test_widget.py` (`PuzzleWidget` + the
  magic), `test_frontend.py` (`node --check` on the extracted `_ESM`, skipped
  if `node` isn't on `PATH`).
- `docs/` -- Quarto + quartodoc site (`docs/pages/*.ipynb` prose,
  `docs/api/*.qmd` API ref -- the checked-in `.qmd` files are placeholders;
  run `pixi run api` to regenerate them from the live docstrings).
- `pyproject.toml` -- packaging metadata **and** the pixi workspace (deps +
  task runner).
- `conda-build/`, `.github/workflows/` -- conda/PyPI release on tag push, for
  macOS, Linux, and Windows.
- `scripts/` -- version-bump / docs-build / release helpers invoked by pixi
  tasks.

## Architecture

### Why an isolated namespace, not the notebook's

`steps_widget`'s `%%steps` deliberately traces the notebook's *live*
execution (via `ip.run_cell`) -- its whole point is showing how the real
cell actually evaluates. `%%puzzle` is different: the cell's lines are
**scrambled on purpose**, and the widget re-runs them on every drag, often
many times per second. Running that through `ip.run_cell` would repeatedly
execute broken/partial code directly into the notebook's namespace (stray
prints, half-applied assignments, `NameError` spam) every time the student
drags a row. Instead, `run_puzzle` always execs into a **fresh `{}`** --
each check is fully isolated from the notebook and from every other check.
The consequence: puzzle code must be self-contained (no references to
notebook-level variables), which is a reasonable constraint for this kind of
short, self-contained exercise.

### The "flat statement sequence" constraint

A puzzle's lines must be independent, non-indented, single-line statements
-- no `if`/`for`/`def`/`class`/... blocks spanning multiple lines, and no
line that only makes sense directly after a specific other line (e.g. a
continuation). This isn't an arbitrary restriction: it's what guarantees
*any* permutation of the lines is still syntactically valid Python (each
line is already a complete statement on its own), so a wrong order can only
fail at runtime -- typically a `NameError` from a line that references a
name defined further down -- never with a `SyntaxError`. `checker.py`'s
module docstring states this; `run_puzzle` still catches `SyntaxError`
defensively (see `test_unparseable_order_reports_syntax_error_not_success`),
but authors should stay inside the flat-sequence shape.

### Synced traitlets

`lines` (`List[Unicode]`), `expected_repr` (`Unicode`, the `repr()` of the
literal passed to the widget, shown as the on-screen goal), and `success`
(`Bool`) are the only synced state -- there is no separate "error" trait;
`last_error` is a plain Python attribute (not `.tag(sync=True)`), used by
tests but deliberately not surfaced in the UI (see Gotchas).

State crosses the boundary in one direction at a time: the frontend commits
a new `lines` order (`model.set("lines", ...); model.save_changes()`) after
a drag/keyboard move; Python's `@observe("lines")` handler recomputes
`success` and syncs it back; the frontend's `render()` only redraws on
`change:success` (a `lines` change with no accompanying `success` change
means the DOM the user just rearranged already shows the right order, so
redrawing would just be wasted work -- see `_ESM`'s comment on this).

### Frontend reordering (`_ESM`)

Hand-rolled vanilla JS, no external/CDN dependencies (same convention as
`turtle-widget`/`steps-widget`) -- no drag-and-drop library is vendored.

- **Drag**: native HTML5 Drag and Drop (`draggable="true"` per row,
  `dragstart`/`dragend` on each row, a single delegated `dragover` on the
  list). `rowAfter()` finds the row whose vertical midpoint is just below
  the pointer and inserts the dragged row before it (the standard
  vanilla-JS sortable-list recipe) -- a single list-level listener, not one
  per row, avoids reorder jitter from overlapping per-row drop zones.
- **Keyboard**: each row is `tabIndex=0`; `ArrowUp`/`ArrowDown` while a row
  has focus swaps it with its neighbor via `moveRow()`. Same `commit()` path
  as a drag drop.
- Both paths call the same `commit(list)`, which reads the *current DOM
  order* (`currentOrder()`) and pushes it to Python -- the DOM, not any JS
  array, is the source of truth for "what order is this right now" during a
  drag.

## Gotchas

- **A scrambled order raising an exception is normal, not a bug.** Most
  orderings of a puzzle with 3+ lines will `NameError` (or similar) when
  run; `run_puzzle` treats that identically to "wrong value" --
  `success=False`, nothing raised, no traceback shown in the widget. Don't
  "fix" this by trying to make more orderings succeed or by surfacing
  `last_error` in the UI -- a constant stream of tracebacks for what is
  expected, frequent, transient state would be worse UX, not better.
- **The last line determines "the result" only if it's a bare expression.**
  Exactly like a real notebook cell only shows output for a trailing bare
  expression, `run_puzzle` only reads a comparable value off a last line
  that's a bare expression (e.g. `x`); an assignment (`x = 44`, `x += 1`)
  still runs -- so a bug there still surfaces as an exception -- but
  `run_puzzle` returns `value=None` with no error, which can never equal
  `expected`. Puzzle authors should end every puzzle with the final
  variable's bare name on its own line, not an assignment to it -- see
  `test_last_line_simple_assignment_is_not_the_result` in `test_checker.py`.
- **Equality is exact (`==`).** No floating-point tolerance is built in;
  pick puzzles whose correct order produces an exactly-comparable value
  (ints, strings, exact-valued floats, lists/tuples/dicts of the same) if
  this matters.
- **Every check gets a fresh namespace.** A wrong order's leftover bindings
  never leak into the next check (see
  `test_each_check_runs_in_a_fresh_namespace`) -- don't be tempted to reuse
  one namespace across checks "for efficiency"; it would let an earlier
  (wrong) order's state leak into evaluating a later one.

## Environment & commands

Pixi-managed (config in `pyproject.toml` under `[tool.pixi.*]`; channels
`conda-forge` + `munch-group`; platforms `osx-arm64`, `linux-64`, `win-64`).
Python `>=3.9,<3.14`. Key deps: `anywidget` (0.11.x), `traitlets`, `ipython`,
`nodejs` (for the `node --check` frontend test), `quarto`/`quartodoc`,
`pytest`.

- Dev install: `pixi run install-dev` (editable, no build isolation).
- Run tests: `pixi run test` (== `pytest test/`).
- Try the widget: open a notebook, `import puzzle_widget`, then
  `%%puzzle 15` followed by scrambled lines in a cell.
- JS syntax check after editing the embedded frontend string:
  ```bash
  python -c "from puzzle_widget import widget as m; open('/tmp/e.mjs','w').write(m._ESM)"
  node --check /tmp/e.mjs
  ```
  (this is also `test_frontend.py::test_esm_is_syntactically_valid_js`, run
  automatically by `pixi run test` whenever `node` is on `PATH`).
- Build docs: `pixi run api` (quartodoc API pages), then `pixi run docs`
  (execute the doc notebooks in place).
- Release: `pixi run bump` / `release` / `version` drive
  `scripts/bump_version.py` + a tag push, which triggers the conda/PyPI
  workflows.

## Distribution

Both `.github/workflows/conda-release.yml` and `pypi-release.yml` trigger on
version tag pushes (`vX.Y[.Z][.rcN]`):

- **conda**: builds natively on `macOS-latest`, `ubuntu-latest`, and
  `windows-latest`, using `conda-build/meta.yaml` -- which pins `python`
  (host and run) to `pyproject.toml`'s `requires-python` via Jinja, and
  derives the run requirements from `[project.dependencies]`
  (`anywidget`/`traitlets`/`ipython`, all on `conda-forge` -- no extra
  channel needed here, unlike `myiagi-widget`'s dependency on the
  unpublished `steps-widget`). Uploaded to the `munch-group` Anaconda.org
  channel.
- **pip**: pure-Python universal wheel, published to PyPI.

## Testing approach

- `checker.run_puzzle` is fully headless-testable (pure stdlib `ast`, no
  `anywidget`/IPython): correct order, scrambled order (routine exception),
  wrong value, last-line-as-(augmented)-assignment *not* counting as a
  result, a bare expression after such an assignment does, string/list
  results, an unparseable order, and namespace isolation across calls.
- `PuzzleWidget` is tested by constructing it directly (bypassing IPython
  entirely) and then **setting `.lines`** to simulate a reorder -- that's
  exactly what the frontend's `commit()` does over the comm
  (`model.set("lines", ...); model.save_changes()`), and traitlets delivers
  it to `_lines_changed` the same way either way.
- The actual drag/keyboard DOM interaction isn't (and can't be, headlessly)
  exercised by the pytest suite -- `test_frontend.py` only checks the
  extracted `_ESM` parses as valid JS. Manually verify real drag/keyboard
  reordering against a live notebook after editing `_ESM`.
- `register_puzzle_magic(ipython=None)` returning `False` is tested the same
  way as `steps_widget`'s equivalent.
