import json
import os
import asyncio
from typing import Dict, Any, Optional

SETTINGS_FILE = "guild_settings.json"

DEFAULT_GUILD_SETTINGS = {
    "is_active": True,
    "log_channel_id": None,
    "auto_delete": True,
    "notify_channel": True,
    "scams_detected_count": 0,
    
    # Subscriber Verification Settings
    "sub_channel_id": None,
    "sub_role_id": None,
    "sub_log_channel_id": None,
    "sub_channel_url": None,
    "sub_target_aliases": [],
    "sub_panel_message_id": None,
    "sub_panel_channel_id": None
}

class Database:
    def __init__(self, filepath: str = SETTINGS_FILE):
        self.filepath = filepath
        self.lock = asyncio.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4)

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
                self._save()
            return self._data[gid]

    async def set_log_channel(self, guild_id: int, channel_id: int) -> None:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data[gid]["log_channel_id"] = channel_id
            self._save()

    async def set_active_status(self, guild_id: int, is_active: bool) -> None:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data[gid]["is_active"] = is_active
            self._save()

    async def increment_scam_count(self, guild_id: int) -> int:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data[gid]["scams_detected_count"] = self._data[gid].get("scams_detected_count", 0) + 1
            self._save()
            return self._data[gid]["scams_detected_count"]

    async def update_sub_setting(self, guild_id: int, key: str, value: Any) -> None:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data[gid][key] = value
            self._save()

    async def clear_sub_aliases(self, guild_id: int) -> None:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data[gid]["sub_target_aliases"] = []
            self._save()

    async def add_sub_alias(self, guild_id: int, alias: str) -> bool:
        async with self.lock:
            gid = str(guild_id)
            if gid not in self._data:
                self._data[gid] = DEFAULT_GUILD_SETTINGS.copy()
            
            aliases = self._data[gid].get("sub_target_aliases", [])
            if alias.lower() not in aliases:
                aliases.append(alias.lower())
                self._data[gid]["sub_target_aliases"] = aliases
                self._save()
                return True
            return False

    async def reset_sub_setup(self, guild_id: int) -> None:
        async with self.lock:
            gid = str(guild_id)
            if gid in self._data:
                self._data[gid]["sub_channel_id"] = None
                self._data[gid]["sub_role_id"] = None
                self._data[gid]["sub_log_channel_id"] = None
                self._data[gid]["sub_channel_url"] = None
                self._data[gid]["sub_target_aliases"] = []
                self._data[gid]["sub_panel_message_id"] = None
                self._data[gid]["sub_panel_channel_id"] = None
                self._save()

db = Database()
