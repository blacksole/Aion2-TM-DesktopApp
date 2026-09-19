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

Implémentation des deux dernières lignes : `ui/widgets/icons.py`
(`icon(name, size, token)`, `IconLabel`, `set_icon(bouton, …)`), jeu vendoré
sous `assets/icons/lucide/`, chevrons pré-teintés par thème sous
`assets/icons/lucide/tinted/<thème>/`. Voir le journal, 2026-09-19.

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

## 5. Architecture Armory (moteur de calcul)

> Ajouté le 2026-09-19 (Stage 1 de `docs/audit-2026-09-18/B-armory.md` §4.2).
> Ce §5 parle d'**architecture**, pas de style : il est ici parce que le
> design system est le seul document que tout le monde lit avant de toucher
> à l'Armory, et parce que sa règle centrale (« aucun Qt ») est de la même
> nature que « aucun littéral de couleur » du §4 — une frontière qu'un test
> garde, pas une convention qu'on se rappelle.

`ItemDatabase/app.py` faisait 22 900 lignes d'UI, de logique et d'accès
données entrelacés. Le calcul **pur** — qui était déjà pur, juste prisonnier
d'un module qui importe PySide6 et se monkey-patche à l'import — vit
maintenant dans `ItemDatabase/armory_engine/` :

| Module | Ce qu'il contient |
|---|---|
| `model.py` | les formes partagées (`Item`, `Detail`, `BuildState`) et le protocole **`DetailProvider`** |
| `enchant.py` | les 4 estimateurs calibrés, la courbe Rune, la poussée de GearScore |
| `substats.py` | les 6 profils (Gear-Typ × Rôle) et l'auto-pick glouton des sous-stats |
| `arcana.py` | le solveur de cartes Lord (meilleur cas) et son « pourquoi pas » |
| `daevanion.py` | le routeur Steiner glouton sur le plateau |
| `transfer.py` | le graphe de hops d'amélioration, l'arbre de matériaux, le cumul de Kinah |
| `sets.py` | la table de sets de donjon précalculée |
| `stats.py` | la fusion de stats par slot et le GearScore, au-dessus d'un `DetailProvider` |
| `explain.py` | le **contrat** que toute recommandation future renverra (données seules) |

**Trois règles, chacune tenue par un test.**

