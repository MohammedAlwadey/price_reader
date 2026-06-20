import base64
import hashlib
import json
import os
import platform
import uuid
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


BASE_DIR = Path(__file__).resolve().parent.parent

LICENSE_FILE = BASE_DIR / "license.json"


PUBLIC_KEY_PEM = b"""
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApvswN0iKIU9HrZBNx6JC
bAuGB0K+4cVHWwN4ypbKbmbNIGVq5dfCDWPdFf+eUFKcK4t55j+LkmYG7blbly4V
qux54Scy1Zde+pkydoSjqaLf/2wGfCgZCGbh4U5NVtgv2kcQyFd943vLQMnOb0VJ
GO6auemjJ0VDijBdL6j/98UqgkRTDpMmjP2gz4bGcshRbf/qU4IJlPr4Uq1qSfwL
PtHo/OLyxB75XMMaQqtEGwqv2kPzUo/nl0cPhCMClfL3WaCR0/uGFJ9PU1hXP4n5
Xo5jWL6jY0nxtCJmptHWBrh7dI1cgqFlX+DoKUJjTUeyYLXsmCDAjaLYBu976D/f
WQIDAQAB
-----END PUBLIC KEY-----
"""


class LicenseError(Exception):
    pass


def get_server_fingerprint() -> str:
    raw = "|".join(
        [
            platform.node() or "",
            platform.system() or "",
            platform.machine() or "",
            platform.processor() or "",
            str(uuid.getnode()) or "",
            os.environ.get("COMPUTERNAME", ""),
            os.environ.get("PROCESSOR_IDENTIFIER", ""),
        ]
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_current_server_id() -> str:
    return get_server_fingerprint()


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_license_file() -> dict:
    if not LICENSE_FILE.exists():
        raise LicenseError("License file not found.")

    try:
        with LICENSE_FILE.open("r", encoding="utf-8") as f:
            license_data = json.load(f)
    except Exception:
        raise LicenseError("Invalid license file format.")

    if "payload" not in license_data or "signature" not in license_data:
        raise LicenseError("Invalid license file structure.")

    return license_data


def verify_license_signature(payload: dict, signature_b64: str) -> None:
    public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)

    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        raise LicenseError("Invalid license signature encoding.")

    try:
        public_key.verify(
            signature,
            _canonical_payload(payload),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        raise LicenseError("Invalid license signature.")


def validate_license() -> dict:
    license_data = load_license_file()

    payload = license_data["payload"]
    signature = license_data["signature"]

    verify_license_signature(payload, signature)

    expected_server_id = payload.get("server_id")
    current_server_id = get_current_server_id()

    if expected_server_id != current_server_id:
        raise LicenseError("License is not valid for this server.")

    expires = payload.get("expires")
    if not expires:
        raise LicenseError("License expiry date is missing.")

    try:
        expires_date = date.fromisoformat(expires)
    except ValueError:
        raise LicenseError("Invalid license expiry date.")

    if date.today() > expires_date:
        raise LicenseError("License has expired.")

    return payload


def get_license_payload() -> dict:
    return validate_license()


def get_license_limit(name: str, default=None):
    payload = validate_license()
    return payload.get(name, default)