
# puzzle-widget

A Jupyter widget where students drag scrambled code lines into the correct
order, built on [anywidget](https://anywidget.dev).

Tag a cell `%%puzzle <result>`; every line below it becomes a draggable row.
Drag (or focus a row and press the arrow keys) to reorder them -- the widget
re-runs the current order after every move and shows a checkmark once it
produces `<result>`.

```python
import puzzle_widget  # registers the %%puzzle cell magic
```

```
%%puzzle 15
a + b
b = 5
a = 10
```

The student sees the three lines in that scrambled order; dragging `a = 10`
and `b = 5` above `a + b` produces `15` and the widget shows "✓ Correct!".

## Installation

```bash
# pixi
pixi workspace channel add munch-group
pixi add puzzle-widget

# conda
conda install -c munch-group puzzle-widget

# pip
pip install puzzle-widget
```

## Writing a puzzle

- `<result>` is a Python **literal** (a number, string, list, ...), parsed
  with `ast.literal_eval` -- not an arbitrary expression, since the puzzle
  runs in its own isolated namespace, not the notebook's.
- Every line must be a complete, independent, non-indented statement. A
  puzzle can't contain multi-line blocks (`if`/`for`/`def`/...) that need to
  stay attached to each other, since any permutation of the lines has to at
  least *parse* -- only the values it produces should depend on the order.
- The result is the value of the **last line**, which must be a bare
  expression (`a + b`, or a variable's name on its own) -- exactly like a
  notebook cell only shows output for a trailing expression, not for an
  assignment. If the puzzle's final step is `total = a + b`, add a `total`
  line after it so there's a value to check.

You can also build a widget directly from a list of lines:

```python
from puzzle_widget import PuzzleWidget

PuzzleWidget(["a + b", "b = 5", "a = 10"], expected=15)
```

## Documentation

Full docs live at
[munch-group.org/puzzle-widget](https://munch-group.org/puzzle-widget).

## Development

This repo is managed with [pixi](https://pixi.sh):

```bash
pixi run install-dev   # editable install into the pixi environment
pixi run test          # run the pytest suite
pixi run docs          # execute the documentation notebooks
pixi run api           # build the quartodoc API reference
```

## License

MIT
