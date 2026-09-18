# Aion2 TM — Design System « Aether Cockpit »

**Statut** : source de vérité. Toute couleur, taille ou durée dans le code vient d'ici via `core/theme.py`. Aucun hex magique dans `ui/` ou `ItemDatabase/`.
**Décidé le** : 2026-09-18 (genjutsu paint, thèses validées par Florian).
**Stack** : PySide6 6.11 · QSS généré depuis un template + tokens · painters via `QColor` exposés par `core/theme.py`.

## Thèses

- **Visuelle** : navy stratifié en 4 niveaux de surface, un seul accent (cyan) pour « actif / important », couleurs sémantiques distinctes de l'accent, typographie condensée pour titres et gros chiffres, mono pour timers et stats, zéro dégradé décoratif.
- **Interaction** : le mouvement confirme un changement d'état, 120–180 ms, opacité + translation 4–8 px uniquement, jamais de largeur/hauteur animée, désactivable (réglage « Réduire les animations »).

## 1. Primitifs

### Couleurs (thème de référence : Abyss)

| Token | Hex | Usage brut |
|---|---|---|
| `navy.950` | `#0b1120` | fond de fenêtre |
| `navy.900` | `#0f172a` | surface 1 |
| `navy.850` | `#151e33` | surface 2 |
| `navy.800` | `#1c2740` | surface 3 |
| `navy.700` | `#26324a` | bordure |
| `navy.600` | `#3b4863` | bordure forte / séparateur actif |
| `slate.400` | `#94a3b8` | texte muet |
| `slate.300` | `#c3cadb` | texte secondaire |
| `slate.100` | `#e5e7eb` | texte principal |
| `cyan.400` | `#22d3ee` | accent |
| `cyan.300` | `#67e8f9` | accent hover |
| `cyan.900a` | `rgba(34,211,238,0.14)` | accent soft (fond de pill active, focus glow) |
| `violet.400` | `#a78bfa` | secondaire |
| `violet.900a` | `rgba(167,139,250,0.16)` | secondaire soft |
| `green.400` | `#4ade80` | ok |
| `amber.400` | `#fbbf24` | attention |
| `red.400` | `#f87171` | critique |
| `green.900a` / `amber.900a` / `red.900a` | alpha 0.16 des trois ci-dessus | fonds de badge |

### Typographie (OFL, embarquée dans `assets/fonts/`, chargée par `core/fonts.py`)

| Token | Famille | Poids | Usage |
|---|---|---|---|
| `font.display` | Barlow Condensed | 600 / 700 | titres de page, gros chiffres (résumé, HUD) |
| `font.body` | Barlow | 400 / 500 / 600 | tout le texte courant, boutons, labels |
| `font.mono` | JetBrains Mono | 400 / 500 | timers, GearScore, colonnes de stats, chemins |
| fallback | `Segoe UI`, `Noto Sans`, `sans-serif` · mono : `Consolas`, `DejaVu Sans Mono` | | si le chargement échoue |

Échelle (px) : `xs 11` · `sm 12` · `base 13` · `md 14` · `lg 16` · `xl 20` · `2xl 26` · `display 34`.
Corps à 13 px minimum, labels majuscules en 11 px avec `letter-spacing 0.06em`, `line-height ≈ 1.45`.

### Espacement, rayons, ombres

- Espace : `1 = 4` · `2 = 8` · `3 = 12` · `4 = 16` · `6 = 24` · `8 = 32`.
- Rayons : `sm = 4` (inputs, pills, badges) · `md = 6` (cartes, panneaux) · `full` (avatars).
- Ombre : une seule, `0 6px 18px rgba(0,0,0,0.35)`, réservée aux popups/tooltips. Les cartes n'ont pas d'ombre, elles ont un niveau de surface.
- Bordures : 1 px `border` partout, `border.strong` pour l'élément focalisé ou sélectionné.

### Motion

| Token | Valeur | Usage |
|---|---|---|
| `motion.fast` | 120 ms | hover, pressed, toggle |
| `motion.base` | 160 ms | apparition/disparition d'une carte, toast |
| `motion.slow` | 220 ms | changement de page (opacité seule) |
| `motion.ease` | `QEasingCurve.OutCubic` | tout |
| `motion.offset` | 6 px | translation d'entrée/sortie |
| `motion.reduced` | réglage utilisateur → toutes les durées à 0 | accessibilité, non négociable |

Interdits : animer `width`/`height`/`geometry` d'un layout, animations décoratives en boucle, effets de flou.

## 2. Sémantique (ce que le code utilise)

