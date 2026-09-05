"""Small local dev-convenience window for check_for_updates.py (User-Wunsch,
2026-09-05: "kannst du eventuell während des Fetches ein kleines
Fortschrittsfenster bauen? Das Fenster wird weiterhin nur hier angezeigt")
-- purely a "don't just stare at a blank terminal for several minutes"
aid while the VS Code task (or a manual run) works through the fetch/
compute scripts. Never required: check_for_updates.py falls back to plain
console output if PySide6 can't be imported (or this window fails for any
other reason), since this is a convenience, not the source of truth --
the terminal/log output it's layered on top of already covers everything
on its own.

Deliberately single-threaded, not a QThread-based worker: an earlier
version ran the fetch loop on a background QThread so the window's own
event loop kept pumping throughout, but that crashed with no error output
at all under this project's headless test setup -- not confident enough
in that design to ship a dev tool that can silently die. Instead, the
fetch loop runs directly on the main thread and calls
QApplication.processEvents() after each step's status update, so the
window repaints/responds between steps. The one real tradeoff: while any
SINGLE step's own (possibly slow) network calls are in flight, the window
won't repaint until that step returns -- acceptable for a local dev aid
that already tells you "which step is running" before each one starts.
"""

import time

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProgressWindow(QWidget):
    def __init__(self, steps: list[str]):
        super().__init__()
        self._steps = steps
        self.setWindowTitle("Aion2 TM -- Game Data Check")
        self.setFixedSize(420, 480)

        layout = QVBoxLayout(self)

        self._title = QLabel("Checking questlog.gg / talentbuilds.com for changes...")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._bar = QProgressBar()
        self._bar.setRange(0, len(steps))
        layout.addWidget(self._bar)

        self._list = QListWidget()
        for script in steps:
            self._list.addItem(QListWidgetItem(f"⏳  {script}"))
        layout.addWidget(self._list, 1)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._close_btn = QPushButton("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.close)
        layout.addWidget(self._close_btn)

    def on_step_started(self, script: str, index: int, total: int):
        self._title.setText(f"Running {script} ({index}/{total})...")
        item = self._list.item(index - 1)
        if item:
            item.setText(f"🔄  {script}")

    def on_step_done(self, script: str, ok: bool):
        index = self._steps.index(script)
        item = self._list.item(index)
        if item:
            item.setText(f"{'✅' if ok else '❌'}  {script}")
        self._bar.setValue(index + 1)

    def on_all_done(self, changes: dict, failed: list[str]):
        total_lines = sum(len(v) for v in changes.values())
        if failed:
            self._title.setText(f"Done, with {len(failed)} failure(s).")
            self._summary.setText(f"Failed: {', '.join(failed)}\nSee the terminal/log for details.")
        elif not changes:
            self._title.setText("Done -- no data changes.")
        else:
            self._title.setText(f"Done -- {len(changes)} file(s) changed, {total_lines} value(s).")
            self._summary.setText("Full exact diff printed in the terminal and in check_for_updates.log.")
        self._close_btn.setEnabled(True)


def run_with_progress_window(steps: list[str], run_fn, snapshot_fn, diff_fn, before: dict, initial_log_lines: list[str]):
    """Runs the given steps (via run_fn(script, log_lines) -> bool, same
    signature check_for_updates._run already has) with a live window shown
    the whole time. Blocks until every step finishes AND the user closes
    the window (so the final summary stays visible instead of vanishing
    the instant work completes). Returns (log_lines, changes, failed) --
    exactly what main() needs to write the log and print the final
    summary, same shape as the no-GUI fallback path."""
    app = QApplication.instance() or QApplication([])
    window = ProgressWindow(steps)
    window.show()
    app.processEvents()

    log_lines = list(initial_log_lines)
    failed: list[str] = []
    for i, script in enumerate(steps, 1):
        window.on_step_started(script, i, len(steps))
        app.processEvents()
        ok = run_fn(script, log_lines)
        if not ok:
            failed.append(script)
        window.on_step_done(script, ok)
        app.processEvents()

    after = snapshot_fn()
    changes = diff_fn(before, after)
    window.on_all_done(changes, failed)

    # Blocks here until the user clicks Close (or the native X) -- a
    # small local event loop scoped to just this window, not the whole
    # QApplication, so it plays nicely regardless of whether this is
    # running standalone or (in principle) embedded in a larger app.
    while window.isVisible():
        app.processEvents()
        time.sleep(0.05)

    return log_lines, changes, failed
