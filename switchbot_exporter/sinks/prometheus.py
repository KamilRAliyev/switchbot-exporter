"""Expose readings as Prometheus gauges on an HTTP /metrics endpoint."""
from __future__ import annotations

import time
from typing import Dict, Optional

from prometheus_client import CollectorRegistry, Gauge, start_http_server

from ..decode import Reading
from ..sink import display_name

_LABELS = ("device", "name", "model")


class PrometheusSink:
    def __init__(self, port: int, names: Optional[Dict[str, str]] = None) -> None:
        self._port = port
        self._names = names or {}
        self._server = None
        self._thread = None
        self.registry = CollectorRegistry()
        self._temperature = Gauge("switchbot_temperature_celsius",
                                  "Temperature in degrees Celsius", _LABELS,
                                  registry=self.registry)
        self._humidity = Gauge("switchbot_humidity_percent",
                               "Relative humidity in percent", _LABELS,
                               registry=self.registry)
        self._battery = Gauge("switchbot_battery_percent",
                              "Battery level in percent", _LABELS,
                              registry=self.registry)
        self._rssi = Gauge("switchbot_rssi_dbm",
                           "Received signal strength in dBm", _LABELS,
                           registry=self.registry)
        self._last_seen = Gauge("switchbot_last_seen_timestamp_seconds",
                                "Unix time of the last advertisement received", _LABELS,
                                registry=self.registry)

    async def start(self) -> None:
        self._server, self._thread = start_http_server(self._port, registry=self.registry)

    def update(self, device_id: str, reading: Reading, rssi: int) -> None:
        labels = (device_id, display_name(device_id, self._names), reading.model)
        self._temperature.labels(*labels).set(reading.temperature_c)
        self._humidity.labels(*labels).set(reading.humidity)
        self._battery.labels(*labels).set(reading.battery)
        self._rssi.labels(*labels).set(rssi)
        self._last_seen.labels(*labels).set(time.time())

    async def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
