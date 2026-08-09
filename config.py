"""
Central config. Single source of truth for paths + validation.

YOU control everything here:
  - PROJECT_ROOT auto-detects where this repo lives (works on R:, e:, anywhere).
    Override anytime with env var PROJECT_ROOT.
  - Validation is toggleable. Turn it off, loosen the pattern, or add tenants
    without touching code elsewhere.

Nothing else in the codebase should hardcode an absolute path. Import from here.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# PATHS  (your knob: set env PROJECT_ROOT to force a location; else auto-detect)
# --------------------------------------------------------------------------
# config.py sits at the repo root, so its parent IS the project root.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parent))

# Load .env before anything else in the app reads os.environ (e.g.
# NVIDIA_API_KEY for the Ollama fallback in generation/answer.py). Every
# module imports config first, so this is the one place that guarantees it.
load_dotenv(PROJECT_ROOT / ".env")

DATA_ROOT           = PROJECT_ROOT / "data" / "tenants"
STAGING_ROOT        = PROJECT_ROOT / "data" / "staging"
AUTH_FILE           = PROJECT_ROOT / "auth" / "allowlist.json"
ENCRYPTION_KEY_PATH = Path(os.environ.get("ENCRYPTION_KEY_PATH", PROJECT_ROOT / ".encryption_key"))


def tenant_dir(tenant_id: str) -> Path:
    """Validated path to a tenant's data dir. Use this instead of DATA_ROOT / tenant_id."""
    return DATA_ROOT / validate_tenant_id(tenant_id)


# --------------------------------------------------------------------------
# VALIDATION CONTROLS  (your knobs)
# --------------------------------------------------------------------------
# Master switch. Set env VALIDATE_TENANT_ID=0 to disable ALL tenant_id checks.
VALIDATE_TENANT_ID = os.environ.get("VALIDATE_TENANT_ID", "1") != "0"

# What a legal tenant_id looks like. Edit freely. Default: letters/digits/_/-.
TENANT_ID_PATTERN = re.compile(os.environ.get("TENANT_ID_PATTERN", r"^[A-Za-z0-9_-]{1,64}$"))

# Master switch for upload filename sanitizing.
VALIDATE_FILENAMES = os.environ.get("VALIDATE_FILENAMES", "1") != "0"

# Master switch for upload_id checks. Set env VALIDATE_UPLOAD_ID=0 to disable.
VALIDATE_UPLOAD_ID = os.environ.get("VALIDATE_UPLOAD_ID", "1") != "0"

# upload_id is always server-generated via uuid.uuid4() (see api/main.py
# upload_file). What a legal upload_id looks like. Edit freely.
UPLOAD_ID_PATTERN = re.compile(os.environ.get("UPLOAD_ID_PATTERN", r"^[0-9a-fA-F-]{36}$"))


def validate_tenant_id(tenant_id: str) -> str:
    """
    Returns tenant_id if allowed, else raises ValueError.
    Blocks path traversal (.. / \\ / absolute drive) that would let one tenant
    read another's data. Disable via VALIDATE_TENANT_ID=0 if you need to.
    """
    if not VALIDATE_TENANT_ID:
        return tenant_id
    if not isinstance(tenant_id, str) or not TENANT_ID_PATTERN.match(tenant_id):
        raise ValueError(f"Invalid tenant_id: {tenant_id!r}")
    return tenant_id


def validate_upload_id(upload_id: str) -> str:
    """
    Returns upload_id if it looks like a server-generated uuid4, else raises
    ValueError. upload_id is used to build a filesystem path
    (staging/<upload_id>/...), so a caller-supplied value like ".." must be
    rejected before it reaches any mkdir/move/copy call. Disable via
    VALIDATE_UPLOAD_ID=0 if you need to.
    """
    if not VALIDATE_UPLOAD_ID:
        return upload_id
    if not isinstance(upload_id, str) or not UPLOAD_ID_PATTERN.match(upload_id):
        raise ValueError(f"Invalid upload_id: {upload_id!r}")
    return upload_id


def safe_filename(name: str) -> str:
    """
    Strip any directory component from an uploaded filename so it cannot escape
    the staging dir (e.g. '..\\..\\windows\\x'). Returns just the base name.
    Disable via VALIDATE_FILENAMES=0.
    """
    if not VALIDATE_FILENAMES:
        return name
    base = os.path.basename(str(name).replace("\\", "/"))
    base = base.strip().lstrip(".") or "upload"
    return base


# --------------------------------------------------------------------------
# RUNTIME KNOBS  (all env-overridable — your control)
# --------------------------------------------------------------------------
DEFAULT_TENANT_ID = os.environ.get("DEFAULT_TENANT_ID", "tenant_1")

# Ollama model id + base URL. Previously hardcoded and duplicated across
# api/main.py, generation/answer.py, retrieval/router.py,
# retrieval/tabular_queries.py, ingestion/extract_entities.py and
# ingestion/summarize_communities.py — centralized here so it's set once.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Seconds before an outbound LLM/API call is abandoned.
API_TIMEOUT = float(os.environ.get("API_TIMEOUT", "60"))

# Max upload size in bytes (default 50 MB). Uploads larger are rejected 413.
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(50 * 1024 * 1024)))

# Seed for Louvain community detection so pipeline runs are reproducible.
LOUVAIN_SEED = int(os.environ.get("LOUVAIN_SEED", "42"))

# --------------------------------------------------------------------------
# API AUTH  (optional gate — OFF by default so local dev on 127.0.0.1 is
# frictionless. Turn ON before ever binding 0.0.0.0. See start.py docstring.)
# --------------------------------------------------------------------------
def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def require_api_key_enabled() -> bool:
    """Whether the X-API-Key gate is active. Read live from env so tests (and a
    running server told to reload) reflect the current value without reimport."""
    return _truthy(os.environ.get("REQUIRE_API_KEY", "0"))


def get_api_key() -> str:
    """The expected X-API-Key value. Empty when unset (misconfig if the gate is
    enabled — the dependency fails closed in that case)."""
    return os.environ.get("API_KEY", "").strip()


# --- Text-to-SQL guardrails (retrieval/tabular_queries.py) ---
# Row cap injected when the generated SQL has no LIMIT.
SQL_ROW_LIMIT = int(os.environ.get("SQL_ROW_LIMIT", "200"))
# Tables the generated SQL is allowed to read. Empty set = allow any (off).
SQL_ALLOWED_TABLES = set(
    t for t in os.environ.get(
        "SQL_ALLOWED_TABLES", "students,student_subjects,needs_review"
    ).split(",") if t.strip()
)
