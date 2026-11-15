"""Small, dependency-light tests for Nika's opt-in metering boundary."""

import asyncio
import hashlib
import hmac
import importlib.util
from pathlib import Path

import pytest


# Load the leaf module without the package's full AI stack. This lets the
# boundary checks run even when optional model dependencies are unavailable.
module_path = Path(__file__).resolve().parents[1] / "open_notebook/utils/nika_metering.py"
spec = importlib.util.spec_from_file_location("nika_metering_leaf", module_path)
nika_metering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nika_metering)


def test_signed_context_is_bound_to_source(monkeypatch):
    secret = "s" * 48
    monkeypatch.setenv("NIKA_METERING_SHARED_SECRET", secret)
    context = {
        "workspace_id": "workspace-id",
        "operation_id": "operation-id",
        "signature": hmac.new(
            secret.encode(), b"workspace-id|operation-id|source:one",
            hashlib.sha256,
        ).hexdigest(),
    }
    nika_metering.validate_context("source:one", context)
    with pytest.raises(ValueError, match="signature"):
        nika_metering.validate_context("source:two", context)


def test_metering_callbacks_require_safe_destination(monkeypatch):
    monkeypatch.setenv("NIKA_METERING_SHARED_SECRET", "s" * 48)
    monkeypatch.setenv("NIKA_METERING_BASE_URL", "http://169.254.169.254")
    with pytest.raises(ValueError, match="HTTPS or loopback"):
        asyncio.run(nika_metering.report(
            "/internal/source-engine/embedding/plan", {"batch_count": 1},
        ))
