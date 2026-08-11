"""
Bootstrap manifest.db for all tenant directories that are missing one.
Run once: python scripts/bootstrap_manifests.py
"""
import sqlite3
import hashlib
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "tenants"

MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest (
    doc_id          TEXT PRIMARY KEY,
    file_hash       TEXT NOT NULL,
    parse_status    TEXT DEFAULT 'PENDING',
    last_indexed_at TEXT,
    error_message   TEXT,
    page_count      INTEGER,
    file_size_bytes INTEGER
);
"""

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def bootstrap_tenant(tenant_dir: Path):
    manifest_db = tenant_dir / "manifest.db"
    conn = sqlite3.connect(manifest_db)
    conn.execute(MANIFEST_SCHEMA)
    conn.commit()

    # Scan raw/ and register any existing files
    raw_dir = tenant_dir / "raw"
    if raw_dir.exists():
        for f in raw_dir.iterdir():
            if not f.is_file():
                continue
            file_hash = sha256_file(f)
            size = f.stat().st_size
            # Check if already in manifest
            existing = conn.execute(
                "SELECT doc_id FROM manifest WHERE doc_id = ?", (f.name,)
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO manifest
                       (doc_id, file_hash, parse_status, last_indexed_at, file_size_bytes)
                       VALUES (?, ?, 'SUCCESS', datetime('now'), ?)""",
                    (f.name, file_hash, size)
                )
                print(f"  [OK] Registered: {f.name} ({size} bytes)")
            else:
                print(f"  [--] Already registered: {f.name}")

    conn.commit()
    conn.close()
    print(f"[OK] manifest.db ready for {tenant_dir.name}")


if __name__ == "__main__":
    if not DATA_ROOT.exists():
        print(f"Data root not found: {DATA_ROOT}")
        exit(1)

    tenant_dirs = [d for d in DATA_ROOT.iterdir()
                   if d.is_dir() and not d.name.startswith("audit_") and not d.name.startswith("{")]

    print(f"Found {len(tenant_dirs)} tenants: {[d.name for d in tenant_dirs]}\n")
    for tenant_dir in tenant_dirs:
        print(f"Bootstrapping {tenant_dir.name}...")
        try:
            bootstrap_tenant(tenant_dir)
        except Exception as e:
            print(f"  [ERR] Error: {e}")
        print()

    print("Done. All tenants have manifest.db.")
