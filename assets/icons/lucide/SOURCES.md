# Lucide — vendored icon subset

**Upstream** : <https://github.com/lucide-icons/lucide>
**Tag épinglé** : `1.47.0` (release du 2026-09-17)
**Licence** : ISC — texte intégral dans [`LICENSE`](LICENSE), copié depuis le
même tag. Lucide est un fork de Feather (MIT) ; l'en-tête ISC couvre les deux.

**Comment ils ont été récupérés** : un `curl` par fichier sur
`https://raw.githubusercontent.com/lucide-icons/lucide/1.47.0/icons/<nom>.svg`.
Pas de `curl | sh`, pas de dépendance npm, pas de fetch au runtime — les SVG
sont dans le dépôt et voyagent dans le bundle PyInstaller
(`Aion2 TM.spec`, entrée `('assets/icons/lucide', 'assets/icons/lucide')`).

**Pourquoi un sous-ensemble** : Lucide publie 1848 icônes à ce tag. Seules
celles réellement posées sur un widget (ou évidemment prochaines) sont
vendorées — un jeu complet pèserait ~5 Mo dans l'exe pour ~3 % d'usage.
`tests/test_icons.py` vérifie dans les deux sens : chaque nom référencé par
le code existe ici, et chaque SVG contient bien `currentColor` (sans quoi
`ui/widgets/icons.py` ne pourrait pas le teinter).

**Trois renommages amont** (par rapport aux noms « classiques » de Lucide 0.x,
qui n'existent plus à ce tag) : `trash-2` → `trash`, `filter` → `funnel`,
`circle-help` → `circle-question-mark`.

## `tinted/<thème>/`

48 fichiers **générés**, pas vendorés : 6 thèmes × 4 chevrons × 2 états,
produits par `scripts/gen_tinted_icons.py` depuis `core/theme.py` — `fg.muted`
au repos, `accent` au survol (suffixe `-accent`). QSS `image: url(...)` ne sait
pas teinter un SVG — d'où des fichiers déjà teintés, un par thème et par état.
Ne pas les éditer à la main : relancer le script.

## Liste (50 icônes)

- `arrow-down`
- `arrow-up`
- `arrow-up-down`
- `bell`
- `calendar`
- `calendar-days`
- `check`
- `chevron-down`
- `chevron-left`
- `chevron-right`
- `chevron-up`
- `circle`
- `circle-question-mark`
- `clock`
- `copy`
- `download`
- `external-link`
- `eye`
- `eye-off`
- `folder-open`
- `funnel`
- `grip-horizontal`
- `inbox`
- `info`
- `layers`
- `list-todo`
- `map`
- `minus`
- `party-popper`
- `pencil`
- `pin`
- `play`
- `plus`
- `refresh-cw`
- `rotate-ccw`
- `save`
- `search`
- `settings`
- `shield`
- `shopping-cart`
- `sparkles`
- `star`
- `timer`
- `trash`
- `triangle-alert`
- `upload`
- `user`
- `users`
- `volume-2`
- `x`