1. **Aucun Qt dans le moteur.** Pas d'import PySide6, ni direct ni transitif.
   Vérifié par `tests/test_armory_engine_qt_free.py`, qui importe chaque
   module **dans un sous-processus** avec un `meta_path` finder qui fait
   échouer tout import PySide6 — un import en cours de processus ne
   prouverait rien, PySide6 étant déjà chargé quand un test tourne. Ce que
   le moteur a réellement besoin de Qt (les détails d'items) passe par
   `DetailProvider`, un `Protocol` à une seule méthode `get(item_id)` que
   `ItemDetailCache` satisfait structurellement, sans rien changer.
2. **Un seul exemplaire.** Le code a été **déplacé**, pas copié : app.py le
   réimporte sous exactement les mêmes noms, donc aucun de ses ~700 sites
   d'appel n'a changé. `tests/test_armory_engine_packaging.py` refuse qu'un
   nom déplacé soit redéfini au niveau module dans app.py — une redéfinition
   masquerait l'import en silence, et les tests du moteur continueraient de
   passer contre du code que plus rien n'exécute. Même motif que les gates
   de tokens du §4.
3. **Toute recommandation s'explique.** Un solveur ne renvoie jamais un
   choix nu : `explain.py` fixe `Reason(stat_id, delta, weight, text_key)` et
   `Recommendation(pick, score_delta, reasons)`. `text_key` est une **clé de
   traduction**, jamais du texte affiché — comme partout ailleurs. Les
   `dataclass` sont livrées en Stage 1 *sans* logique, exprès : figer le type
   de retour avant le premier solveur est ce qui empêche le deuxième
   d'inventer le sien. La surface d'affichage existe déjà (les lignes de
   delta par stat de Build Compare), et `stats.compute_stat_totals_detailed`
   renvoie déjà l'attribution par slot dont ces deltas se justifient.

**Empaquetage.** `app.py` est embarqué comme fichier de **données** (l'hôte
le charge par `spec_from_file_location`), donc PyInstaller ne suit pas ses
imports : le paquet a besoin de sa propre entrée `datas`, vers
`ItemDatabase/armory_engine`, dans les **deux** `.spec`. Une destination plus
haute d'un niveau et l'Armory ne s'ouvre plus du tout. Gardé par
`tests/test_armory_engine_packaging.py`, même raisonnement que le gate de
destination de la feuille (`tests/test_armory_theme.py`).

**Ce qui n'est pas parti.** Tout ce qui dessine ou charge : les tables de
libellés et de couleurs, les `_load_*` qui lisent `data/*.json`, et la fusion
**6 sources** (`_refresh_stat_info` / `_compute_full_build_totals`), qui
touche huit autres morceaux d'état de `LoadoutWindow`. La couper en deux
laisserait deux fusions qui doivent s'accorder — exactement le bug de
2026-09-03 que cette méthode a été écrite pour corriger. Elle part entière,
avec Genius/Arcana/Daevanion/wings, ou pas du tout.

### Recommandations — contrat d'explicabilité (ajout 2026-09-19, Stage 2)

> Stage 2 de `docs/audit-2026-09-18/B-armory.md` : les deux premières
> features **S** du §3.4 (#1 écart de stats vs profil de rôle, #2 pièce de set
> manquante). Trois modules de plus dans `armory_engine/` — `providers.py`
> (le seul qui touche au disque), `score.py`, `recommend.py` — et une carte
> de plus sur la page Armory.

**1. Toute recommandation s'explique, et l'explication est une donnée.**
La règle 3 du §5 devient exécutable : `next_best_actions()` ne renvoie que des
`Recommendation(pick, score_delta, reasons, text_key, text_kwargs)`, chaque
`Reason` portant `(stat_id, delta, weight, text_key, text_kwargs)`.
`text_key` est une **clé**, jamais une phrase : le solveur tourne quand l'état
change, le rendu arrive plus tard, et la langue peut changer entre les deux
(`tests/test_armory_dashboard.py::test_a_language_switch_re_renders_a_recommendation_solved_earlier`).
Le `Recommendation` a gagné son propre `text_key` en Stage 2, avec défaut :
sans lui, le titre de la ligne devait être re-dérivé du `pick` dans le widget
— exactement le « rendre à partir de ce que le moteur a déjà calculé » que ce
contrat existe pour empêcher.

**2. Les poids viennent du rang, pas d'un modèle de combat.**
`score.role_weights()` = décroissance géométrique `decay ** rang`
(défaut 0.75 : le rang 7, plafond `_STAT_PRIORITY_MAX_ENTRIES`, vaut 0.178 du
rang 1). C'est tout ce qu'une liste ordonnée contient. Le §3.4 #1 promettait
« tu es 240 Accuracy sous le profil » ; ce nombre demande une cible absolue,
donc un modèle de combat que les données ne livrent pas (§3.4, dernière
ligne). L'inventer, c'est inventer le modèle — et le joueur n'aurait aucun
moyen de distinguer un chiffre venu du jeu d'un chiffre venu de nous.

Donc ce qui est calculé est **sans unité** :

| Constat | Pourquoi il est défendable |
|---|---|
| *couverture par slot* — combien de slots équipés portent un stat que le profil classe haut | « aucune pièce ne fournit ça » est un fait, dans aucune unité |
| *alignement des sous-stats* — part des choix qui tombent dans le top-N du profil | compare le joueur à **son propre** classement, pas à une cible |
| *complétude de set* — pièces possédées / pièces du set | pur comptage sur `dungeon_sets.json` |
| *écart vs build de référence* (optionnel) | même stat, mêmes unités → le ratio a un sens |

Comparer la **magnitude** de deux stats différents (3 000 Attack contre 44
Critical Hit) est la seule chose que l'absence de modèle interdit. Rien ne le
fait.

**3. `score_delta` ne somme pas toujours ses `reasons`.**
`explain.py` promet `score_delta == Σ reason.score_contribution` — vrai pour
un solveur en espace de stats (§3.4 #3/#4). Les deux features de Stage 2 n'en
sont pas : leur `score_delta` est une **complétude dans [0, 1]**, et leurs
`reasons` *énumèrent* le constat au lieu de le décomposer. L'exception est
`missing_set_pieces`, où la décomposition tombe juste (une raison par pièce
manquante, chacune valant `1/total`) et où le test le vérifie. Chaque solveur
dit lequel des deux il est, dans sa propre docstring ; un solveur qui ne le
dit pas est un bug de revue.

**Ce qu'il faudrait pour un vrai optimiseur** (et qui n'existe pas encore) :
une valeur marginale par point de stat, les soft caps, les courbes de
rendement décroissant, et l'interaction avec ce qui est déjà empilé. Avec ça,
`score_delta` redevient un delta de score réel, les features #3 (meilleur
upgrade par slot) et #4 (GearScore +N le moins cher) deviennent exactes, et
`Reason.weight` cesse d'être une approximation par le rang. Sans ça, toute
« recommandation d'optimisation » serait une opinion déguisée en calcul.

