"""
make_practice_notebooks.py
==========================
Derive the *practice* version of each module notebook from the complete one.

Architecture
------------
`notebooks/module_N.ipynb` is the SINGLE SOURCE OF TRUTH. It contains the teaching
prose, the tutorial code, the problem statements, AND the worked answers.

An answer cell needs two things:

  * `#| code-fold: true` (+ an optional `#| code-summary: "..."`) so the WEBSITE
    renders it collapsed and the reader chooses whether to reveal it, and
  * a `solution` marker so THIS SCRIPT knows to strip it. Mark it either by adding
    `solution` to the cell's tags in JupyterLab's Property Inspector, or simply by
    typing `#| tags: [solution]` at the top of the cell. Both work; the typed form
    means you never have to leave the keyboard.

This script copies each module notebook and replaces every `solution`-tagged cell
with a stub, producing `notebooks/module_N_practice.ipynb` — the practice notebook
people download and open in Colab. Because it is generated, the practice version can
never drift from the module.

Optional scaffolding
--------------------
If an answer cell contains a divider line `# --- SOLUTION ---`, everything ABOVE the
divider is preserved in the practice stub (use it to hand out starter code); the
answer below it is removed. Without a divider, the whole body is replaced.

Usage
-----
    pixi run make-practice            # regenerate all
    pixi run python scripts/make_practice_notebooks.py --check   # CI: verify up to date
"""

from __future__ import annotations

import argparse
import copy
import glob
import os
import sys

import nbformat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(ROOT, "notebooks")

SOLUTION_TAG = "solution"
DIVIDER = "# --- SOLUTION ---"
PRACTICE_SUFFIX = "_practice"

# Prepended to every practice notebook so it runs in a bare Colab kernel.
COLAB_SETUP = """\
#| eval: false
# --- Colab / fresh-environment setup -------------------------------------
# Running locally with pixi? You can skip this cell.
%pip install --quiet ratinabox
"""

STUB_BODY = """\
# TODO: your answer here.
# Hint: the module page for this notebook walks through the API you need.
"""


def is_answer_cell(cell) -> bool:
    """Is this an answer cell (to be stubbed out of the practice notebook)?

    Two equivalent ways to mark one, so you never have to leave the keyboard while
    authoring in JupyterLab:

      1. a `solution` entry in the cell's **tags** metadata (JupyterLab's Property
         Inspector), or
      2. a `#| tags: [solution]` line typed at the top of the cell source — normal
         Quarto cell-option syntax, no UI needed.
    """
    if cell.cell_type != "code":
        return False
    if SOLUTION_TAG in cell.metadata.get("tags", []):
        return True
    for line in cell.source.splitlines():
        s = line.strip()
        if not s.startswith("#|"):
            # options must sit in the contiguous block at the top of the cell
            if s and not s.startswith("#"):
                break
            continue
        if s.startswith("#| tags:") and SOLUTION_TAG in s:
            return True
    return False


def strip_quarto_directives(src: str) -> str:
    """Drop `#| ...` cell directives (they're for Quarto rendering, not the reader)."""
    keep = [ln for ln in src.splitlines() if not ln.strip().startswith("#|")]
    return "\n".join(keep).strip("\n")


def make_stub(src: str) -> str:
    """Turn an answer cell body into a practice stub, preserving any scaffolding."""
    body = strip_quarto_directives(src)
    if DIVIDER in body:
        scaffold = body.split(DIVIDER, 1)[0].rstrip("\n")
        return f"{scaffold}\n\n{STUB_BODY}" if scaffold.strip() else STUB_BODY
    return STUB_BODY


def build_practice(nb: nbformat.NotebookNode) -> tuple[nbformat.NotebookNode, int]:
    """Return (practice notebook, number of answer cells stubbed)."""
    out = copy.deepcopy(nb)
    n_stubbed = 0
    cells = []

    setup = nbformat.v4.new_code_cell(COLAB_SETUP)
    setup.metadata["tags"] = ["colab-setup"]
    # Pin the cell id: nbformat mints a random one, which would make this script
    # nondeterministic and `--check` fail even right after a regeneration.
    setup.id = "colab-setup"
    cells.append(setup)

    for cell in out.cells:
        if is_answer_cell(cell):
            cell.source = make_stub(cell.source)
            cell.metadata["tags"] = [
                t for t in cell.metadata.get("tags", []) if t != SOLUTION_TAG
            ] + ["exercise"]
            n_stubbed += 1
        # Never ship stored outputs in the practice notebook.
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
        cells.append(cell)

    out.cells = cells
    return out, n_stubbed