| Token | Abyss | Rôle |
|---|---|---|
| `bg.window` | navy.950 | fond de la fenêtre principale et de l'overlay |
| `bg.surface` | navy.900 | pages, panneaux |
| `bg.elevated` | navy.850 | cartes, lignes de tableau alternées |
| `bg.overlay` | navy.800 | popups, menus, tooltips |
| `bg.input` | navy.950 | champs de saisie |
| `border` | navy.700 | |
| `border.strong` | navy.600 | |
| `fg` | slate.100 | texte principal |
| `fg.secondary` | slate.300 | |
| `fg.muted` | slate.400 | placeholders, hints (≥ 4.5:1 sur bg.surface) |
| `fg.on-accent` | navy.950 | texte sur accent — **jamais blanc sur cyan** |
| `accent` | cyan.400 | actif, sélection, CTA primaire, focus |
| `accent.hover` | cyan.300 | |
| `accent.soft` | cyan.900a | fond de pill/onglet actif, glow de focus |
| `secondary` | violet.400 | badges de schedule, Flow Map, liens |
| `secondary.soft` | violet.900a | |
| `ok` / `warn` / `danger` | green.400 / amber.400 / red.400 | complété, attention, MISSED / destructif |
| `ok.soft` / `warn.soft` / `danger.soft` | alphas | fonds de badge |
| `focus.ring` | accent, 2 px, offset 1 px | tout widget focalisable, tous les thèmes |

### Thèmes = mêmes tokens sémantiques, autre jeu de valeurs

Chaque thème redéfinit **au plus** : `accent`, `accent.hover`, `accent.soft`, `secondary`, `secondary.soft`, la famille `bg.*`, et — depuis le 2026-09-18 — `border` / `border.strong`. Tout le reste est hérité d'Abyss. Un thème ne peut pas redéfinir `ok/warn/danger` ni `fg.on-accent` sans re-vérifier le contraste (test automatique).

| Thème | accent | secondary | bg.window / bg.surface |
|---|---|---|---|
| Abyss (réf.) | `#22d3ee` | `#a78bfa` | `#0b1120` / `#0f172a` |
| Inferno | `#f97316` | `#fda4af` | `#140c0c` / `#1c1010` |
| Emerald | `#2dd4bf` | `#c4b5fd` | `#081410` / `#0c1a15` |
| Frostbite | `#7dd3fc` | `#c4b5fd` | `#0b1220` / `#101a2e` |
| Obsidian | `#e5e7eb` (accent neutre, on-accent = navy.950) | `#94a3b8` | `#0a0a0c` / `#111114` |
| Void | `#c084fc` | `#f472b6` | `#0c0a14` / `#120f1e` |

#### Révision des accents (2026-09-18, wave de câblage)

Deux thèmes avaient un accent que l'œil confondait avec une couleur
sémantique. Le contraste n'y voit rien — les paires du §2 passaient — mais le
sens, lui, était perdu : deux rôles, une seule couleur perçue.

| Thème | Avant | Après | Pourquoi |
|---|---|---|---|
| Emerald | accent `#34d399`, secondary `#a3e635` | accent `#2dd4bf` (teal), secondary `#c4b5fd` (lavande) | `ok` vaut `#4ade80` : avec un accent vert **et** un secondaire lime, « complété », « actif » et « schedule » rendaient la même teinte. Le teal met ~30° entre l'accent et `ok` ; la lavande sort le secondaire de la famille verte (et rejoint Frostbite, ce qui est cohérent, pas paresseux : le secondaire n'est pas l'identité d'un thème, l'accent l'est). |
| Inferno | accent `#fb923c` | accent `#f97316` | `warn` vaut `#fbbf24` : l'orange 400 en était à ~14° — « attention » et « actif » se ressemblaient sur une ligne de badges. L'orange 500 creuse l'écart et garde `fg.on-accent` à 6.72:1 (contre 8.44:1, seuil 4.5). |

