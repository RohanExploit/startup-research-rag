import json
import logging
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import AUTH_FILE

logging.basicConfig(level=logging.INFO)

class AllowlistManager:
    def __init__(self, auth_file=None):
        self.auth_file = Path(auth_file) if auth_file else AUTH_FILE
        self.auth_file.parent.mkdir(parents=True, exist_ok=True)
        self.allowlist = self._load()

    def _load(self):
        if not self.auth_file.exists():
            default = {
                "tenant_1": {
                    "telegram_users": ["telegram_user_123"],
                    "whatsapp_users": ["whatsapp_user_456"],
                    "description": "Default Prototype Tenant"
                }
            }
            self._save(default)
            return default
            
        with open(self.auth_file, "r") as f:
            return json.load(f)
            
    def _save(self, data):
        with open(self.auth_file, "w") as f:
            json.dump(data, f, indent=2)
            
    def is_telegram_user_allowed(self, tenant_id: str, user_id: str) -> bool:
        tenant = self.allowlist.get(tenant_id)
        if not tenant:
            return False
        # Fallback to 'users' for backwards compatibility
        return user_id in tenant.get("telegram_users", tenant.get("users", []))

    def is_whatsapp_user_allowed(self, tenant_id: str, user_id: str) -> bool:
        tenant = self.allowlist.get(tenant_id)
        if not tenant:
            return False
        # Fallback to 'users' for backwards compatibility
        return user_id in tenant.get("whatsapp_users", tenant.get("users", []))

    def is_user_allowed(self, tenant_id: str, user_id: str) -> bool:
        """Channel-agnostic check: allowed if the user is on either channel's list."""
        return (self.is_telegram_user_allowed(tenant_id, user_id)
                or self.is_whatsapp_user_allowed(tenant_id, user_id))

if __name__ == "__main__":
    mgr = AllowlistManager()
    print(f"Is Telegram user allowed? {mgr.is_telegram_user_allowed('tenant_1', 'telegram_user_123')}")
