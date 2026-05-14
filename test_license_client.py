import platform

from core.app_config import APP_ID, LICENSE_SERVER_URL
from services.license_client import LicenseClient
from utils.device_id import get_device_id


license_client = LicenseClient(
    base_url=LICENSE_SERVER_URL,
    app_id=APP_ID,
)

result = license_client.validate_license(
    license_key="6E51-RD0J-NKVH-BQG4",
    device_id=get_device_id(),
    device_name=platform.node(),
)

print(result)