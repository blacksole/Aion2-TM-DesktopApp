# Aion2 TM — Design System « Aether Cockpit »

**Statut** : source de vérité. Toute couleur, taille ou durée dans le code vient d'ici via `core/theme.py`.
**Portée du « aucun hex magique »** : garantie et testée pour `ui/` et `core/`
(`tests/test_no_hex_literals_in_ui.py`, exceptions ligne par ligne dans
`tests/fixtures/hex_allowlist.txt`) ; `core/theme.py` est le propriétaire des
valeurs, donc exempt par construction. `ItemDatabase/` est tokenisée depuis le
2026-09-18 (wave 3) : son plancher compté
(`tests/fixtures/itemdatabase_literal_baseline.txt`) est passé de 201 hex /
96 `setStyleSheet` à **18 hex / 2 `setStyleSheet`**, et ce qui reste n'est pas
de la dette — 19 valeurs forment la table de repli Abyss utilisée uniquement
si `core.theme` est introuvable (build standalone), la 20ᵉ est le
`#FCC78B` du **format de l'API amont** (`_HIGHLIGHT_SPAN_RE`), et les deux
`setStyleSheet` sont les points de livraison de sa feuille. Le plancher reste
testé dans les deux sens : il ne peut ni monter, ni baisser sans être mis à
jour.
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
| `focus.ring` | **anneau = bordure accent, dessinée sur le bord du contrôle** (2 px, le px pris est rendu en padding via `space_*_inset`) | tout widget focalisable, tous les thèmes |

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
| Badge | 11 px majuscules, rayon `sm`, fond `*.soft`, texte couleur pleine ; schedule → `secondary`, EVENT / NEW → `secondary` (« quel genre d'entrée », comme schedule), MISSED → `danger`, priorité → **texte seul**, couleur `ok`/`warn`/`danger` |
| Champ | fond `bg.input`, bordure `border`, focus : bordure `accent` (via `border-color`, largeur inchangée) ; placeholder `fg.muted` |
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
5. Test de contraste automatique sur les 6 thèmes (paires du §2) :
   `tests/test_qss_contrast.py`. Test de **rendu** : `tests/test_render_gate.py`
   construit une MainWindow offscreen par thème, grabbe ToDo + Réglages, et
   vérifie (a) qu'aucune exception ne sort, (b) qu'aucune zone de la page ne
   porte un gris par défaut de Fusion (signature d'un widget que la feuille
   n'a pas atteint), (c) que le contrôle focalisé montre bien l'accent **sur
   son bord**. C'est le seul garde-fou qui voie des pixels plutôt que des
   noms — et c'est son absence qui avait laissé passer l'anneau de focus
   cassé.
6. Motion : un helper `ui/motion.py` (`fade_in(widget)`, `fade_out(widget, then)`, `slide_hint(widget)`) qui lit `motion.*` et respecte `motion.reduced`. Aucune autre animation ailleurs. Une animation **supplantée** sur le même `(objet, propriété)` est retirée par le helper lui-même, et sa post-condition est **abandonnée** (`SUPERSEDED_POLICY`) : la plus récente exprime l'intention actuelle de l'utilisateur.
7. La feuille est **scopée** : toute règle est préfixée `QWidget[aion2="true"]`
   (voir « Portée de la feuille » au §2). Une règle non scopée est une fuite
   vers l'Armory et doit être justifiée dans
   `tests/fixtures/unscoped_selectors_allowlist.txt`.
8. **Jamais de `color` ni de `selection-color` sur une vue d'items** — une
   couleur QSS y écrase le `setForeground()` de chaque item. La couleur du
   texte d'item vient de la palette.

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

#### `focus.ring` : bordure sur le bord du contrôle (corrigé deux fois, 2026-09-18)

Le §2 disait « accent, 2 px, offset 1 px ». Deux tentatives ont échoué avant
la bonne, et les deux échecs valent d'être écrits parce qu'ils viennent de la
même méconnaissance de Qt.

1. **`border` sur un sélecteur de type** (`QPushButton:focus`). Qt résout les
   conflits QSS par la spécificité CSS2 : un sélecteur d'id vaut 100, un
   type + pseudo-classe 11 — et 157 règles `#objectName` de ce template
   déclarent une bordure. L'anneau ne s'est jamais affiché.
2. **`outline`**, choisi parce qu'aucune autre règle ne touche cette
   propriété : plus de conflit à perdre. Mais **Qt ne peut pas peindre en
   dehors du rect d'un widget** : sur un QWidget, `outline` ne fait que
   recolorer le `PE_FrameFocusRect` de Fusion, un rectangle dessiné autour du
   *sous-rect du label*, à l'intérieur du contrôle et à travers les jambages
   du texte. `outline-offset` et le rayon de la pill sont ignorés. Visible
   dans `docs/audit-2026-09-18/shots/aether/app_focus_ring_detail.png`
   (deuxième boîte collée au mot « Shopping », coupant le « g »).

**Règle retenue** : l'anneau est une **bordure accent dessinée sur le bord du
contrôle**, déclarée à la spécificité d'id (`#tabButton:focus`), plus un fond
`accent.soft` sur les contrôles non remplis. `outline: none` est posé sur la
base pour éteindre le rect de Fusion. Deux corollaires :

- passer de `border.width` à `focus.ring.width` augmente le `sizeHint` du
  contrôle, ce qui décalerait toute sa ligne au focus. Chaque règle rend donc
  le pixel en padding. QSS n'a pas d'arithmétique : les valeurs compensées
  sont des tokens dérivés — `space_2_inset` = `space_2` − `focus_inset`
  (`core/theme.py`). Un test vérifie que focaliser ne change aucune
  géométrie ;
- sur un contrôle **rempli en accent** (le bouton Save), un anneau accent est
  invisible — et c'est le premier contrôle qu'atteint un utilisateur clavier.
  Ceux-là s'entourent de `fg.on-accent`.

Les contrôles bordés dont ce fichier ne fixe pas le padding prennent l'accent
sur leur bordure existante (`border-color`), sans changement de géométrie.

#### Portée de la feuille : `QWidget[aion2="true"]` (décision 2026-09-18)

La feuille vit sur la `QApplication` (§4-1) — et Qt **fusionne** deux
feuilles propriété par propriété au lieu de laisser la plus profonde
remplacer l'autre : le poids est `(origin + depth) * 0x100000 + specificity *
0x100 + order`, donc la profondeur écrase la spécificité d'un facteur 4096.
Conséquence mesurée : la feuille de l'Armory (posée par `app.py` sur chacune
de ses fenêtres) gagne toutes les propriétés qu'elle déclare, et **toutes
celles qu'elle ne déclare pas descendent de la nôtre chez elle**. Barlow dans
un layout calé au doigt sur la police système, du `letter-spacing` dans ses
en-têtes de table, des fonds de badge qui suivent le thème dans une fenêtre
par ailleurs codée en Abyss — et, le plus grave, un `color` sur les vues
d'items qui aplatissait chaque `setForeground()` par rareté (le correctif du
2026-08-29, avec rapport utilisateur attaché, défait en silence).

Décision : **toute règle de la feuille est préfixée `QWidget[aion2="true"]`**.
Nos trois top-levels (MainWindow, OverlayWindow, FlowMapWindow) posent la
propriété dans `__init__`, et Qt remonte `parentWidget()` pour les sélecteurs
de descendance — donc chaque dialogue, popup et enfant des nôtres matche,
tandis que les fenêtres sans parent de l'Armory ne matchent jamais. Une seule
exception, forcée par Qt : `QToolTip`, que Qt rend dans un `QTipLabel`
top-level sans parent widget, qu'aucun sélecteur de descendance ne peut
atteindre. Elle est allow-listée avec sa raison
(`tests/fixtures/unscoped_selectors_allowlist.txt`), et elle est sans risque
parce que l'Armory déclare son propre `QToolTip`, fond **et** texte.

Corollaire à ne pas oublier : **aucun `color` ni `selection-color` sur une vue
d'items**, jamais — ni en bare ni en scopé. Une couleur QSS sur une vue
d'items écrase inconditionnellement le `setForeground()` de chaque item. La
couleur du texte d'item vient de la palette (`QPalette::Text` /
`::HighlightedText`, toutes deux dérivées des tokens). Nos propres popups de
combo reçoivent leur couleur par règle `#objectName`.

**Police globale = vague Armory (décision différée).** `app.setFont()` ne
passe pas par la cascade QSS et atteindrait donc l'Armory quoi qu'il arrive :
la police par défaut de l'application reste **inchangée** pour l'instant, et
Barlow est posée par la règle scopée ci-dessus. Le jour où l'Armory est
tokenisée, `app.setFont()` devient le bon véhicule et la règle scopée peut
disparaître.

**Dette Armory, comptée et gelée.** `ItemDatabase/` n'est pas tokenisée (206
hex, 23 `QColor`, 96 `setStyleSheet`, zéro import de `core.theme`) et le
§ « Statut » promet pourtant « aucun hex magique dans `ui/` ou
`ItemDatabase/` ». Tant que la vague n'a pas eu lieu, la promesse tenable est
un plancher : `tests/fixtures/itemdatabase_literal_baseline.txt` enregistre
les comptes, et le test échoue s'ils **montent** (comme s'ils baissent sans
mise à jour du plancher).
*(Fermé le jour même par la wave 3 — voir l'entrée « tokenisation de
l'Armory » ci-dessous. Le mécanisme du plancher, lui, reste en place.)*

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

### 2026-09-18 — tokenisation de l'Armory (wave 3)

L'`ItemDatabase/` était la dernière zone hors du système : sa propre feuille
écrite à la main (1 205 lignes, 190 sélecteurs, « Abyss, copié
volontairement »), 201 littéraux de couleur, 96 `setStyleSheet`, zéro import
de `core.theme`. Elle restait navy pendant que l'app changeait de thème.

- **§4-2** — `ItemDatabase/styles.qss` disparaît au profit de
  `ItemDatabase/styles.template.qss`, rendu **par thème** via un renderer
  générique (`core.theme.build_qss_from`). La garantie « le template couvre
  les 190 sélecteurs de l'ancienne feuille » survit à la suppression sous
  forme de snapshot : `tests/fixtures/armory_legacy_selectors.txt`.
- **Portée** — cette feuille n'est **pas** scopée en `QWidget[aion2="true"]`,
  au contraire de celle de l'app : les fenêtres de l'Armory sont sans parent
  et la reçoivent directement (`window.setStyleSheet`), donc un préfixe n'y
  aurait rien à sélectionner. L'étanchéité décrite dans « Portée de la
  feuille » reste donc exacte et nécessaire dans les deux sens.
- **§4-4** — 96 `setStyleSheet` → **2**, et ce sont des points de livraison
  (`_style_window` pour une fenêtre neuve, `apply_theme` pour celles déjà
  ouvertes), pas du style. Les couleurs pilotées par la donnée passent par
  une propriété dynamique `dataColor="<kind>:<key>"` + une règle par entrée
  de table : la couleur reste dans la feuille (donc suit le thème) au lieu
  d'être figée sur le widget — une feuille inline est la plus profonde que
  Qt connaisse, elle gagnait la propriété et aucun re-rendu ne la
  rattrapait.
- **§4-4, propriétaire** — les **tables de données** montent dans
  `core/theme.py` (rareté d'item, type de gear, type de skill, méthode de
  craft, thème/catégorie d'Arcana, board Genius, rôle, type de dégâts, état
  de spécialisation). `ItemDatabase/app.py` n'en garde aucune copie ; le
  gate anti-dérive de `tests/test_theme.py` est inversé en conséquence.
- **Deux tables par thème supprimées** : `LAYOUT_THEMES` (6 × 4 hex, le fond
  en dégradé diagonal — contraire à la thèse « zéro dégradé décoratif », et
  déjà retiré côté app à la wave 2) devient le token `bg.window` ;
  `ENCHANT_ACCENT_BY_THEME` (6 hex choisis à la main pour ne pas collider
  avec une couleur de rareté) était la copie privée de « l'accent du thème
  courant » et devient `{{accent}}` dans `#SlotEnchantLabel`.
- **Nouvelle forme de placeholder** : `{{token|alpha}}`
  (`{{accent|0.06}}`). L'ancêtre de cette feuille était construit en couches
  translucides — 60 règles en `rgba(34, 211, 238, 0.06 … 0.25)` — et le jeu
  sémantique n'a qu'un seul alpha par rôle (`accent.soft` = 0.14). Sans
  modificateur, porter ces couches imposait soit de les aplatir sur un seul
  token *soft* (visiblement différent), soit d'inventer douze tokens
  `*.soft-er` dont personne d'autre n'aurait l'usage.
- **Correspondances non exactes** : chaque valeur de l'ancienne feuille qui
  n'était pas *sur* un token est documentée ligne par ligne dans le bloc
  d'en-tête de `ItemDatabase/styles.template.qss` (les quatre gris
  éteints/désactivés deviennent `fg.muted` à quatre alphas ; les traits
  slate-500 deviennent `border` sur les surfaces et `border.strong` sur les
  contrôles ; les quatre ors deviennent `warn`). Pour le thème Abyss, tout
  ce qui n'est pas dans cette liste rend **octet pour octet** comme avant.
