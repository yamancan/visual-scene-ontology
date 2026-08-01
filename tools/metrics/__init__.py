"""Agreement metrics over VSON graphs.

One module today: :mod:`tools.metrics.smatch`, the triple-level
precision/recall/F1 of docs/vson.md §5.15, exposed to the CLI as `vson diff`.

A metric here answers "how far apart are these two documents", never "is this
document right". Nothing in this package reads an image, and §2.1 governs every
number it prints.

Nothing is imported at package level on purpose: `python3 -m
tools.metrics.smatch` imports the package before running the module, and a
package that has already imported it earns a `RuntimeWarning` on every run. The
eval-loop entry point is one line either way::

    from tools.metrics.smatch import compare_paths
"""
