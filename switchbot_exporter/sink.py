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


def _norm(value: str) -> str:
    """Lowercase and strip ':' and '-' so ids and keys compare equal."""
    return value.strip().lower().replace(":", "").replace("-", "")


def parse_names(raw: Optional[str]) -> Dict[str, str]:
    """Parse "key=name,key=name" into {normalized_key: name}. Skips malformed items.

    A key is a full device id or a suffix of one (4+ chars), normalized with _norm.
    """
    names: Dict[str, str] = {}
    if not raw:
        return names
    for item in raw.split(","):
        addr, sep, name = item.partition("=")
        addr = _norm(addr)
        name = name.strip()
        if sep and addr and name:
            names[addr] = name
    return names


def display_name(device_id: str, names: Dict[str, str]) -> str:
    """Configured name, else meter-<last 4 chars of id>.

    Order: exact id match, then the longest key (4+ chars) that is a suffix of
    the normalized id, then the default.
    """
    nid = _norm(device_id)
    norm = {_norm(k): v for k, v in names.items()}
    found = norm.get(nid)
    if found:
        return found
    suffixes = [k for k in norm if len(k) >= 4 and nid.endswith(k)]
    if suffixes:
        return norm[max(suffixes, key=len)]
    return "meter-" + nid[-4:]
