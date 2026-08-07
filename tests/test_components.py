import sys
import os
import pytest
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from auth.allowlist import AllowlistManager

def test_allowlist_manager(tmp_path):
    auth_file = tmp_path / "allowlist.json"
    mgr = AllowlistManager(auth_file=str(auth_file))
    
    assert mgr.is_user_allowed("tenant_1", "telegram_user_123") == True
    assert mgr.is_user_allowed("tenant_1", "unknown_user") == False
    assert mgr.is_user_allowed("unknown_tenant", "telegram_user_123") == False

# Can add more mock tests for router, chunking, etc.
def test_dummy():
    assert True
