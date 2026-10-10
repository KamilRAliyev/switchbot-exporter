"""BLE source: scans advertisements and fans readings out to sinks."""
from __future__ import annotations

import sys
from typing import Iterable, List, Optional

from bleak import BleakScanner

from .decode import SERVICE_UUID, decode_meter
from .sink import Sink


class MeterScanner:
    def __init__(self, sinks: List[Sink], addresses: Optional[Iterable[str]] = None,
                 adapter: Optional[str] = None) -> None:
        self._sinks = list(sinks)
        self._wanted = {a.lower() for a in addresses or []}
        self._adapter = adapter
        self._scanner: Optional[BleakScanner] = None

    def _on_detect(self, device, adv) -> None:
        data = adv.service_data.get(SERVICE_UUID)
        if data is None:
            return
        device_id = device.address.lower()
        if self._wanted and device_id not in self._wanted:
            return
        reading = decode_meter(bytes(data))
        if reading is None:
            return
        for sink in self._sinks:
            try:
                sink.update(device_id, reading, adv.rssi)
            except Exception as exc:  # one bad sink must not break the others
                print("sink %s failed: %r" % (type(sink).__name__, exc),
                      file=sys.stderr, flush=True)

    async def start(self) -> None:
        kwargs = {}
        if self._adapter and sys.platform.startswith("linux"):
            kwargs["adapter"] = self._adapter
        self._scanner = BleakScanner(self._on_detect, **kwargs)
        await self._scanner.start()

    async def stop(self) -> None:
        if self._scanner is not None:
            await self._scanner.stop()
            self._scanner = None
