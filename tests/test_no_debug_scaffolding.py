"""Diagnostic scaffolding must not survive the bug hunt it was written for.

Apex review of PR #7 (2026-09-25, blockers 1+2): the Daevanion tooltip fix
shipped with three ``logger.debug("DAEVANION DEBUG ...")`` calls firing on
every node hover, plus a blanket ``except Exception`` wrapped around
``_daevanion_show_tooltip_impl``.  The logging was noise in a hot slot; the
catch-all was worse -- a permanent blindfold over the one code path the
next bug in it would have to surface through.

Both are the kind of thing that is invisible in review a second time, so
they are pinned here rather than remembered.  This module parses/reads
``app.py`` as TEXT: no Qt, no import of the 22k-line module.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "ItemDatabase" / "app.py"


def test_no_daevanion_debug_logging_survives() -> None:
    source = APP_PY.read_text(encoding="utf-8")
    offenders = [
        f"{n}: {line.strip()}"
        for n, line in enumerate(source.splitlines(), 1)
        if "DAEVANION DEBUG" in line
    ]
    assert not offenders, "debug scaffolding left in app.py:\n" + "\n".join(offenders)


def test_the_tooltip_slot_has_no_blanket_except() -> None:
    """``_daevanion_show_tooltip`` must let a real error surface.

    The diagnostic wrapper is gone and the ``_impl`` split with it, so the
    check is the general one: no ``except Exception``/bare ``except`` may
    reappear anywhere inside the tooltip slot.
    """
    tree = ast.parse(APP_PY.read_text(encoding="utf-8"), filename=str(APP_PY))
    slots = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("_daevanion_show_tooltip")
    ]
    assert slots, "_daevanion_show_tooltip disappeared -- update this gate"
    for slot in slots:
        for handler in (h for h in ast.walk(slot) if isinstance(h, ast.ExceptHandler)):
            caught = handler.type
            assert caught is not None, f"bare except in {slot.name}"
            assert not (isinstance(caught, ast.Name) and caught.id == "Exception"), (
                f"blanket 'except Exception' back in {slot.name} -- it swallows "
                "every future bug in the hover path"
            )