`accent.hover` et `accent.soft` sont re-dérivés par la règle du §2 (teinte 300
de l'accent ; accent à alpha 0.14) : Emerald → `#5eead4` / `rgba(45,212,191,0.14)`,
Inferno → `#fdba74` / `rgba(249,115,22,0.14)`.

#### Bordures par thème (ajout 2026-09-18)

`border` et `border.strong` étaient hérités d'Abyss, donc **navy** : une ligne
froide dessinée autour de chaque carte d'un thème rouge (Inferno) ou vert
(Emerald). Une bordure appartient à la famille `bg.*` de son thème — elle
prolonge l'échelle de surfaces, elle ne s'y superpose pas. Les deux tokens
entrent donc dans le périmètre redéfinissable, avec les valeurs ci-dessous
(dérivées de chaque famille `bg.*`, un cran et deux crans au-dessus de
`bg.overlay`).

| Thème | border | border.strong |
|---|---|---|
| Abyss (réf.) | `#26324a` (navy.700) | `#3b4863` (navy.600) |
| Inferno | `#3a2222` | `#4f2e2e` |
| Emerald | `#173026` | `#224536` |
| Frostbite | `#223354` | `#2f4670` |
| Obsidian | `#26262c` | `#3a3a44` |
| Void | `#2a2140` | `#3b2f5c` |

Aucune paire de contraste du §2 ne concerne une bordure (ce sont des lignes de
1 px, non-texte), mais l'invariant qui les tient est testé :
`bg.elevated < border < border.strong < fg.muted` en luminance, dans les six
thèmes — une bordure doit se voir sur la carte qu'elle entoure sans jamais se
lire comme du texte (`tests/test_theme.py::test_borders_sit_between_the_surfaces_and_the_text`).

Valeurs de départ : reprises des blocs QSS actuels, à ajuster **uniquement** si le test de contraste échoue (`fg.on-accent` sur `accent` ≥ 4.5:1, `fg.muted` sur `bg.surface` ≥ 4.5:1, `fg` sur `bg.elevated` ≥ 7:1).

#### Valeurs complètes par thème (ajout 2026-09-18, implémentation `core/theme.py`)

Le tableau ci-dessus ne fixait que `accent`, `secondary`, `bg.window` et `bg.surface` : les quatre tokens restants du périmètre autorisé (`accent.hover`, `accent.soft`, `secondary.soft`, et le reste de la famille `bg.*`) manquaient. Complétés ici plutôt qu'inventés en ligne dans le code.

| Thème | accent.hover | accent.soft | secondary.soft | bg.elevated | bg.overlay | bg.input |
|---|---|---|---|---|---|---|
| Abyss | `#67e8f9` | `rgba(34,211,238,0.14)` | `rgba(167,139,250,0.16)` | `#151e33` | `#1c2740` | `#0b1120` |
| Inferno | `#fdba74` | `rgba(249,115,22,0.14)` | `rgba(253,164,175,0.16)` | `#241616` | `#2e1c1c` | `#140c0c` |
| Emerald | `#5eead4` | `rgba(45,212,191,0.14)` | `rgba(196,181,253,0.16)` | `#11231c` | `#172d24` | `#081410` |
| Frostbite | `#bae6fd` | `rgba(125,211,252,0.14)` | `rgba(196,181,253,0.16)` | `#17233b` | `#1e2c49` | `#0b1220` |
| Obsidian | `#f8fafc` | `rgba(229,231,235,0.14)` | `rgba(148,163,184,0.16)` | `#18181c` | `#212126` | `#0a0a0c` |
| Void | `#d8b4fe` | `rgba(192,132,252,0.14)` | `rgba(244,114,182,0.16)` | `#1a1528` | `#231c34` | `#0c0a14` |

Règles de dérivation (une seule, pour que le prochain thème s'ajoute sans arbitrage) : `accent.hover` = la teinte 300 de l'accent ; `accent.soft` = l'accent à alpha 0.14, `secondary.soft` = le secondaire à alpha 0.16 (mêmes alphas qu'Abyss) ; `bg.elevated` et `bg.overlay` prolongent l'échelle propre au thème avec les mêmes écarts de luminance qu'Abyss (950→900→850→800) ; `bg.input` = `bg.window`, comme Abyss.

**Note contraste (re-vérifiée le 2026-09-18 après la révision des accents, `tests/test_qss_contrast.py`)** : les six thèmes passent toujours les paires du §2 avec de la marge. `fg.on-accent` sur `accent` va de 6.72:1 (Inferno, le plus serré depuis le passage à l'orange 500) à 15.21:1 (Obsidian) ; le minimum toutes paires confondues reste 4.53:1 (`danger` sur `danger.soft`, Frostbite, seuil 3:1). `fg.on-accent` reste `navy.950` dans les six thèmes, y compris Obsidian dont l'accent est quasi blanc.

#### Typographie — fichiers réellement embarqués (ajout 2026-09-18)

`assets/fonts/` contient les statiques Barlow 400/500/600 et Barlow Condensed 600/700 depuis `google/fonts`. **JetBrains Mono n'existe pas en statique dans `google/fonts`** (le dépôt ne publie que la variable `JetBrainsMono[wght].ttf`, axe 100–800) : c'est ce fichier qui est embarqué, il couvre 400 et 500. URLs exactes et licences OFL dans `assets/fonts/SOURCES.md`.

## 3. Composants (règles, pas de nouveaux widgets)

| Composant | Règle |
|---|---|
| Bouton primaire | fond `accent`, texte `fg.on-accent`, pas de dégradé ; hover `accent.hover` ; pressed : translation 0, opacité 0.9 |
| Bouton secondaire / pill | fond `bg.elevated`, bordure `border`, texte `fg.secondary` ; actif : fond `accent.soft`, bordure `accent`, texte `fg` |
| Bouton destructif | contour `danger`, texte `danger`, fond transparent ; hover fond `danger.soft` ; toujours suivi d'une confirmation ou d'un undo |
| Carte (tâche, shopping, item) | fond `bg.elevated`, bordure `border`, rayon `md`, padding `3` ; focus : `focus.ring` ; complétée : titre `fg.muted` + coche `ok` |
| Badge | 11 px majuscules, rayon `sm`, fond `*.soft`, texte couleur pleine ; schedule → `secondary`, MISSED → `danger`, priorité → texte seul |
| Champ | fond `bg.input`, bordure `border`, focus `accent` ; placeholder `fg.muted` |
| Sidebar | item actif : fond `accent.soft`, barre gauche 2 px `accent`, texte `fg` ; jamais indigo fixe |
| Onglets/pills de page | même règle que pill ; un seul style d'onglet dans toute l'app (les QTabWidget natifs adoptent ce style) |
| Toast | fond `bg.overlay`, bordure `border.strong`, texte `fg`, bouton d'action en texte `accent` ; entrée/sortie `motion.base` |
| Tableau | en-têtes 11 px majuscules `fg.muted`, lignes alternées `bg.surface`/`bg.elevated`, chiffres en `font.mono` alignés à droite |
| Overlay HUD | fond `bg.window` avec alpha réglable **par section**, texte toujours opaque ; sections en `font.display` 14 px ; timers en `font.mono` |
| État vide | icône Lucide 24 px `fg.muted`, titre `font.body 500 fg.secondary`, hint `fg.muted`, action en bouton secondaire |
| Icônes | Lucide (ISC), 16/20/24 px, couleur héritée via `fg.*` ; aucun emoji comme icône |

## 4. Règles d'implémentation

1. `core/theme.py` : `THEMES: dict[str, Tokens]`, `tokens(theme) -> Tokens`, `qcolor(token)`, `build_qss(theme) -> str` depuis `ui/styles.template.qss` (`{{token}}`), `apply(app, theme)`.
2. `ui/styles.qss` disparaît au profit du template ; aucun bloc `[theme=…]` dupliqué.
3. Les painters (overlay, flow map, tooltips Armory, delegates) prennent leurs couleurs par `theme.qcolor("…")`, jamais par littéral.
4. `setStyleSheet(...)` inline → `setObjectName` + règle dans le template. Exception tolérée : couleur pilotée par la donnée (grade d'item, couleur de timer personnalisée), qui passe alors par `theme.data_color(...)`.
5. Test de contraste automatique sur les 6 thèmes (paires du §2). Test de rendu : grab offscreen des pages principales par thème, pas de texte élidé en EN.
6. Motion : un helper `ui/motion.py` (`fade_in(widget)`, `fade_out(widget, then)`, `slide_hint(widget)`) qui lit `motion.*` et respecte `motion.reduced`. Aucune autre animation ailleurs.

## Journal d'implémentation

### 2026-09-18 — câblage du moteur (wave 2)

Le moteur (`core/theme.py`, `core/fonts.py`, `ui/motion.py`, le template) était
construit mais pas branché. Cette wave l'a branché et a retiré ce qu'il
remplace :

- **§4-1** — le QSS est rendu sur la **`QApplication`**, plus sur chaque
  fenêtre. Les trois copies poussées à la main (MainWindow, Overlay, Flow Map)
  disparaissent : une fenêtre sans parent Qt hérite de la feuille de
  l'application, y compris si elle est créée plus tard. C'est ce qui règle à la
  racine le bug du 2026-09-08 (les boutons du dialogue Templates restaient
  cyan sur Inferno parce qu'ils ne descendaient d'aucun widget portant la
  propriété `theme`).
- **§4-2** — `ui/styles.qss` est supprimé. `apply_theme()` re-rend la feuille
  et re-construit la `QPalette` Fusion depuis les tokens (`theme.build_palette`)
  ; les trois `setProperty("theme", …)` n'existent plus, plus rien ne
  sélectionne dessus. La garantie que le template couvre bien les 373
  sélecteurs de l'ancienne feuille survit à sa suppression, sous forme de
  snapshot : `tests/fixtures/legacy_selectors.txt`.
- **§4-3/§4-4** — zéro littéral de couleur dans `ui/` (124 avant), zéro
  `setStyleSheet` sauf les couleurs pilotées par la donnée. `core.theme.current()`
  donne aux painters le thème actif sans le faire passer par quinze
  constructeurs. Gardé par `tests/test_no_hex_literals_in_ui.py`, dont la
  liste d'exceptions (`tests/fixtures/hex_allowlist.txt`) ne contient aucune
  couleur : seulement deux fichiers qui ne sont pas du style Qt (l'export HTML
  de Full View, et les glyphes de marque en SVG de la page À propos).
- **Dégradés retirés** (thèse visuelle « zéro dégradé décoratif ») : le fond de
  fenêtre à 4 arrêts et sa table de 24 hex, la barre de progression
  cyan→violet, le lavis horizontal derrière chaque ligne de l'overlay, la
  bordure violet→gris du panneau Réglages, le dégradé clair/foncé du bouton
  Start/Stop de l'overlay, et la bordure en dégradé du workaround
  `#dayButton`/`#toggleButton` (dont la table de six paires d'accents est
  partie avec).
- **§3 Overlay HUD** — le curseur pilote l'**alpha des fonds de section**, plus
  `setWindowOpacity()` : à 20 %, le fond s'efface et le texte reste opaque
  (avant, le HUD entier devenait illisible au bas de son propre curseur).
- **§1 motion.reduced** — réglage « Réduire les animations » dans
  Réglages → Darstellung, persisté dans le profil (`settings.reduce_motion`),
  poussé dans `ui.motion` au chargement et à chaque bascule. Le mouvement est
  utilisé à **exactement trois endroits** (toast, suppression/annulation d'une
  carte, changement de page) ; un quatrième appel fait échouer un test.

#### `focus.ring` : `outline`, pas `border` (correction 2026-09-18)

Le §2 dit « accent, 2 px, offset 1 px, tout widget focalisable, tous les
thèmes ». Écrit en `border`, l'anneau ne s'affichait **jamais** sur un bouton,
une pill, un champ ou une combo : Qt résout les conflits QSS par la
spécificité CSS2, un sélecteur d'id (`#tabButton`) vaut 100 contre 11 pour
`QPushButton:focus` — et 157 règles `#objectName` de ce template déclarent une
bordure. Vérifié offscreen avant/après.

L'anneau est donc un **`outline`** : aucune autre règle ne touche cette
propriété, il n'y a plus de conflit à perdre, et un outline se dessine *à
l'extérieur* de la bordure — ce que « offset 1 px » décrit exactement.
`outline-offset` porte enfin le token `focus.ring.offset`, jusque-là non
utilisé. Seule exception : un **champ** focalisé teinte aussi sa propre
bordure en accent (§3 « Champ »), via `border-color` — pas le raccourci
`border`, qui changerait la largeur et décalerait la ligne d'un pixel.

#### Deux défauts trouvés en relisant le rendu câblé

Ni l'un ni l'autre n'est un problème de token : ce sont des états que le code
n'attribuait pas. Trouvés en regardant les captures, pas les tests.

- **Badge de priorité** : `setObjectName("priorityMedium")` était écrit en dur
  pour *toutes* les cartes, donc chaque priorité sortait en `warn` — une tâche
  HIGH était visuellement identique à une MIDDLE. Le mapping ok/warn/danger du
  §3 ne fonctionnait que dans le dialogue Templates, seul endroit à posséder
  une table. Corrigé côté carte (tâche et shopping). Au passage, le §3 dit
  « priorité → texte seul » : le fond `*.soft` de ces trois badges est retiré,
  parce qu'une priorité figure sur *chaque* ligne et qu'un remplissage sur
  chaque ligne transforme la liste en nuancier. Les trois badges qui gardent
  un fond (schedule, MISSED, EVENT) sont ceux qui veulent dire « pas comme les
  autres ».
- **Onglet actif (Tasks / Shopping)** : la propriété `active` n'était posée que
  par un clic, donc l'app s'ouvrait avec *aucun* des deux onglets marqué.
  `MainWindow` — qui détient l'onglet actif et le restaure depuis le profil —
  déplace maintenant le surlignage lui-même (`TasksPage.mark_active_tab`).

## Pages (overrides)

Aucun pour l'instant. Un fichier `pages/<page>.md` n'est créé que si une page a besoin de déroger, et dit pourquoi.
