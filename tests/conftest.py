"""
Shared pytest fixtures + a service-availability probe so live-service tests can
skip cleanly (honest skip, not a false failure) when Ollama / the API are down.
"""
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as _config


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def service_up(host: str, port: int) -> bool:
    return _port_open(host, port)


# Convenience skip markers importable via `from conftest import requires_api`
requires_api = pytest.mark.skipif(
    not _port_open("127.0.0.1", 8000), reason="API server not running on :8000"
)
requires_ollama = pytest.mark.skipif(
    not _port_open("127.0.0.1", 11434), reason="Ollama not running on :11434"
)


@pytest.fixture
def project_root() -> Path:
    return _config.PROJECT_ROOT


@pytest.fixture
def data_root() -> Path:
    return _config.DATA_ROOT
