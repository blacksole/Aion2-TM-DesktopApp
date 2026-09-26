"""Generic WordPress REST API "latest post" checker (Teil 2, @koordinator
2026-09-26): companion.g-place.de is becoming a WordPress news blog (design
by @designer); this is the technical plumbing that asks it for the newest
post at app start and hands it to a popup.

Deliberately generic for now -- format/frequency/dismiss-behaviour/i18n are
still being worked out once the WordPress site is actually live (per
@koordinator: "Details klaeren wir, sobald die WordPress-Seite technisch
steht"), so this only does the one thing that's already decided: fetch the
newest published post from the standard `/wp-json/wp/v2/posts` endpoint and
hand back a plain dict a caller can render however it likes.

Modeled on core/update_checker.py's UpdateChecker (same QThread + signal
shape, same "never raise into the caller, always resolve to a signal"
contract) so it drops into the same startup-timer pattern without inventing
a second convention.
"""

import html
import json
import re
import urllib.request

from PySide6.QtCore import QThread, Signal

# The standard WP REST API endpoint (WordPress core, no plugin required).
# `per_page=1` + `_fields=` keeps the response to just what's rendered,
# instead of the full post object (content, full HTML, meta, links, ...).
_POSTS_URL = (
    "https://companion.g-place.de/wp-json/wp/v2/posts"
    "?per_page=1&_fields=id,date,link,title,excerpt"
)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """WP's `title.rendered`/`excerpt.rendered` are HTML (WordPress always
    renders these server-side, even for a plain-text title) -- strip tags
    and turn entities back into text for a plain popup label. Not a full
    HTML sanitizer: this text is only ever displayed as plain text, never
    re-interpreted as HTML/inserted into a QTextBrowser, so no injection
    risk in stripping-instead-of-escaping here."""
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


class NewsChecker(QThread):
    # (post_id, title, excerpt, link)
    post_available = Signal(int, str, str, str)
    no_news = Signal()

    def run(self):
        try:
            post = self._fetch_latest_post()
            if post is None:
                self.no_news.emit()
                return

            post_id = post.get("id")
            title = _strip_html((post.get("title") or {}).get("rendered", ""))
            excerpt = _strip_html((post.get("excerpt") or {}).get("rendered", ""))
            link = post.get("link") or ""

            if not isinstance(post_id, int) or not title:
                self.no_news.emit()
                return

            self.post_available.emit(post_id, title, excerpt, link)
        except Exception:
            # Same policy as UpdateChecker: a WordPress hiccup (site not
            # live yet, DNS blip, malformed JSON) must never surface as a
            # startup error -- it's just "no news to show right now".
            self.no_news.emit()

    def _fetch_latest_post(self) -> dict | None:
        req = urllib.request.Request(
            _POSTS_URL, headers={"User-Agent": "Aion2-TM-NewsCheck"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            posts = json.loads(resp.read())
        if not posts:
            return None
        return posts[0]
