import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
import os
import sys
from pathlib import Path
import asyncio

# Setup paths
project_root = Path(f"{PROJECT_ROOT}")
sys.path.append(str(project_root))

from auth.allowlist import AllowlistManager
from pipeline import check_for_changes

def test_allowlist():
    print("Testing AllowlistManager...")
    mgr = AllowlistManager()
    
    # Test valid tenant/users
    telegram_allowed = mgr.is_telegram_user_allowed('tenant_1', 'telegram_user_123')
    whatsapp_allowed = mgr.is_whatsapp_user_allowed('tenant_1', 'whatsapp_user_456')
    print(f"Telegram user allowed: {telegram_allowed}")
    print(f"WhatsApp user allowed: {whatsapp_allowed}")
    
    # Test fallback compatibility
    legacy_allowed = mgr.is_telegram_user_allowed('tenant_1', '1990648223') # from original json if untouched
    print(f"Legacy user allowed: {legacy_allowed}")
    
    # Test unauthorized
    unauth = mgr.is_whatsapp_user_allowed('tenant_1', 'hacker_999')
    print(f"Unauthorized user allowed: {unauth}")
    print("Allowlist test complete.\n")

def test_incremental_ingestion():
    print("Testing Incremental Ingestion Logic...")
    raw_dir = str(project_root / "data" / "tenants" / "tenant_1" / "raw")
    
    # Create raw dir if missing
    os.makedirs(raw_dir, exist_ok=True)
    
    # Create a test file
    test_file = Path(raw_dir) / "test.txt"
    with open(test_file, "w") as f:
        f.write("Hello World")
        
    print(f"Created {test_file}")
    
    # First check (should be True since it's new)
    changed_1 = check_for_changes(raw_dir, "tenant_1")
    print(f"First check (expect True): {changed_1}")
    
    # Second check (should be False since it hasn't changed)
    changed_2 = check_for_changes(raw_dir, "tenant_1")
    print(f"Second check (expect False): {changed_2}")
    
    # Modify file
    with open(test_file, "w") as f:
        f.write("Hello World 2")
        
    # Third check (should be True since it changed)
    changed_3 = check_for_changes(raw_dir, "tenant_1")
    print(f"Third check (expect True): {changed_3}")
    
    # Cleanup test file
    test_file.unlink()
    
    # Final check (won't detect deletions currently with just REPLACE, but we can verify it runs)
    print("Incremental ingestion test complete.\n")

if __name__ == "__main__":
    test_allowlist()
    test_incremental_ingestion()