**4. La dégradation est une valeur de retour, pas une liste vide.**
Un tableau de bord ne sait pas distinguer « rien à améliorer » de « pas de
données ». `DataBundle.available` / `.reason_key` répondent à la question :
sans `items_all.json`, `next_best_actions()` renvoie **une** recommandation
portant `armory_reco_needs_data`, et la carte affiche la phrase. C'est l'état
normal d'un clone frais (le pack de données fait ~278 Mo et n'est pas dans
git), donc c'est le chemin nominal, pas une branche d'erreur.

**5. Style.** La carte `#armoryRecoCard` reprend la surface, la bordure et le
rayon de `#armoryCard` (§15) et n'a **ni `:hover` ni `:focus` accentué** :
elle n'est pas un bouton, ses lignes le sont. « Why? » est un lien accentué
(`#armoryRecoWhyButton`), pas un second bouton primaire — §3, un primaire par
surface. Volontairement **non animée** : `ui/motion.fade_in` conviendrait,
mais §4-6 dit « aucune autre animation ailleurs » et
`tests/test_theme_wiring.py::test_exactly_three_places_animate` compte les
sites d'appel. Un sixième est une décision de design qui passe par ce
document d'abord, pas un détail de cette carte.

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

#### Ce que la revue G a corrigé (même jour)

La revue d'Apex a trouvé la faille structurelle de la vague, et elle vaut
d'être écrite parce qu'elle est générale : **partout où la vague affirmait
quelque chose qu'un test pouvait confronter à une seconde source,
l'affirmation était vraie ; partout où le test ne pouvait inspecter qu'un
seul côté, elle était fausse.** La moitié QSS→QSS est épinglée par un
snapshot de sélecteurs, donc exacte. La moitié Python→QSS — 94 feuilles
inline devenues 228 règles — n'était épinglée par rien, et c'est là que
vivaient tous les défauts :

- **trois règles écrites pour un `objectName` que personne ne posait**
  (`#TooltipStatusPill`, `#EquipItemIconLabel`, `#SimGradeLabel`) : la pilule
  d'état du Daevanion et la plaque de l'objet équipé rendaient sans fond,
  sans padding, sans rayon et **sans anneau de rareté** — de la géométrie
  perdue dans une vague « style only ». Le test censé garder exactement ça
  comparait la feuille à elle-même et **nommait deux des trois victimes**
  dans sa propre liste de paramètres tout en passant. Il est inversé : les
  `#Id` sont désormais *dérivés de la feuille* et confrontés au source de
  `app.py` ;