- **Contraste (`tests/test_armory_theme.py`)** : aucune couleur de rareté n'a
  eu besoin d'être adoucie. Sur les six thèmes, chaque rareté est à ≥ 6,1:1
  sur `bg.elevated` (min. 6,11 — Common sur Frostbite ; max. 11,60 — Unique
  sur Void), et la pire de **toutes** les couleurs de donnée est à 3,96:1
  (`skill_type:passive` sur Frostbite, seuil 3:1). Une couleur de rareté est
  de la **donnée de jeu** : si l'une échouait un jour, le correctif serait
  une puce `*.soft` derrière le texte, jamais une autre teinte.
- **§4-5** — garde-fou de rendu propre à l'Armory : les trois fenêtres
  (Item Database, Build Planner, Crafting) construites offscreen et grabbées
  par thème (18 captures), zéro gris Fusion, plus une vérification en
  **pixels** que le `setForeground()` par rareté survit à la feuille (le
  défaut du 2026-08-29, re-garanti du bon côté de la suppression du fichier).

### Décisions différées (posées explicitement, pas oubliées)

| Sujet | Décision | Pourquoi pas maintenant |
|---|---|---|
| `app.setFont()` comme véhicule de la police de base | **toujours différé** (l'Armory est tokenisée, mais pas re-typographiée) | `setFont` ne passe pas par la cascade QSS : il atteindrait l'Armory quoi qu'on fasse. La vague Armory (2026-09-18) a migré ses **couleurs**, pas ses métriques — sa feuille ne déclare toujours aucune `font-family`, et ses 22k lignes de layout sont calées au doigt sur la police système. Barlow reste posée par la règle scopée. Le jour où l'Armory est re-typographiée, `setFont` devient le bon véhicule. |
| Emoji utilisés comme icônes (`"📋 Vorlagen"`, `"🛒 Einkauf"`, `"👤 Charaktere"`) dans `core/translations.py` | vague icônes | §3 dit « aucun emoji comme icône » et ces glyphes sont dans les chaînes traduites des trois langues. Les remplacer demande de vrais `QIcon` Lucide posés sur les boutons — un travail d'icônes, pas une retouche de chaîne. Le double sélecteur de thème du `SettingsDialog` a en revanche perdu ses emoji tout de suite (ils n'étaient pas traduits). |
| Deux sélecteurs de thème (`SettingsDialog` + page Appearance) | à dédupliquer | Le dialogue est vivant (en-tête → `open_settings`) ; retirer un contrôle qu'un utilisateur utilise peut-être est une décision produit, pas un correctif de revue. Sa version emoji est corrigée, la duplication reste. |
| Flèches de spinbox/combo (`assets/icons/arrow_*_orange.png`) | vague icônes | Assets PNG oranges, donc hors thème sur Abyss/Emerald/Void. Corriger demande des icônes par thème ou teintées à l'exécution. |

## Pages (overrides)

Aucun pour l'instant. Un fichier `pages/<page>.md` n'est créé que si une page a besoin de déroger, et dit pourquoi.
