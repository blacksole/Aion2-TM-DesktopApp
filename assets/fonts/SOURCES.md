# Bundled fonts — provenance

All three families are under the **SIL Open Font License 1.1** (OFL), which
permits bundling and redistribution inside an application. Each family's
license text is next to its files (`OFL-<Family>.txt`).

Fetched **2026-09-18** with plain `curl -fsSL` (no `curl | sh`) from
`raw.githubusercontent.com/google/fonts` at branch `main`.

| File | Weight | Source URL |
|---|---|---|
| `Barlow-Regular.ttf` | 400 | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlow/Barlow-Regular.ttf> |
| `Barlow-Medium.ttf` | 500 | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlow/Barlow-Medium.ttf> |
| `Barlow-SemiBold.ttf` | 600 | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlow/Barlow-SemiBold.ttf> |
| `BarlowCondensed-SemiBold.ttf` | 600 | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/BarlowCondensed-SemiBold.ttf> |
| `BarlowCondensed-Bold.ttf` | 700 | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/BarlowCondensed-Bold.ttf> |
| `JetBrainsMono[wght].ttf` | variable 100–800 (covers 400/500) | <https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf> |

Licenses:

| File | Source URL |
|---|---|
| `OFL-Barlow.txt` | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlow/OFL.txt> |
| `OFL-BarlowCondensed.txt` | <https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/OFL.txt> |
| `OFL-JetBrainsMono.txt` | <https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/OFL.txt> |

## Deviation from MASTER §1

MASTER asks for JetBrains Mono as **static** 400/500 TTFs. `google/fonts`
only ships the **variable** file for that family (`ofl/jetbrainsmono/`
contains `JetBrainsMono[wght].ttf` and `JetBrainsMono-Italic[wght].ttf`,
nothing static), so the variable roman file is bundled instead — one file
covering both required weights, 187 KB. Recorded in MASTER §2 under
"Typographie — fichiers réellement embarqués".

Italics are deliberately not bundled: MASTER uses none.

Total: 723 KB of TTF (budget: 2 MB).