- **une couleur passée là où une clé de donnée est attendue**
  (`dataColor="skill_type:#22d3ee"`), donc les en-têtes ACTIF/PASSIF du
  tooltip de carte Arcana perdaient leur couleur dans les six thèmes. Gardé
  maintenant en interrogeant les **widgets construits**, pas en énumérant
  les clés légitimes ;
- **une dérive de teinte non documentée** : la bande « pvp » de l'accordéon
  de substats passait de rose `rgb(244,114,182)` à violet `{secondary}`
  (Δ 77,25,68). Elle prend la couleur de donnée PvP (`#fb7185`), qui est ce
  que « PvP » veut déjà dire partout ailleurs dans cette fenêtre ;
- **la parité des valeurs n'était plus falsifiable** : le fichier de
  référence avait été supprimé dans le même commit, donc la phrase « pour
  Abyss, tout ce qui n'est pas dans la table de correspondance rend octet
  pour octet comme avant » était vraie et invérifiable. Elle l'est
  maintenant : `tests/fixtures/armory_abyss_declarations.json` est
  **régénéré en rejouant la table de correspondance sur
  `git show eb53cd6:ItemDatabase/styles.qss`**, pas en photographiant le
  rendu courant — un échec signifie donc « le rendu s'est éloigné de la
  feuille supprimée », pas « il a changé depuis hier » ;
