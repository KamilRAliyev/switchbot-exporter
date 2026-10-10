"""Sink contract shared by all outputs, plus device naming helpers."""
from __future__ import annotations

from typing import Dict, Optional, Protocol

from .decode import Reading


class Sink(Protocol):
    async def start(self) -> None: ...

    def update(self, device_id: str, reading: Reading, rssi: int) -> None:
        """Sync; called from the bleak detection callback."""
        ...

    async def stop(self) -> None: ...


def parse_names(raw: Optional[str]) -> Dict[str, str]:
    """Parse "addr=name,addr=name" into {addr_lower: name}. Skips malformed items."""
    names: Dict[str, str] = {}
    if not raw:
        return names
    for item in raw.split(","):
        addr, sep, name = item.partition("=")
        addr = addr.strip().lower()
        name = name.strip()
        if sep and addr and name:
            names[addr] = name
    return names


def display_name(device_id: str, names: Dict[str, str]) -> str:
    """Configured name, else meter-<last 4 chars of id>."""
    found = names.get(device_id.lower())
    if found:
        return found
    short = device_id.lower().replace(":", "").replace("-", "")
    return "meter-" + short[-4:]
