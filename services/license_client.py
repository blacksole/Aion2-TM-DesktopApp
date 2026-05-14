import requests


class LicenseClient:
    def __init__(self, base_url: str, app_id: str):
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id

    def validate_license(
        self,
        license_key: str,
        device_id: str,
        device_name: str | None = None,
    ) -> dict:
        try:
            response = requests.post(
                f"{self.base_url}/api/license/validate",
                json={
                    "app_id": self.app_id,
                    "license_key": license_key,
                    "device_id": device_id,
                    "device_name": device_name,
                },
                timeout=10,
            )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as error:
            return {
                "valid": False,
                "reason": "server_unreachable",
                "message": str(error),
            }