def fingerprint(nb: nbformat.NotebookNode) -> list[tuple[str, str, tuple[str, ...]]]:
    """Compare notebooks by MEANING, not bytes.

    Cell ids and stored outputs are owned by other tools -- nbstripout renumbers ids
    to "0","1","2"... on commit, and `quarto render` writes outputs back into the
    source. Neither is a real content change, so `--check` must ignore both or it
    reports "out of date" immediately after a regeneration.
    """
    return [
        (c.cell_type, c.source, tuple(sorted(c.metadata.get("tags", []))))
        for c in nb.cells
    ]


def module_notebooks() -> list[str]:
    """Complete module notebooks (excludes generated practice versions)."""
    return sorted(
        p
        for p in glob.glob(os.path.join(NB_DIR, "module_*.ipynb"))
        if not os.path.basename(p).replace(".ipynb", "").endswith(PRACTICE_SUFFIX)
    )


def practice_path(src_path: str) -> str:
    stem = os.path.basename(src_path)[: -len(".ipynb")]
    return os.path.join(NB_DIR, f"{stem}{PRACTICE_SUFFIX}.ipynb")


def has_code_fold(cell) -> bool:
    return any(l.strip().startswith("#| code-fold") for l in cell.source.splitlines())


def lint() -> int:
    """Catch answer cells that are about to leak.

    An answer cell needs a `code-fold` directive (so the WEBSITE hides it) and a
    `solution` marker (so THIS SCRIPT strips it). Those are set independently, so
    they can drift apart when a cell is edited, retyped, or copy-pasted. Either
    half alone is a silent failure:

      * folded but unmarked -> the answer ships in the practice notebook
      * marked but unfolded -> the answer is spoiled on the module page

    Neither shows up as a broken build, which is why this check exists.
    """
    problems = []
    for src in module_notebooks():
        nb = nbformat.read(src, as_version=4)
        rel = os.path.relpath(src, ROOT)
        for i, c in enumerate(nb.cells):
            if c.cell_type != "code":
                continue
            marked, folded = is_answer_cell(c), has_code_fold(c)
            if folded and not marked:
                problems.append(
                    f"{rel} cell {i}: has `code-fold` but no `solution` marker. "
                    f"The answer WILL leak into the practice notebook."
                )
            elif marked and not folded:
                problems.append(
                    f"{rel} cell {i}: marked `solution` but has no `code-fold`. "
                    f"The answer will be visible on the module page."
                )

    if problems:
        print("Answer-cell markers are inconsistent:")
        for p in problems:
            print(f"  ✗ {p}")
        print(
            "\nEvery answer cell needs all of:\n"
            '  #| code-fold: true\n  #| code-summary: "Show solution N.M"\n'
            "  #| tags: [solution]"
        )
        return 1

    n = sum(
        1
        for src in module_notebooks()
        for c in nbformat.read(src, as_version=4).cells
        if c.cell_type == "code" and is_answer_cell(c)
    )
    print(f"All {n} answer cell(s) are correctly marked and folded.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit non-zero if any practice notebook is missing or stale",
    )
    ap.add_argument(
        "--lint",
        action="store_true",
        help="don't write; exit non-zero if any answer cell is mis-marked (leak guard)",
    )
    args = ap.parse_args()

    if args.lint:
        return lint()

    sources = module_notebooks()
    if not sources:
        print(f"No module notebooks found in {os.path.relpath(NB_DIR, ROOT)}/")
        return 1

    stale = []
    for src in sources:
        nb = nbformat.read(src, as_version=4)
        practice, n_stubbed = build_practice(nb)
        dest = practice_path(src)
        rel_src = os.path.relpath(src, ROOT)
        rel_dest = os.path.relpath(dest, ROOT)

        if n_stubbed == 0:
            print(f"  !  {rel_src}: no cells tagged '{SOLUTION_TAG}' — nothing to strip")

        new_text = nbformat.writes(practice)
        if args.check:
            if not os.path.exists(dest):
                stale.append(f"{rel_dest} is missing")
            elif fingerprint(nbformat.reads(new_text, as_version=4)) != fingerprint(
                nbformat.read(dest, as_version=4)
            ):
                stale.append(f"{rel_dest} is out of date")
            continue

        with open(dest, "w") as f:
            f.write(new_text)
        print(f"  ✓  {rel_src}  ->  {rel_dest}  ({n_stubbed} answer cells stubbed)")

    if args.check:
        if stale:
            print("Practice notebooks are not up to date:")
            for s in stale:
                print(f"  ✗ {s}")
            print("Run: pixi run make-practice")
            return 1
        print(f"All {len(sources)} practice notebook(s) are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
