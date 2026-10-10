"""Print readings, deduplicating unchanged values within an interval."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Dict, Optional, TextIO, Tuple

from ..decode import Reading
from ..sink import display_name


class StdoutSink:
    def __init__(self, interval: float = 60.0, names: Optional[Dict[str, str]] = None,
                 out: Optional[TextIO] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._interval = interval
        self._names = names or {}
        self._out = out
        self._clock = clock
        self._last: Dict[str, Tuple[Reading, float]] = {}

    async def start(self) -> None:
        pass

    def update(self, device_id: str, reading: Reading, rssi: int) -> None:
        now = self._clock()
        prev = self._last.get(device_id)
        if prev and prev[0] == reading and now - prev[1] < self._interval:
            return
        self._last[device_id] = (reading, now)
        print("%s  %s  %s  %s  %.1fC  %d%%  batt %d%%  rssi %s" % (
            datetime.now().isoformat(timespec="seconds"),
            display_name(device_id, self._names), device_id, reading.model,
            reading.temperature_c, reading.humidity, reading.battery, rssi),
            file=self._out, flush=True)

    async def stop(self) -> None:
        pass
