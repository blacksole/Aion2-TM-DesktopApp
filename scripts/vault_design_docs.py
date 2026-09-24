#!/usr/bin/env python
"""Dev tool: write one Obsidian note per theme, straight from ``core.theme``.

The vault must never become a second source of truth.  A hand-maintained
colour table drifts the moment a token changes and is then worse than no
table at all -- it is confidently wrong.  So every value in the generated
notes is read out of :mod:`core.theme` at run time, including the contrast
ratios, which are computed with the app's own :func:`contrast_ratio` rather
than copied from a spreadsheet.

Re-run after any token change:

    .venv/Scripts/python.exe scripts/vault_design_docs.py

The vault path comes from ``OBSIDIAN_VAULT_PATH`` (or ``--vault``).
Everything is written into the vault's ``Appearance/`` folder; the rest of
the vault (hand-written notes under ``Design/`` and ``Branding/``) is never
touched.  Obsidian resolves ``[[wikilinks]]`` by basename, so moving these
notes into a subfolder does not break a single link.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import theme as T  # noqa: E402

STAMP = "2026-09-23"

# Which surfaces text can realistically sit on, in stacking order.
SURFACES = ("bg.window", "bg.surface", "bg.elevated", "bg.overlay")
# Which foregrounds are worth a contrast row.
FOREGROUNDS = (
    "fg",
    "fg.secondary",
    "fg.muted",
    "accent",
    "secondary",
    "ok",
    "warn",
    "danger",
)

GERMAN_ROLE = {
    "bg.window": "Fensterhintergrund, HUD-Overlay",
    "bg.surface": "Seiten, Panels",
    "bg.elevated": "Karten, alternierende Tabellenzeilen",
    "bg.overlay": "Popups, Menüs, Tooltips",
    "bg.input": "Eingabefelder",
    "border": "1px-Rahmen (Standard)",
    "border.strong": "fokussiert / ausgewählt",
    "fg": "Haupttext, Seitentitel",
    "fg.secondary": "Sekundärtext, Unterüberschriften",
    "fg.muted": "Bildunterschriften, Platzhalter, deaktiviert",
    "fg.on-accent": "Text/Icons AUF der Akzentfläche",
    "accent": "aktiv / ausgewählt, Links, Sektionsköpfe",
    "accent.hover": "Akzentelement bei Hover",
    "accent.soft": "Fläche aktiver Pills, Fokus-Schimmer",
    "secondary": "zweite Betonung, getrennt vom Akzent",
    "secondary.soft": "Badge-Fläche sekundär",
    "ok": "Erfolg / positiv",
    "warn": "Achtung / benötigt Aufmerksamkeit",
    "danger": "Fehler / kritisch",
    "ok.soft": "Badge-Fläche ok",
    "warn.soft": "Badge-Fläche warn",
    "danger.soft": "Badge-Fläche danger",
}


def _attr(token: str) -> str:
    return token.replace(".", "_").replace("-", "_")


def _val(tk: T.Tokens, token: str) -> str:
    return getattr(tk, _attr(token))


def _swatch(value: str) -> str:
    """A colour chip Obsidian renders inline (HTML is allowed in notes)."""
    return (
        f'<span style="display:inline-block;width:11px;height:11px;'
        f'background:{value};border:1px solid #8884;border-radius:2px;'
        f'vertical-align:middle"></span>'
    )


def _rate(ratio: float, *, large: bool = False) -> str:
    """WCAG verdict for a contrast ratio."""
    if ratio >= 7:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3:
        return "AA groß" if large else "nur groß"
    return "✗"


def theme_note(name: str) -> str:
    tk = T.tokens(name)
    is_default = name == T.DEFAULT_THEME
    out: list[str] = []
    a = out.append

    a("---")
    a("typ: appearance")
    a("projekt: Aion 2 Companion")
    a(f"theme: {name}")
    a(f"aktualisiert: {STAMP}")
    a("generiert: scripts/vault_design_docs.py")
    a("---")
    a("")
    a(f"# Appearance — {name.capitalize()}")
    a("")
    a("> [!warning] Generiert — nicht von Hand bearbeiten")
    a("> Erzeugt aus `core/theme.py`. Änderungen hier gehen beim nächsten Lauf")
    a("> verloren. Token ändern → `scripts/vault_design_docs.py` neu ausführen.")
    a("")
    a(f"Teil von [[Aion2 Companion]] · System: [[Design System - Aether Cockpit]]")
    a("")

    if is_default:
        a("**Standard-Theme.** Referenz für alle anderen und für Promo-Material.")
        a("")

    # ---- colours ----------------------------------------------------
    a("## Flächen (von unten nach oben)")
    a("")
    a("| | Token | Wert | Wofür |")
    a("|---|---|---|---|")
    for tok in ("bg.window", "bg.surface", "bg.elevated", "bg.overlay", "bg.input"):
        v = _val(tk, tok)
        a(f"| {_swatch(v)} | `{tok}` | `{v}` | {GERMAN_ROLE[tok]} |")
    a("")

    a("## Linien")
    a("")
    a("| | Token | Wert | Wofür |")
    a("|---|---|---|---|")
    for tok in ("border", "border.strong"):
        v = _val(tk, tok)
        a(f"| {_swatch(v)} | `{tok}` | `{v}` | {GERMAN_ROLE[tok]} |")
    a("")

    a("## Text")
    a("")
    a("| | Token | Wert | Wofür |")
    a("|---|---|---|---|")
    for tok in ("fg", "fg.secondary", "fg.muted", "fg.on-accent"):
        v = _val(tk, tok)
        a(f"| {_swatch(v)} | `{tok}` | `{v}` | {GERMAN_ROLE[tok]} |")
    a("")

    a("## Akzente")
    a("")
    a("| | Token | Wert | Wofür |")
    a("|---|---|---|---|")
    for tok in ("accent", "accent.hover", "accent.soft", "secondary", "secondary.soft"):
        v = _val(tk, tok)
        chip = _swatch(v) if v.startswith("#") else ""
        a(f"| {chip} | `{tok}` | `{v}` | {GERMAN_ROLE[tok]} |")
    a("")

    a("## Status")
    a("")
    a("| | Token | Wert | Wofür |")
    a("|---|---|---|---|")
    for tok in ("ok", "warn", "danger", "ok.soft", "warn.soft", "danger.soft"):
        v = _val(tk, tok)
        chip = _swatch(v) if v.startswith("#") else ""
        a(f"| {chip} | `{tok}` | `{v}` | {GERMAN_ROLE[tok]} |")
    a("")
    a("Status- und `fg`-Farben sind in **allen 6 Themes identisch** — nur so")
    a("bedeutet Rot überall dasselbe.")
    a("")

    # ---- contrast ---------------------------------------------------
    a("## Welche Farbe auf welchem Hintergrund")
    a("")
    a("Kontrastwerte nach WCAG, berechnet mit `core.theme.contrast_ratio`.")
    a("AAA ≥ 7 · AA ≥ 4.5 · darunter nur für große Schrift (≥ 24 px).")
    a("")
    head = "| Text ↓ / Fläche → | " + " | ".join(f"`{s}`" for s in SURFACES) + " |"
    a(head)
    a("|---|" + "---|" * len(SURFACES))
    for fg in FOREGROUNDS:
        fv = _val(tk, fg)
        cells = []
        for s in SURFACES:
            r = T.contrast_ratio(fv, _val(tk, s))
            cells.append(f"{r:.1f} {_rate(r)}")
        a(f"| `{fg}` | " + " | ".join(cells) + " |")
    a("")

    on_accent = T.contrast_ratio(tk.fg_on_accent, tk.accent)
    fg_on_accent = T.contrast_ratio(tk.fg, tk.accent)
    a("### Auf der Akzentfläche")
    a("")
    a("| Text | auf `accent` | Urteil |")
    a("|---|---|---|")
    a(f"| `fg.on-accent` `{tk.fg_on_accent}` | **{on_accent:.2f}** | {_rate(on_accent)} — richtig |")
    a(f"| `fg` `{tk.fg}` | {fg_on_accent:.2f} | ✗ **niemals** |")
    a("")
    a("> [!tip] Die Regel, die man am häufigsten falsch macht")
    a("> Heller Text auf einer Akzentfläche ist unlesbar. Auf Akzent kommt")
    a("> **immer** `fg.on-accent` — dunkles Navy, in allen sechs Themes.")
    a("> `accent.soft` ist dagegen nur ein Hauch über dunklem Grund, dort")
    a("> bleibt normaler `fg`-Text richtig.")
    a("")

    # ---- hue separation --------------------------------------------
    a("## Farbton-Abstand Akzent ↔ Status")
    a("")
    if tk.accent.startswith("#"):
        import colorsys

        def hue(h: str) -> float:
            h = h.lstrip("#")
            r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
            return colorsys.rgb_to_hsv(r, g, b)[0] * 360

        ah = hue(tk.accent)
        sat = colorsys.rgb_to_hsv(
            *(int(tk.accent.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
        )[1]
        if sat < 0.1:
            a("Akzent ist **neutral** (keine Buntheit) — die Trennung zu den")
            a("Statusfarben läuft hier über Sättigung, nicht über Farbton.")
            a("Das ist in Ordnung und braucht keine Gradzahl.")
        else:
            a("| gegen | Abstand | |")
            a("|---|---|---|")
            worst = 360.0
            for tok in ("ok", "warn", "danger"):
                d = abs(ah - hue(_val(tk, tok)))
                d = min(d, 360 - d)
                worst = min(worst, d)
                flag = "✗ zu nah" if d < 30 else "ok"
                a(f"| `{tok}` | {d:.0f}° | {flag} |")
            a("")
            if worst < 30:
                a(f"> [!danger] Engste Trennung: {worst:.0f}°")
                a("> Unter ~30° lesen sich zwei Rollen auf einer Badge-Zeile als")
                a("> dieselbe Farbe. Siehe [[Offene Design-Entscheidungen]].")
            else:
                a(f"Engste Trennung **{worst:.0f}°** — ausreichend.")
    a("")

    a("## Fokus")
    a("")
    a(f"- Ring = immer der Akzent dieses Themes (`{tk.accent}`), abgeleitet, nie gespeichert")
    a(f"- Breite `{tk.focus_ring_width}px`, Versatz `{tk.focus_ring_offset}px`")
    a("- Der Ring ist eine **Border auf der Kante**, kein Outline drumherum —")
    a("  Qt kann außerhalb des Widget-Rects nicht zeichnen")
    a("- Das Padding gibt exakt die Differenz zurück (`*_inset`-Tokens), sonst")
    a("  springt die ganze Zeile beim Fokussieren")
    a("")
    a("---")
    a("")
    a("Andere Appearances: " + " · ".join(
        f"[[{n.capitalize()}]]" for n in T.THEMES if n != name
    ))
    a("")
    a("Übersicht: [[Appearances]]")
    return "\n".join(out) + "\n"


def typography_note() -> str:
    tk = T.tokens(T.DEFAULT_THEME)
    out: list[str] = []
    a = out.append
    a("---")
    a("typ: appearance")
    a("projekt: Aion 2 Companion")
    a(f"aktualisiert: {STAMP}")
    a("generiert: scripts/vault_design_docs.py")
    a("---")
    a("")
    a("# Schrift, Maß & Bewegung")
    a("")
    a("> [!warning] Generiert — nicht von Hand bearbeiten")
    a("> Erzeugt aus `core/theme.py`.")
    a("")
    a("Teil von [[Aion2 Companion]] · System: [[Design System - Aether Cockpit]]")
    a("")
    a("Diese Werte sind **themeunabhängig** — in allen 6 Appearances gleich.")
    a("")
    a("## Schriftfamilien")
    a("")
    a("| Rolle | Stack | Verwendung |")
    a("|---|---|---|")
    a(f"| `font.display` | `{tk.font_display}` | Seitentitel, große Zahlen, HUD-Sektionen |")
    a(f"| `font.body` | `{tk.font_body}` | Fließtext, Buttons, Labels |")
    a(f"| `font.mono` | `{tk.font_mono}` | Timer, GearScore, Stat-Spalten, Pfade |")
    a("")
    a("Alle OFL-lizenziert, eingebettet in `assets/fonts/`, geladen von `core/fonts.py`.")
    a("Der Fallback greift nur, wenn die Registrierung scheitert.")
    a("")
    a("> [!note] JetBrains Mono ist variabel")
    a("> `google/fonts` liefert keine statischen Schnitte — eingebettet ist")
    a("> `JetBrainsMono[wght].ttf` (Achse 100–800), genutzt werden 400 und 500.")
    a("")
    a("## Gewichte")
    a("")
    a("| Token | Wert |")
    a("|---|---|")
    for lbl, attr in (
        ("regular", "font_weight_regular"),
        ("medium", "font_weight_medium"),
        ("semibold", "font_weight_semibold"),
        ("bold", "font_weight_bold"),
    ):
        a(f"| `font.weight.{lbl}` | {getattr(tk, attr)} |")
    a("")
    a("> [!danger] Gewicht nie allein im QSS setzen")
    a("> `QPushButton` berechnet seinen `sizeHint` aus der **Widget**-Schrift.")
    a("> Ein `font-weight` nur im Stylesheet malt breiter als die reservierte")
    a("> Breite → der Text wird an beiden Rändern abgeschnitten.")
    a("> Real passiert am 2026-09-23, siehe [[Design Log]].")
    a("")
    a("## Größen")
    a("")
    a("| Token | px | Verwendung |")
    a("|---|---|---|")
    sizes = [
        ("xs", tk.text_xs, "Versal-Labels, Badges, Tabellenköpfe"),
        ("sm", tk.text_sm, "dichte Nebeninfo"),
        ("base", tk.text_base, "Fließtext — Minimum für Lesetext"),
        ("md", tk.text_md, "Sektionsüberschriften"),
        ("lg", tk.text_lg, "Unterüberschrift"),
        ("xl", tk.text_xl, "Seitenüberschrift klein"),
        ("2xl", tk.text_2xl, "Dialog-/Seitentitel"),
        ("display", tk.text_display, "Haupttitel, große Kennzahlen"),
    ]
    for tok, px, use in sizes:
        a(f"| `text.{tok}` | {px} | {use} |")
    a("")
    a(f"- Versal-Labels: {tk.text_xs} px mit `letter-spacing: {tk.letter_spacing_caps}`")
    a(f"- Zeilenhöhe: `{tk.line_height}`")
    a("")
    a("## Abstände")
    a("")
    a("| Token | px |")
    a("|---|---|")
    for n in (1, 2, 3, 4, 6, 8):
        a(f"| `space.{n}` | {getattr(tk, f'space_{n}')} |")
    a("")
    a("## Radien, Rahmen, Schatten")
    a("")
    a("| Token | Wert | Verwendung |")
    a("|---|---|---|")
    a(f"| `radius.sm` | {tk.radius_sm}px | Inputs, Pills, Badges |")
    a(f"| `radius.md` | {tk.radius_md}px | Karten, Panels |")
    a(f"| `radius.full` | {tk.radius_full}px | Avatare |")
    a(f"| `border.width` | {tk.border_width}px | überall |")
    a(f"| `shadow.popup` | `{tk.shadow_popup}` | **nur** Popups/Tooltips |")
    a("")
    a("Karten bekommen **keinen** Schatten — sie haben eine Flächen-Ebene.")
    a("")
    a("## Bewegung")
    a("")
    a("| Token | Wert | Wofür |")
    a("|---|---|---|")
    a(f"| `motion.fast` | {tk.motion_fast}ms | Hover, Pressed, Toggle |")
    a(f"| `motion.base` | {tk.motion_base}ms | Karte/Toast ein- und ausblenden |")
    a(f"| `motion.slow` | {tk.motion_slow}ms | Seitenwechsel (nur Deckkraft) |")
    a(f"| `motion.ease` | `{tk.motion_ease}` | alles |")
    a(f"| `motion.offset` | {tk.motion_offset}px | Versatz beim Ein-/Ausgang |")
    a("")
    a("Nur **Deckkraft + Versatz**. Verboten: `width`/`height`/`geometry`")
    a("animieren, Dauerschleifen, Weichzeichner.")
    a("Die Einstellung „Animationen reduzieren\" setzt alle Dauern auf 0 —")
    a("nicht verhandelbar.")
    return "\n".join(out) + "\n"


def data_colors_note() -> str:
    out: list[str] = []
    a = out.append
    a("---")
    a("typ: appearance")
    a("projekt: Aion 2 Companion")
    a(f"aktualisiert: {STAMP}")
    a("generiert: scripts/vault_design_docs.py")
    a("---")
    a("")
    a("# Datenfarben")
    a("")
    a("> [!warning] Generiert — nicht von Hand bearbeiten")
    a("")
    a("Teil von [[Aion2 Companion]] · System: [[Design System - Aether Cockpit]]")
    a("")
    a("Farben, die die **Daten** bestimmen, nicht das Theme — eine Item-")
    a("Seltenheit ist in Inferno dieselbe wie in Abyss, sonst verlöre sie ihre")
    a("Bedeutung. Deshalb sind sie themeunabhängig und laufen über")
    a("`theme.data_color(kind, key)` statt über einen Token.")
    a("")
    a("Unbekannter Schlüssel → `fg.muted` statt Absturz: Kataloge wachsen,")
    a("die UI darf daran nicht zerbrechen.")
    a("")
    labels = {
        "item_grade": "Item-Seltenheit",
        "gear_type": "Ausrüstungstyp",
        "timer": "Timer-Kategorie",
        "timer_swatch": "Timer-Farbwähler",
        "role": "Rolle",
        "skill_type": "Skill-Typ",
        "craft_method": "Herstellungsart",
        "damage_type": "Schadensart",
        "arcana_theme": "Arcana-Thema",
        "arcana_category": "Arcana-Kategorie",
        "arcana_category_deep": "Arcana-Kategorie (dunkel)",
        "genius_board": "Genius-Board",
        "spec_state": "Spec-Zustand",
    }
    for kind, label in labels.items():
        try:
            keys = T.data_color_keys(kind)
        except KeyError:
            continue
        a(f"## {label} — `{kind}`")
        a("")
        a("| | Schlüssel | Wert |")
        a("|---|---|---|")
        for k in keys:
            v = T.data_color(kind, k)
            chip = _swatch(v) if v.startswith("#") else ""
            a(f"| {chip} | `{k}` | `{v}` |")
        a("")
    return "\n".join(out) + "\n"


def index_note() -> str:
    out: list[str] = []
    a = out.append
    a("---")
    a("typ: appearance")
    a("projekt: Aion 2 Companion")
    a(f"aktualisiert: {STAMP}")
    a("generiert: scripts/vault_design_docs.py")
    a("---")
    a("")
    a("# Appearances — Übersicht")
    a("")
    a("Teil von [[Aion2 Companion]] · System: [[Design System - Aether Cockpit]]")
    a("")
    a("> [!warning] Generierte Notizen")
    a("> Alle `Appearance - *`-Notizen stammen aus `core/theme.py`.")
    a("> Nach einer Token-Änderung neu erzeugen:")
    a("> ```sh")
    a("> .venv/Scripts/python.exe scripts/vault_design_docs.py")
    a("> ```")
    a("")
    a("## Die sechs Appearances")
    a("")
    a("| Theme | | accent | | secondary | | Fenster |")
    a("|---|---|---|---|---|---|---|")
    for n in T.THEMES:
        tk = T.tokens(n)
        star = " ⭐" if n == T.DEFAULT_THEME else ""
        a(
            f"| [[{n.capitalize()}]]{star} | {_swatch(tk.accent)} | `{tk.accent}` "
            f"| {_swatch(tk.secondary)} | `{tk.secondary}` "
            f"| {_swatch(tk.bg_window)} `{tk.bg_window}` |"
        )
    a("")
    a("⭐ = Standard, Referenz für Promo-Material.")
    a("")
    a("## Themeunabhängig")
    a("")
    a("- [[Schrift, Maß & Bewegung]] — Schriften, Größen, Abstände, Motion")
    a("- [[Datenfarben]] — Seltenheit, Rollen, Timer u. a.")
    a("")
    a("## Was ein Theme überhaupt ändern darf")
    a("")
    a("Nur diese Tokens:")
    a("")
    for k in sorted(T.THEME_OVERRIDABLE_KEYS):
        a(f"- `{k.replace('_', '.')}`")
    a("")
    a("Alles andere erbt von Abyss. Insbesondere `fg`, `ok`, `warn`, `danger`")
    a("und `fg.on-accent` sind **überall gleich** — ein Theme darf die")
    a("Bedeutung einer Farbe nicht verschieben.")
    a("")
    a("## Ableitungsregeln")
    a("")
    a("Damit das siebte Theme ohne Diskussion entsteht:")
    a("")
    a("| Token | Regel |")
    a("|---|---|")
    a("| `accent.hover` | Ton 300 des Akzents |")
    a("| `accent.soft` | Akzent mit Alpha 0.14 |")
    a("| `secondary.soft` | Sekundär mit Alpha 0.16 |")
    a("| `bg.elevated` / `bg.overlay` | setzen die Flächenskala des Themes fort (gleiche Luminanzschritte wie Abyss) |")
    a("| `bg.input` | = `bg.window` |")
    a("| `border` / `border.strong` | aus der `bg.*`-Familie des Themes, ein bzw. zwei Stufen über `bg.overlay` |")
    a("")
    a("Invariante, per Test bewacht:")
    a("`bg.elevated < border < border.strong < fg.muted` in der Luminanz —")
    a("ein Rahmen muss sichtbar sein, darf sich aber nie wie Text lesen.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vault", type=Path, default=None)
    args = p.parse_args(argv)

    vault = args.vault or Path(os.environ.get("OBSIDIAN_VAULT_PATH", ""))
    if not vault or not vault.is_dir():
        print(
            "Vault-Pfad unbekannt. OBSIDIAN_VAULT_PATH setzen oder --vault angeben.",
            file=sys.stderr,
        )
        return 2

    # Alles Generierte lebt in einem Ordner -- so ist auf einen Blick klar,
    # was Maschine und was Mensch geschrieben hat.
    out_dir = vault / "Appearance"
    out_dir.mkdir(exist_ok=True)

    written: list[Path] = []
    for name in T.THEMES:
        path = out_dir / f"{name.capitalize()}.md"
        path.write_text(theme_note(name), encoding="utf-8")
        written.append(path)

    for fname, body in (
        ("Schrift, Maß & Bewegung.md", typography_note()),
        ("Datenfarben.md", data_colors_note()),
        ("Appearances.md", index_note()),
    ):
        path = out_dir / fname
        path.write_text(body, encoding="utf-8")
        written.append(path)

    for path in written:
        print(f"  Appearance/{path.name}  ({path.stat().st_size:,} B)")
    print(f"\n{len(written)} Notizen geschrieben nach {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
