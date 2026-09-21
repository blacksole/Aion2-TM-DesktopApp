#!/usr/bin/env python3
"""Generate the per-theme chevrons the QSS draws, from MASTER's tokens.

Run from the repo root::

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/gen_tinted_icons.py

QSS ``image: url(...)`` loads a file exactly as it is on disk -- it cannot
tint, recolour or mask it.  That is why the sheet used to point at two baked
**orange** PNGs (``assets/icons/arrow_{down,up}_orange.png``), which read as a
warm accent on Abyss, Emerald and Void and had been sitting in MASTER's
« Décisions différées » ever since: « Corriger demande des icônes par thème
ou teintées à l'exécution ».

Per theme, then -- but *when*?  Three options, and only one of them works:

* **at runtime, into the install directory** — writes into the app bundle,
  which is read-only on a packaged install (and on any sane deployment).
* **at runtime, into the user cache dir** — writable, but unreachable: the
  sheet addresses files through the ``ASSET_PATH`` marker, and ASSET_PATH is
  the *bundle* root (``sys._MEIPASS``), not the cache.  Pointing the sheet
  at the cache would need a second placeholder resolved by ``core/theme.py``.
* **at build time, committed** — six themes × four chevrons = 24 files of
  ~250 bytes.  No new placeholder, no write at startup, nothing to
  invalidate, and the files are reviewable in a diff.

The third one is what this script does.  Regenerate it whenever a theme's
``fg.muted`` changes; ``tests/test_icons.py`` fails if the committed files
and the tokens ever disagree, so it cannot silently go stale.

``fg.muted`` and not the accent: MASTER §3 says an icon inherits ``fg.*``,
and a dropdown chevron is an affordance, not a call to action.  MASTER §2
guarantees ``fg.muted`` ≥ 4.5:1 on ``bg.surface``; these arrows sit on
``bg.input``, which is ``bg.window`` -- darker still, so the margin is wider
than the guarantee.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core import theme  # noqa: E402
from ui.widgets import icons  # noqa: E402

#: The chevrons the sheet needs (combo ``::down-arrow``, spin box
#: ``::up-arrow``/``::down-arrow``) plus their two siblings, so a future
#: horizontal control does not have to re-run a generator to get one.
CHEVRONS: tuple[str, ...] = (
    "chevron-down",
    "chevron-up",
    "chevron-left",
    "chevron-right",
)

#: MASTER §3 — an icon's colour is inherited from ``fg.*``.  Two variants,
#: because one of them is the reason the per-theme layout is not ceremony:
#:
#: * ``fg.muted`` at rest.  MASTER §2 does NOT let a theme redefine any
#:   ``fg.*`` token, so this one resolves to the same grey in all six --
#:   the six directories hold the same bytes today, on purpose (see below);
#: * ``accent`` under the cursor.  THAT one is a different colour in every
#:   theme, which is what the ``{{name}}`` in the sheet actually selects
#:   between, and what gives the control back the bit of colour the orange
#:   PNG used to carry -- this time the theme's own colour rather than one
#:   bitmap's idea of it.
#:
#: Keeping the resting variant per theme anyway costs 5.5 kB and means the
#: sheet needs no edit the day a theme is allowed its own ``fg.muted``.
ARROW_TOKEN = "fg.muted"
ARROW_HOVER_TOKEN = "accent"

#: Suffix of the hovered variant: ``chevron-down-accent.svg``.
HOVER_SUFFIX = "-accent"


def generate(root: Path | None = None) -> list[Path]:
    """Write ``<tinted>/<theme>/<chevron>[-accent].svg``; return every path."""
    base = Path(root) if root is not None else icons.tinted_dir()
    written: list[Path] = []
    for name in sorted(theme.THEMES):
        tokens = theme.tokens(name)
        out_dir = base / name
        out_dir.mkdir(parents=True, exist_ok=True)
        for token, suffix in ((ARROW_TOKEN, ""), (ARROW_HOVER_TOKEN, HOVER_SUFFIX)):
            color = theme.qcolor(tokens, token).name()
            for chevron in CHEVRONS:
                source = (icons.icon_dir() / f"{chevron}.svg").read_text(encoding="utf-8")
                target = out_dir / f"{chevron}{suffix}.svg"
                target.write_text(icons.tint(source, color), encoding="utf-8")
                written.append(target)
    return written


def main() -> int:
    written = generate()
    total = sum(p.stat().st_size for p in written)
    print(f"wrote {len(written)} tinted chevrons ({total} bytes) under {icons.tinted_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
