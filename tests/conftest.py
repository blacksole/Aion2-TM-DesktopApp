"""Shared test setup: headless Qt so the suite runs on CI and on Linux without a display."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test MainWindow start the real startup update-check QThread.
os.environ.setdefault("AION2TM_NO_UPDATE_CHECK", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
