import requests
from pathlib import Path

from core.app_config import (
    AUTH_REQUIRED,
    API_URL,
    SERVER_API_KEY,
    APP_VERSION,
)


class AuthManager:
    def __init__(self):
        self.is_authenticated = False
        self.username = None
        self.user_id = None
        self.roles = []
        self.access_token = None

    def validate_access(self):
        print("validate_access gestartet")

        if not AUTH_REQUIRED:
            print("AUTH_REQUIRED = False")
            self.is_authenticated = True
            self.username = "Local Dev"
            self.user_id = "local"
            return True

        user_id = self.load_test_user_id()
        print("Geladene User ID:", repr(user_id))

        if not user_id:
            print("Keine User ID gefunden")
            return False

        try:
            print("API URL:", API_URL)
            print("API Key gesetzt:", bool(SERVER_API_KEY))

            response = requests.post(
                f"{API_URL}/validate",
                json={
                    "user_id": user_id,
                    "app_version": APP_VERSION,
                },
                headers={
                    "X-API-Key": SERVER_API_KEY,
                },
                timeout=30,
            )

            print("Status Code:", response.status_code)
            print("Response:", response.text)

            if response.status_code != 200:
                return False

            data = response.json()

            if data.get("allowed") is True:
                self.is_authenticated = True
                self.user_id = user_id
                self.username = f"Discord User {user_id}"
                return True

            return False

        except Exception as e:
            print("Auth Exception:", repr(e))
            return False

    def load_test_user_id(self):
        project_root = Path(__file__).resolve().parent.parent
        user_file = project_root / "test_user_id.txt"

        print("Suche test_user_id unter:", user_file)

        try:
            with open(user_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print("test_user_id.txt nicht gefunden")
            return ""

    def get_user_display_name(self):
        return self.username or "Unknown User"