"""
puzzle_widget.widget
=====================

A Jupyter widget where students drag scrambled code lines into the correct
order: tag a cell with ``%%puzzle <result>`` and the lines below it become a
reorderable list. The widget re-runs the current order after every reorder
(``puzzle_widget.checker.run_puzzle``) and shows whether it produces
``<result>``.

* Built on `anywidget` (the standard ipywidgets comm protocol + plain ESM), so it
  behaves the same across VS Code notebooks, JupyterLab, Notebook 7 and Colab.
* The frontend only reports the user's current line order; Python owns all
  checking logic (see ``checker.py``) -- the frontend never evaluates code.

Usage
-----
    import puzzle_widget  # registers the %%puzzle cell magic

    %%puzzle 15
    a + b
    b = 5
    a = 10

Or construct the widget directly from a list of lines::

    from puzzle_widget import PuzzleWidget

    PuzzleWidget(["a + b", "b = 5", "a = 10"], expected=15)
"""

from __future__ import annotations

import ast

import anywidget
import traitlets

from .checker import run_puzzle

try:  # IPython is present whenever a kernel is running, but guard anyway.
    from IPython import get_ipython
    from IPython.display import display as _ipy_display
except Exception:  # pragma: no cover
    def get_ipython():
        return None

    def _ipy_display(*a, **k):
        pass


__all__ = ["PuzzleWidget", "register_puzzle_magic"]


# --------------------------------------------------------------------------- #
# Frontend (ESM + CSS) -- no external dependencies, offline-safe.             #
# --------------------------------------------------------------------------- #

_ESM = r"""
/**
 * HTML-escape a string so raw code text can be injected via innerHTML safely
 * (row text is otherwise set via textContent, which escapes automatically --
 * this is only for the one spot that builds an HTML string directly).
 */
function esc(s){
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

/**
 * Find the row the dragged element should be inserted *before*, given the
 * pointer's current Y position: the row whose vertical midpoint is the
 * closest one still below the pointer. Returns undefined if the pointer is
 * below every remaining row (caller should append at the end instead).
 * Standard vanilla-JS sortable-list recipe -- a single delegated `dragover`
 * on the list (not one listener per row) avoids reorder jitter from
 * overlapping per-row dragover regions.
 */
function rowAfter(list, y){
  const rows = [...list.querySelectorAll(".pz-row:not(.pz-dragging)")];
  return rows.reduce((closest, row) => {
    const box = row.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset){
      return { offset, element: row };
    }
    return closest;
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}

/**
 * anywidget render entry point. Builds the puzzle UI once and wires drag/
 * keyboard reordering plus success-state redraws; returns a teardown
 * function per anywidget's render/cleanup contract.
 */
function render({ model, el }){

  /** Current row order read straight from the DOM (source of truth while dragging). */
  function currentOrder(list){
    return [...list.querySelectorAll(".pz-row")].map(row => row.dataset.text);
  }

  /** Push the DOM's current order to Python; triggers a re-check there. */
  function commit(list){
    model.set("lines", currentOrder(list));
    model.save_changes();
  }

  /** Move `row` one slot up (`dir=-1`) or down (`dir=1`) among its siblings. */
  function moveRow(list, row, dir){
    if (dir < 0 && row.previousElementSibling){
      list.insertBefore(row, row.previousElementSibling);
    } else if (dir > 0 && row.nextElementSibling){
      list.insertBefore(row.nextElementSibling, row);
    } else {
      return;
    }
    row.focus();
    commit(list);
  }

  function draw(){
    el.innerHTML = "";
    const root = document.createElement("div");
    root.className = "pz-root";

    const goal = document.createElement("div");
    goal.className = "pz-goal";
    goal.innerHTML = "Arrange the lines to produce: <code>" + esc(model.get("expected_repr")) + "</code>";
    root.appendChild(goal);

    const list = document.createElement("ol");
    list.className = "pz-list";

    (model.get("lines") || []).forEach((text) => {
      const row = document.createElement("li");
      row.className = "pz-row";
      row.draggable = true;
      row.tabIndex = 0;
      row.dataset.text = text;

      const handle = document.createElement("span");
      handle.className = "pz-handle";
      handle.textContent = "⋮⋮";
      handle.setAttribute("aria-hidden", "true");

      const code = document.createElement("span");
      code.className = "pz-code";
      code.textContent = text;

      row.appendChild(handle);
      row.appendChild(code);

      row.addEventListener("dragstart", (e) => {
        row.classList.add("pz-dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", ""); // Firefox needs data set to allow the drag
      });
      row.addEventListener("dragend", () => {
        row.classList.remove("pz-dragging");
        commit(list);
      });
      row.addEventListener("keydown", (e) => {
        if (e.key === "ArrowUp"){ e.preventDefault(); moveRow(list, row, -1); }
        else if (e.key === "ArrowDown"){ e.preventDefault(); moveRow(list, row, 1); }
      });

      list.appendChild(row);
    });

    list.addEventListener("dragover", (e) => {
      e.preventDefault();
      const dragging = list.querySelector(".pz-dragging");
      if (!dragging) return;
      const after = rowAfter(list, e.clientY);
      if (after == null) list.appendChild(dragging);
      else list.insertBefore(dragging, after);
    });

    root.appendChild(list);

    const success = model.get("success");
    const status = document.createElement("div");
    status.className = "pz-status " + (success ? "pz-success" : "pz-pending");
    status.textContent = success ? "✓ Correct!" : "Not solved yet — drag the lines into place.";
    root.appendChild(status);

    el.appendChild(root);
  }

  draw();
  // Redraw on success changes (drives the status banner); a `lines` change
  // with no accompanying success change means the DOM the user just dragged
  // already reflects the new order, so no rebuild is needed for that alone.
  model.on("change:success", draw);
  return () => model.off("change:success", draw);
}

export default { render };
"""

