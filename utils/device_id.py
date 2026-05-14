import hashlib
import platform
import uuid


def get_device_id() -> str:
    raw = f"{platform.node()}-{platform.system()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()