from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    sid: str
    label: str
    pubkey: bytes
    privkey: bytes
    psk: bytes
    session_key: Optional[bytes] = None
    sas: Optional[str] = None
    device_name: Optional[str] = None

    def wipe_keys(self) -> None:
        """Zero all key material in-place."""
        for attr in ("privkey", "psk", "session_key"):
            val = getattr(self, attr)
            if val:
                object.__setattr__(self, attr, bytes(len(val)))
        object.__setattr__(self, "session_key", None)
        object.__setattr__(self, "sas", None)