_CSS = r"""
/* Styles for the DOM built in _ESM's render(): .pz-root > .pz-goal, .pz-list
   (draggable .pz-row items), .pz-status. */
.pz-root { display: flex; flex-direction: column; gap: 10px; margin-top: 8px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; max-width: 520px; }
.pz-goal { font-size: 13px; color: #4a4a55; }
.pz-goal code { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Menlo, monospace;
  background: #eef0f2; border-radius: 4px; padding: 1px 5px; }
.pz-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.pz-row { display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  border: 1px solid #d0d0d8; border-radius: 6px; background: #fbfbfd;
  box-shadow: 0 1px 3px rgba(0,0,0,.06); cursor: grab; }
.pz-row:focus { outline: 2px solid #0969da; outline-offset: 1px; }
.pz-row.pz-dragging { opacity: 0.4; }
.pz-handle { color: #9a9aa6; user-select: none; line-height: 1; }
.pz-code { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Menlo, monospace;
  font-size: 13px; color: #24292f; white-space: pre; }
.pz-status { font-size: 13px; font-weight: 600; padding: 6px 10px; border-radius: 6px; }
.pz-status.pz-pending { color: #6e7781; background: #eef0f2; }
.pz-status.pz-success { color: #116329; background: #ddf4e4; }
"""


# --------------------------------------------------------------------------- #
# The widget                                                                  #
# --------------------------------------------------------------------------- #

class PuzzleWidget(anywidget.AnyWidget):
    """A reorderable list of code lines that checks itself against an expected result.

    Parameters
    ----------
    lines : list of str
        The puzzle's lines in their initial (typically scrambled) order.
        Each must be a complete, independent, non-indented statement -- no
        multi-line ``if``/``for``/``def``/... blocks, since those can't
        survive an arbitrary reordering (see ``puzzle_widget.checker``).
    expected : object
        The value the lines should produce, in the correct order, to count
        as solved. Compared against the value of the last line, which must
        be a bare expression (e.g. a variable's name on its own line) --
        an assignment produces no comparable value, exactly as it produces
        no cell output in a real notebook -- see
        ``puzzle_widget.checker.run_puzzle``.

    Attributes
    ----------
    success : bool
        Whether the current order is correct. Recomputed automatically
        whenever ``lines`` changes (i.e. after every drag/keyboard reorder).
    last_error : str or None
        A short description of the exception raised by the current order,
        if any -- expected and routine while the student is still arranging
        a scrambled puzzle, not shown in the widget UI itself.
    """

    _esm = _ESM
    _css = _CSS

    lines = traitlets.List(traitlets.Unicode()).tag(sync=True)
    expected_repr = traitlets.Unicode().tag(sync=True)
    success = traitlets.Bool(False).tag(sync=True)

    def __init__(self, lines, expected):
        super().__init__()
        self._expected = expected
        self.expected_repr = repr(expected)
        self.last_error = None
        self.lines = list(lines)
        self._check()

    @traitlets.observe("lines")
    def _lines_changed(self, change):
        self._check()

    def _check(self):
        result = run_puzzle(self.lines, self._expected)
        self.last_error = result.error
        self.success = result.success


def register_puzzle_magic(ipython=None):
    r"""Register the `%%puzzle` cell magic.

    In IPython/Jupyter, `%%puzzle <result>` turns the cell's lines into a
    reorderable `PuzzleWidget` that checks itself against `<result>` (a
    Python literal) after every reorder::

        %%puzzle 15
        a + b
        b = 5
        a = 10

    `<result>` must be a literal (number, string, list, ...) parsed with
    `ast.literal_eval` -- not an arbitrary expression, since the puzzle runs
    in its own isolated namespace rather than the notebook's, so a variable
    reference wouldn't resolve to anything meaningful. Blank lines in the
    cell are dropped and each remaining line is stripped of surrounding
    whitespace before becoming a draggable row.

    Called automatically on import; returns True when a live shell is found,
    False otherwise (e.g. plain Python).
    """
    ip = ipython or get_ipython()
    if ip is None:
        return False

    def puzzle(line, cell):
        arg = line.strip()
        if not arg:
            print("%%puzzle: missing the expected result, e.g. `%%puzzle 42`.")
            return
        try:
            expected = ast.literal_eval(arg)
        except (ValueError, SyntaxError):
            print(f"%%puzzle: {arg!r} isn't a Python literal (number, string, list, ...).")
            return
        lines = [ln.strip() for ln in (cell or "").splitlines() if ln.strip()]
        if not lines:
            print("%%puzzle: cell is empty -- put scrambled code lines below the magic line.")
            return
        _ipy_display(PuzzleWidget(lines, expected))

    ip.register_magic_function(puzzle, magic_kind="cell", magic_name="puzzle")
    return True


try:
    register_puzzle_magic()
except Exception:
    pass
