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

Chaque thème redéfinit **au plus** : `accent`, `accent.hover`, `accent.soft`, `secondary`, `secondary.soft`, et optionnellement la famille `bg.*`. Tout le reste est hérité d'Abyss. Un thème ne peut pas redéfinir `ok/warn/danger` ni `fg.on-accent` sans re-vérifier le contraste (test automatique).

| Thème | accent | secondary | bg.window / bg.surface |
|---|---|---|---|
| Abyss (réf.) | `#22d3ee` | `#a78bfa` | `#0b1120` / `#0f172a` |
| Inferno | `#fb923c` | `#f87171`→ secondaire = `#fda4af` | `#140c0c` / `#1c1010` |
| Emerald | `#34d399` | `#a3e635` | `#081410` / `#0c1a15` |
| Frostbite | `#7dd3fc` | `#c4b5fd` | `#0b1220` / `#101a2e` |
| Obsidian | `#e5e7eb` (accent neutre, on-accent = navy.950) | `#94a3b8` | `#0a0a0c` / `#111114` |
| Void | `#c084fc` | `#f472b6` | `#0c0a14` / `#120f1e` |

Valeurs de départ : reprises des blocs QSS actuels, à ajuster **uniquement** si le test de contraste échoue (`fg.on-accent` sur `accent` ≥ 4.5:1, `fg.muted` sur `bg.surface` ≥ 4.5:1, `fg` sur `bg.elevated` ≥ 7:1).

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

## Pages (overrides)

Aucun pour l'instant. Un fichier `pages/<page>.md` n'est créé que si une page a besoin de déroger, et dit pourquoi.
