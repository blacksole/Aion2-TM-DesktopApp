"""core/news_checker.py + ui/news_dialog.py: fetch the latest
companion.g-place.de WordPress post and offer it as a popup.

Deliberately minimal (Teil 2, @koordinator 2026-09-26) -- see both
modules' docstrings. This just locks down the one thing already decided:
the standard `/wp-json/wp/v2/posts` shape parses correctly, HTML in
title/excerpt is stripped for plain-text display, and network/shape
failures always resolve to `no_news` rather than raising.
"""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core import news_checker as nc  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wp_payload(posts):
    return json.dumps(posts).encode("utf-8")


def test_fetches_and_strips_html_from_title_and_excerpt(monkeypatch):
    posts = [{
        "id": 42,
        "title": {"rendered": "Season 3 is <em>live</em>!"},
        "excerpt": {"rendered": "<p>Read more &amp; enjoy.</p>\n"},
        "link": "https://companion.g-place.de/season-3/",
        "date": "2026-09-26T12:00:00",
    }]
    monkeypatch.setattr(
        nc.urllib.request, "urlopen", lambda *a, **k: _Resp(_wp_payload(posts))
    )
    checker = nc.NewsChecker()
    emitted = []
    checker.post_available.connect(lambda *args: emitted.append(args))

    checker.run()

    assert emitted == [(42, "Season 3 is live!", "Read more & enjoy.", "https://companion.g-place.de/season-3/", "2026-09-26T12:00:00")]


def test_no_posts_emits_no_news(monkeypatch):
    monkeypatch.setattr(nc.urllib.request, "urlopen", lambda *a, **k: _Resp(_wp_payload([])))
    checker = nc.NewsChecker()
    no_news = []
    checker.no_news.connect(lambda: no_news.append(True))

    checker.run()

    assert no_news == [True]


def test_network_failure_emits_no_news_not_an_exception(monkeypatch):
    def _boom(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(nc.urllib.request, "urlopen", _boom)
    checker = nc.NewsChecker()
    no_news = []
    checker.no_news.connect(lambda: no_news.append(True))

    checker.run()  # must not raise

    assert no_news == [True]


def test_malformed_post_without_a_title_emits_no_news(monkeypatch):
    posts = [{"id": 1, "title": {"rendered": ""}, "excerpt": {"rendered": ""}, "link": ""}]
    monkeypatch.setattr(
        nc.urllib.request, "urlopen", lambda *a, **k: _Resp(_wp_payload(posts))
    )
    checker = nc.NewsChecker()
    no_news = []
    checker.no_news.connect(lambda: no_news.append(True))

    checker.run()

    assert no_news == [True]


def test_news_dialog_shows_title_and_excerpt(qapp):
    from ui.news_dialog import NewsDialog
    from tests.conftest import destroy_window

    dlg = NewsDialog("Hello", "World", "https://x", language="en", parent=None)
    try:
        assert dlg.windowTitle() == "News"
    finally:
        dlg.close()
        destroy_window(dlg)


def test_news_dialog_buttons_follow_the_app_language(qapp):
    """tobia, 2026-09-26: buttons must be translated like the rest of the
    app, not hardcoded English -- same tr()/TRANSLATIONS mechanism every
    other dialog already uses."""
    from PySide6.QtWidgets import QPushButton
    from ui.news_dialog import NewsDialog
    from tests.conftest import destroy_window

    dlg = NewsDialog("Hello", "World", "https://x", language="de", parent=None)
    try:
        texts = {btn.text() for btn in dlg.findChildren(QPushButton)}
        assert texts == {"Schließen", "Öffnen"}
    finally:
        dlg.close()
        destroy_window(dlg)


def test_news_popup_is_enabled():
    """tobia, 2026-09-26 (verbatim): "Das News update soll auf jedenfall
    jetzt schon mit rein - damit ich Nachrichten ueber die Webseite an die
    App user schicken kann" -- live, no longer gated pending approval."""
    from ui.news_dialog import NEWS_POPUP_ENABLED
    assert NEWS_POPUP_ENABLED is True


def test_main_window_shows_a_post_only_once(monkeypatch):
    """Same "remembered across restarts, not per profile" persistence as
    dps_meter_path/avatar in config.json (tobia asked for this,
    2026-09-26) -- a post already shown (by id) must not pop up again on
    the next app start, and a lower/equal id is "nothing new"."""
    import ui.main_window as mw

    win = mw.MainWindow.__new__(mw.MainWindow)
    win.language = "en"
    win._last_seen_news_id = 5
    saved = []
    monkeypatch.setattr(mw.MainWindow, "_save_app_config", lambda self: saved.append(self._last_seen_news_id))
    shown = []
    monkeypatch.setattr(
        mw, "NewsDialog",
        lambda title, excerpt, link, date="", language=None, parent=None: shown.append((title, excerpt, link, date, language)) or _FakeDialog(),
    )

    mw.MainWindow._on_news_post_available(win, 5, "Old", "old excerpt", "https://x/old", "2026-09-20T10:00:00")
    assert shown == []
    assert saved == []
    assert win._last_seen_news_id == 5

    mw.MainWindow._on_news_post_available(win, 7, "New", "new excerpt", "https://x/new", "2026-09-26T10:00:00")
    assert shown == [("New", "new excerpt", "https://x/new", "2026-09-26T10:00:00", "en")]
    assert saved == [7]
    assert win._last_seen_news_id == 7


class _FakeDialog:
    def exec(self):
        return None