- `_FALLBACK_TOKENS` (la table de repli d'`app.py`) était affirmée égale aux
  valeurs Abyss dans trois documents et comparée à elles dans aucun : un
  miroir sans comparaison est un commentaire, pas un contrat. Gate ajouté.

### 2026-09-19 — vague icônes

§3 posait deux lignes (« Icônes : Lucide (ISC), 16/20/24 px, couleur héritée
via `fg.*` » et « État vide : icône Lucide 24 px `fg.muted` ») que **rien ne
pouvait tenir** : le dépôt n'embarquait aucun jeu d'icônes. Trois lignes des
« Décisions différées » pointaient toutes vers la même cause. Elles sont
closes (ou réduites) ici.

**Le jeu.** 51 SVG Lucide vendorés depuis le tag **1.47.0**, sous
`assets/icons/lucide/`, avec la licence ISC et un `SOURCES.md` qui nomme le
tag, la méthode de récupération (un `curl` par fichier, jamais `curl | sh`) et
les trois renommages amont (`trash-2` → `trash`, `filter` → `funnel`,
`circle-help` → `circle-question-mark`). 21 ko au total — le jeu complet en
pèse ~5 Mo pour ~3 % d'usage.

**La teinture, et pourquoi un `QIconEngine`.** Un SVG Lucide se peint en
`stroke="currentColor"` ; Qt n'a pas de `currentColor`, donc la couleur est
substituée dans le **texte** du SVG avant `QSvgRenderer`. Une icône teintée est
donc l'instantané d'**un** thème, et un `QIcon(QPixmap)` posé sur un bouton
garderait la couleur de l'ancien thème pour toujours après une bascule. Deux
manières de s'en sortir : rappeler chaque site d'appel depuis
`MainWindow.apply_theme` (une chose de plus à ne pas oublier, dans un fichier
que cette vague ne possédait pas), ou résoudre la couleur **au moment de
peindre**. C'est la seconde : `ui/widgets/icons.py` expose un `QIconEngine`
qui interroge `theme.current_tokens()` à chaque `pixmap()`/`paint()`, et un
`IconLabel` qui fait la même chose dans son `paintEvent` pour les endroits où
un bouton mentirait. Le cache est indexé sur la couleur **résolue** : une
bascule de thème le rate simplement, il n'y a aucune entrée périmée à
invalider, et aucun hôte à prévenir. Un site d'appel ne nomme jamais une
couleur, il nomme un **token** (`fg`, `fg.muted`, `ok`, `accent`) — §4-3 sans
exception.

**Les flèches, et pourquoi au build.** QSS `image: url(...)` charge un fichier
tel quel : il ne sait ni teindre, ni masquer, ni recolorer. La seule sortie est
que le fichier soit déjà de la bonne couleur — donc un fichier par thème. Reste
le *quand* : à l'exécution dans le répertoire d'installation (impossible, il est
en lecture seule sur un install packagé), à l'exécution dans le cache
utilisateur (inatteignable : la feuille adresse ses fichiers par le marqueur
`ASSET_PATH`, qui est la racine du **bundle**, et pointer ailleurs demanderait
un second placeholder dans `core/theme.py`), ou **au build, commité**. 6 thèmes
× 4 chevrons × 2 états = 48 fichiers de ~230 octets, générés par
`scripts/gen_tinted_icons.py`, relisibles dans un diff, et comparés aux tokens
par `tests/test_icons.py` — ils ne peuvent pas se périmer en silence. La
feuille les sélectionne par `{{name}}`, le nom du thème actif.

Deux états, et c'est le second qui justifie la découpe par thème : au repos le
chevron est `fg.muted`, un token que §2 **n'autorise aucun thème à
redéfinir** — les six dossiers contiennent donc les mêmes octets, exprès. Au
survol il passe à `accent`, qui est précisément ce qui distingue un thème d'un
autre (cyan, teal, orange, lavande, blanc, violet). Le contrôle retrouve ainsi
la touche de couleur que le PNG orange lui donnait — mais celle du thème que
l'utilisateur a choisi, pas celle d'un bitmap. Un test exige que les six
accents survolés soient six couleurs distinctes.

#### Une pseudo-classe de survol va sur le **sous-contrôle**, pas sur le widget

La règle de survol ci-dessus a d'abord été écrite
`#settingsCombo:hover::down-arrow` — la forme CSS naturelle, « quand le combo
est survolé, sa flèche ». Elle **parse**, et elle fait dessiner l'image une
**seconde fois** : non redimensionnée, non positionnée, par-dessus le texte du
combo. Un chevron à moitié rogné, qui se lit comme une coche `✓` parasite à
côté de la valeur — dans les six thèmes, dans tous les combos, **sans qu'aucun
survol soit en jeu**. Repéré dans une capture, pas par un nom : les tests de
tokens voyaient une feuille parfaitement correcte.

La forme juste met l'état sur le sous-contrôle :
`#settingsCombo::down-arrow:hover`. Même famille que la leçon `outline` de
l'anneau de focus (§ « `focus.ring` », plus haut) — la feuille est valide, et
l'idée que Qt se fait de ce qu'elle veut dire n'est pas celle de CSS. Gardé
par `tests/test_icons.py::test_no_arrow_rule_puts_its_pseudo_state_on_the_widget`,
qui refuse la forme `:<état>::<flèche>` dans les deux feuilles.

**Ce qui a changé de glyphe à icône** (16/20/24 px, jamais autre chose — gaté) :
engrenage et fermeture de l'overlay, chevron d'accordéon de l'overlay,
engrenage de la page Timers, suppressions du gestionnaire de Custom Timers,
reset manuel de ToDo, édition/enregistrement du nom de profil (le `💾` était un
emoji **couleur** sur la plupart des piles de polices Linux — le seul glyphe de
l'app qui ignorait le thème entièrement), suppression et reset de la Flow Map,
bouton « fait » d'une carte de nœud, boutons « fait »/« éditer » du mode Guide
et la coche peinte dans sa pastille, bascule de description du dialogue
Templates, et les quatre pastilles du résumé de progression (`✓ ○ ! Σ` →
`check` / `circle` / `triangle-alert` / `sigma`, chacune sur le **token que sa
règle QSS utilisait déjà**, parce qu'un `color:` de feuille n'atteint pas un SVG
rendu).

**Ce qui reste un glyphe, et pourquoi** (`tests/fixtures/icon_emoji_allowlist.txt`,
une raison par entrée, et un test qui échoue sur une entrée **morte** comme sur
un nouveau glyphe) : la bascule de complétion `○`/`●`/`✓`, dont l'exemplaire
canonique vit dans `ui/main_window.py` — la convertir sur Shopping et l'overlay
seuls aurait rendu l'app **moins** cohérente qu'avant ; les pastilles de
couleur, qui ne sont pas des icônes déguisées mais le moyen le moins cher
d'afficher une couleur venue de la donnée ou d'une règle `[status=…]` ; et le
symbole de nœud Flow, **choisi par l'utilisateur** et stocké dans sa map.

**Revue D/m4 (« une pastille de couleur a besoin d'une forme ») n'est pas
close** : elle demande quatre formes distinctes par statut dans la légende de la
Flow Map, ce qui est une décision de design, pas une substitution d'icône.

### Décisions différées (posées explicitement, pas oubliées)

| Sujet | Décision | Pourquoi pas maintenant |
|---|---|---|
| `app.setFont()` comme véhicule de la police de base | **toujours différé** (l'Armory est tokenisée, mais pas re-typographiée) | `setFont` ne passe pas par la cascade QSS : il atteindrait l'Armory quoi qu'on fasse. La vague Armory (2026-09-18) a migré ses **couleurs**, pas ses métriques — sa feuille ne déclare toujours aucune `font-family`, et ses 22k lignes de layout sont calées au doigt sur la police système. Barlow reste posée par la règle scopée. Le jour où l'Armory est re-typographiée, `setFont` devient le bon véhicule. |
| Emoji utilisés comme icônes (`"📋 Vorlagen"`, `"🛒 Einkauf"`, `"👤 Charaktere"`) dans `core/translations.py` | **réduit** (vague icônes 2026-09-19) — reste les seules **chaînes traduites** | §3 dit « aucun emoji comme icône » et ces glyphes sont dans les chaînes traduites des trois langues. La vague icônes du 2026-09-19 a livré le moteur (`ui/widgets/icons.py`) et **tous les glyphes posés dans le code** ; il reste exactement les ~40 clés de `core/translations.py` (de + ru + en), qui appartiennent à un autre chantier au même moment. Ce qui manque n'est plus un jeu d'icônes, c'est un passage clé par clé : retirer le glyphe de la chaîne et poser `icons.set_icon(bouton, …, clear_text=False)` au site d'appel. Liste exacte dans le rapport de la vague. Le double sélecteur de thème du `SettingsDialog` avait en revanche perdu ses emoji tout de suite (ils n'étaient pas traduits). |
| Deux sélecteurs de thème (`SettingsDialog` + page Appearance) | à dédupliquer | Le dialogue est vivant (en-tête → `open_settings`) ; retirer un contrôle qu'un utilisateur utilise peut-être est une décision produit, pas un correctif de revue. Sa version emoji est corrigée, la duplication reste. |
| ~~Flèches de spinbox/combo (`assets/icons/arrow_*_orange.png`)~~ | **fait** (2026-09-19, vague icônes) | Les deux PNG oranges sont supprimés. Les trois règles `::down-arrow`/`::up-arrow` de `ui/styles.template.qss` pointent maintenant sur `assets/icons/lucide/tinted/{{name}}/chevron-*.svg` — « par thème » plutôt que « teintées à l'exécution », parce que QSS `image: url()` ne sait pas teindre et que les deux chemins d'exécution possibles échouent (écrire dans le bundle est impossible en install packagé ; écrire dans le cache utilisateur est inatteignable, `ASSET_PATH` étant la racine du bundle). Les 6 × 4 × 2 fichiers sont **générés et commités** par `scripts/gen_tinted_icons.py` — `fg.muted` au repos (§3 : « couleur héritée via `fg.*` »), **`accent` au survol et au focus**, ce qui rend au contrôle la touche de couleur que le PNG orange portait, mais celle du thème choisi. `tests/test_icons.py` échoue s'ils s'écartent des tokens, et exige que les six accents survolés soient bien six couleurs distinctes. La flèche de l'Armory (`ItemDatabase/styles.template.qss`, `QComboBox::down-arrow` → `assets/ui/dropdown_arrow.png`) n'est **pas** dans ce lot : c'est un PNG gris neutre, pas un accent chaud hors thème, et sa déclaration est tenue par le gate de parité octet-pour-octet (`tests/fixtures/armory_abyss_declarations.json`) — la toucher est une décision de la vague Armory, pas de celle-ci. |
| Deux libellés tronqués dans le Build Planner : « Constitutior » (colonne Stat Values, `Constitution` coupé) et « 1aterials & Enhancemer » (en-tête de section du Crafting, `Materials & Enhancement` coupé aux deux bouts) | dette de **layout**, pas de style | Repérés dans les captures de la vague Armory (`docs/audit-2026-09-18/shots/aether-armory/`) et **antérieurs** à elle : la vague n'a changé aucune métrique (ni police, ni padding, ni largeur — voir « NOT tokenised, on purpose » dans l'en-tête de `ItemDatabase/styles.template.qss`). Ce sont des largeurs fixes trop courtes pour la chaîne rendue ; corriger demande de toucher au layout (élargir la colonne, ou élider proprement), ce qui est hors d'une vague de couleurs. |
| ~~Icône de l'**état vide** (§3 : « icône Lucide 24 px `fg.muted` »)~~ | **fait** (2026-09-19, vague icônes) | Revue G/m13. `EmptyStateWidget.set_icon(name)` pose une icône Lucide 24 px `fg.muted` au-dessus du titre ; elle est **optionnelle et absente par défaut**, parce que `ui/pages/armory_page.py` construit le même widget et appartenait à un autre chantier le jour même — une icône obligatoire aurait modifié une page hors périmètre. Posée sur ToDo (`list-todo`), Shopping (`shopping-cart`) et le gestionnaire de Custom Timers (`timer`) ; l'Armory reste à brancher (une ligne, `set_icon("shield")`). Raison d'origine, conservée :  `ui/widgets/empty_state.py` n'a pas d'icône, et la page Armory en fait la première vue d'un nouvel utilisateur — mais le dépôt n'embarque **aucun jeu Lucide** (`assets/icons/` ne contient que l'icône d'app et les PNG d'outils Flow). Poser un emoji à la place violerait la ligne « aucun emoji comme icône » du même §3. Donc : même vague que les deux lignes ci-dessus (emoji des onglets, flèches spinbox/combo) — un travail d'assets, pas une retouche de style. Le widget est déjà prêt à la recevoir (il n'expose que des `objectName`, zéro style en dur). |
| Pastille de grade du **nœud « start »** des tooltips Daevanion | à corriger dans `ItemDatabase/` | Revue G/m9. `_DAEVANION_GRADE_TO_ITEM_GRADE` mappe `"start"` sur `""`, que `_set_data_color` traite comme « efface » ; le chemin canvas (`_daevanion_grade_color`) sait déjà spécialiser `start` → `accent`, pas le chemin tooltip. Correctif d'une ligne, mais **dans `ItemDatabase/app.py`** : hors du périmètre de la passe MINOR du 2026-09-19 (fichier tenu par un autre chantier au même moment). À prendre avec m7 (early return de `apply_theme`), qui vit dans le même fichier. |
| 4 `objectName` morts dans la feuille de l'Armory (`#ChainNode`, `#ChainSideLabel`, `#ExpandableMaterialHeader`, `#SkillRow`) | à câbler ou à supprimer | Règles sans widget : les quatre sont déjà morts dans `eb53cd6` (avant la vague) et leurs règles existaient dans l'ancienne feuille écrite à la main. Supprimer une règle est une décision sur une **fonctionnalité** (widget renommé ? panneau retiré ?), pas une retouche de style — d'où l'attente. Ils sont listés avec cette raison dans `tests/fixtures/armory_dead_selectors.txt`, et le gate `test_every_objectname_rule_has_a_widget_that_sets_it` échoue sur tout **nouveau** mort. |

## Pages (overrides)

Aucun pour l'instant. Un fichier `pages/<page>.md` n'est créé que si une page a besoin de déroger, et dit pourquoi.
