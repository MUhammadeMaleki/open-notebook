"""Optional Nika-only embedding checkpoints; never used by ordinary jobs."""

import hashlib
import hmac
import os
from urllib.parse import urlsplit

import httpx


def validate_context(source_id: str, context: dict[str, str]) -> None:
    """Require a Nika signature before accepting privileged metering metadata."""
    secret = os.getenv("NIKA_METERING_SHARED_SECRET", "")
    if len(secret) < 32:
        raise ValueError("Nika metering is not configured")
    if set(context) != {"workspace_id", "operation_id", "signature"}:
        raise ValueError("Invalid Nika metering context")
    workspace_id = context["workspace_id"]
    operation_id = context["operation_id"]
    signature = context["signature"]
    if not all(isinstance(value, str) for value in context.values()):
        raise ValueError("Invalid Nika metering context")
    message = f"{workspace_id}|{operation_id}|{source_id}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid Nika metering signature")


async def report(path: str, payload: dict) -> dict:
    """Send only identifiers and hashes to Nika over HTTPS or loopback HTTP."""
    base_url = os.getenv("NIKA_METERING_BASE_URL", "").rstrip("/")
    secret = os.getenv("NIKA_METERING_SHARED_SECRET", "")
    parsed = urlsplit(base_url)
    if (not base_url or not parsed.hostname or parsed.path not in {"", "/"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Invalid Nika metering URL")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    ):
        raise ValueError("Nika metering requires HTTPS or loopback HTTP")
    if not path.startswith("/internal/source-engine/embedding/"):
        raise ValueError("Invalid Nika metering endpoint")
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"X-Nika-Engine-Key": secret},
        timeout=15,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        response = await client.post(path, json=payload)
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict):
        raise ValueError("Invalid Nika metering response")
    return result
