# Contributing to Aion 2 Companion

Thanks for wanting to help build this out — PRs, issues, and forks-to-collaborate are all welcome.

## License note

The project is licensed under **AGPL-3.0** (see [`LICENSE`](LICENSE)). By
opening a pull request you agree your contribution is licensed under the
same terms as the rest of the project, so it stays under one consistent
license.

What that means in practice, day to day:

- Fork it, branch it, open PRs — exactly as before, nothing changes about
  the day-to-day workflow.
- If you (or anyone) redistribute a modified copy of this app, or run it
  as a network service others use, AGPL-3.0 requires making that version's
  full source available under the same license. It cannot be taken
  closed-source and sold as a separate product.

## Workflow

- Branch from `main` (or the currently active work branch — check with the
  maintainer if unsure).
- Merge commits, not squash, once a PR is approved.
- `uv run pytest -q` should stay green (existing known-baseline failures
  are tracked separately, not blockers for new PRs).
