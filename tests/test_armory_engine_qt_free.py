"""The one rule ``ItemDatabase/armory_engine`` exists to enforce: no Qt.

Audit B-armory.md §3.2 puts ``from PySide6... at module import`` first on the
list of coupling that blocks a recommendation engine, and rates it HIGH for
testability: none of the pure functions could be imported without Qt
installed AND the whole 23 000-line module executing, global
``QComboBox.showPopup`` monkey-patch included.

Stage 1 fixed that by moving them.  This module makes it stay fixed, and
checks it the only way that actually proves anything: in a **subprocess**,
with a meta-path finder installed before the import that makes any PySide6
import raise.  A plain in-process ``import armory_engine.x`` cannot prove it —
PySide6 is already in ``sys.modules`` by the time any test runs (conftest and
pytest-qt both pull it in), so a stray ``from PySide6 import ...`` inside the
engine would silently succeed and this file would pass while the rule was
broken.

The subprocess also gets a clean ``sys.modules``, which catches the subtler
failure: a module in the engine importing something from *app.py* (which
would drag Qt in transitively, through no PySide6 line of its own).
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "ItemDatabase" / "armory_engine"

#: Every module in the package, discovered rather than listed: a module added
#: later is covered without anyone remembering to add it here.
ENGINE_MODULES = sorted(
    p.stem if p.stem != "__init__" else "__init__"
    for p in ENGINE.glob("*.py")
)

#: Run in the child: block PySide6 (and shiboken, its own dependency) at the
#: finder level, then import the module and report back.  Takes the module
#: name and the package's parent directory as argv, with no string formatting
#: of its own -- a .format()/f-string mix in a program-as-a-string is a trap.
BLOCKED_IMPORT_PROGRAM = """
import importlib
import sys

BLOCKED = ("PySide6", "shiboken6")


class Blocker:
    '''A meta-path finder that refuses the Qt packages and their submodules.

    Installed at position 0, so it is consulted before anything that could
    actually find them.  Raising ImportError from find_spec (rather than
    returning None) makes the refusal loud and attributable instead of
    degrading into "module not found somewhere".
    '''

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError(fullname + " is not importable: armory_engine must be Qt-free")
        return None


sys.meta_path.insert(0, Blocker())

module_name, engine_parent = sys.argv[1], sys.argv[2]
sys.path.insert(0, engine_parent)

target = "armory_engine" if module_name == "__init__" else "armory_engine." + module_name
importlib.import_module(target)

leaked = sorted(name for name in sys.modules if name.split(".")[0] in BLOCKED)
if leaked:
    raise AssertionError(target + " pulled in " + repr(leaked))
print("OK", target)
"""


@pytest.mark.parametrize("module_name", ENGINE_MODULES)
def test_every_engine_module_imports_with_pyside6_blocked(module_name, tmp_path):
    """One subprocess per module, so a failure names the module."""
    script = tmp_path / "import_under_blocker.py"
    script.write_text(BLOCKED_IMPORT_PROGRAM, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), module_name, str(ENGINE.parent)],
        capture_output=True, text=True, timeout=60,
        # A bare environment: no QT_QPA_PLATFORM to honour, nothing to find a
        # display with, and no inherited sys.path via PYTHONPATH.
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"armory_engine.{module_name} is not Qt-free:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert result.stdout.strip().startswith("OK")


def test_the_package_really_has_the_modules_the_two_stages_promised():
    """A guard on the guard: if the glob above found nothing, every
    parametrized test would vacuously pass.

    Stage 2 (2026-09-19) added ``providers``/``score``/``recommend``.
    ``providers`` is the interesting one for THIS module: it is the first
    engine module that touches the filesystem, and the rule it has to keep
    is that it does so with ``json`` and ``pathlib`` — a Qt-free
    ``DetailProvider`` is the entire reason a recommendation can be computed
    on the landing page, before any Armory window exists.
    """
    assert set(ENGINE_MODULES) >= {
        "__init__", "arcana", "daevanion", "enchant", "explain",
        "model", "providers", "recommend", "score", "sets", "stats",
        "substats", "transfer",
    }


def test_no_engine_module_imports_pyside6():
    """The static half, as a cheap and readable backstop to the subprocess.

    Catches a PySide6 import hidden inside a function body, which the import
    test above would not reach (it imports the module, it does not call
    everything in it).

    Parsed, not grepped: the engine's docstrings talk ABOUT PySide6 at length
    (that is the point of the package), so a text search would flag the very
    comments explaining the rule.  ``ast`` sees only real imports.
    """
    offenders = {}
    for path in sorted(ENGINE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] in ("PySide6", "shiboken6"):
                    offenders[f"{path.name}:{node.lineno}"] = name
    assert not offenders, f"Qt imported inside the engine: {offenders}"
