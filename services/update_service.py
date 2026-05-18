import requests

from core.version import APP_VERSION


class UpdateService:
    def __init__(self):
        self.latest_version = None
        self.release_url = None
        self.changelog = None

    def check_for_update(self):
        try:
            response = requests.get(
                "https://api.github.com/repos/blacksole/Aion2-Task-Manager/releases/latest",
                timeout=10,
            )

            if response.status_code != 200:
                return {
                    "update_available": False,
                    "error": "Could not check updates",
                }

            data = response.json()

            latest_tag = data.get("tag_name", "")
            self.latest_version = latest_tag.replace("v", "")
            self.release_url = data.get("html_url")
            self.changelog = data.get("body", "")

            return {
                "update_available": self.is_newer_version(
                    self.latest_version,
                    APP_VERSION,
                ),
                "current_version": APP_VERSION,
                "latest_version": self.latest_version,
                "release_url": self.release_url,
                "changelog": self.changelog,
            }

        except requests.RequestException as e:
            return {
                "update_available": False,
                "error": str(e),
            }

    def is_newer_version(self, latest, current):
        def normalize(version):
            return tuple(
                int(part)
                for part in version.split(".")
                if part.isdigit()
            )

        return normalize(latest) > normalize(current)