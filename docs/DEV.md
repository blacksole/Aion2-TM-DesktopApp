# Developer setup

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned by `pyproject.toml`; same commands on Linux and Windows.

```bash
uv sync --group dev                        # runtime + pytest/ruff, from uv.lock
uv run python main.py                      # launch
uv run ruff check .                        # lint
QT_QPA_PLATFORM=offscreen uv run pytest    # tests, no display needed
```
`pyproject.toml` + `uv.lock` are the source of truth for dev; `requirements*.txt` exist only for the
Windows release workflow (`requirements-build.txt` = PyInstaller and friends).

**Config and profiles** — path resolution lives in `utils/paths.py` (Phase 1, in progress); do not hardcode
paths. `config.json` is runtime state and gitignored — copy `config.example.json` for a starting point.
Profiles sit in `profiles/` next to the repo from source, in `%APPDATA%\Aion2 TM\` when frozen;
`profiles/last_profile.txt` is rewritten every launch and untracked.

**Build the Windows exe** (Windows only, output in `dist/`):
```bash
uv sync --group build && uv run pyinstaller "Aion2 TM.spec"
```
**Dev-only stub** — `.venv/lib/python3.12/site-packages/winsound.py` is a local shim so the Windows-only
`import winsound` does not explode on Linux. Phase 1 replaces it with a real cross-platform sound backend
and deletes the stub. Never commit it, never ship it.
