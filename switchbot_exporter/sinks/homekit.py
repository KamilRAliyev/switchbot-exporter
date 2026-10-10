"""Expose Meters to Apple Home through a HAP-python bridge on the bleak event loop.

Each device seen gets one HAP accessory (TemperatureSensor, HumiditySensor,
BatteryService) under a single Bridge. The driver runs on the caller's asyncio
loop via AccessoryDriver(loop=...) and async_start()/async_stop(); the blocking
driver.start() is never used.

Pairing caveat: a paired controller caches the accessory list, and HAP-python
does not support adding accessories to a paired bridge cleanly. So start()
returns immediately (the scanner must keep running to find devices) and a
background task waits `warmup` seconds for devices to appear, then publishes
the bridge with every device seen so far. Devices that first appear later are
still added to the bridge and driver.config_changed() bumps the HAP config
version and re-advertises, so controllers refetch the accessory list. That
path is best effort: the Home app may need a moment, or a restart of the
bridge, before a late tile shows up. Accessory ids are derived from a hash of
the device id so they survive restarts.

Staleness: if no reading arrives for `stale_after` seconds, StatusFault is set
to GENERAL_FAULT on the temperature and humidity services (the tile shows "No
Response"-style fault state); the next reading clears it.

Pairing: the driver prints the setup code and QR payload itself on start when
the state file has no paired client. Pairing keys persist in the state file.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import zlib
from typing import Callable, Dict, Optional

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver

from ..decode import Reading
from ..sink import display_name

LOW_BATTERY_PERCENT = 20
BRIDGE_NAME = "SwitchBot"
_NOT_CHARGEABLE = 2  # ChargingState value; Meters use coin cells
_RESERVED_AIDS = (0, 1, 7)  # 1 is the bridge, 7 is flaky in iOS (see pyhap)


def stable_aid(device_id: str, taken=()) -> int:
    """Accessory id from a hash of device_id; probes upward on collision."""
    aid = 2 + zlib.crc32(device_id.lower().encode("utf-8")) % (2 ** 31)
    while aid in _RESERVED_AIDS or aid in taken:
        aid += 1
    return aid


class MeterAccessory(Accessory):
    """One Meter: temperature, humidity and battery services."""

    def __init__(self, driver, name: str, aid: int, device_id: str, model: str) -> None:
        super().__init__(driver, name, aid=aid)
        self.set_info_service(manufacturer="SwitchBot", model=model,
                              serial_number=device_id)
        temp = self.add_preload_service("TemperatureSensor", chars=["StatusFault"])
        hum = self.add_preload_service("HumiditySensor", chars=["StatusFault"])
        batt = self.add_preload_service("BatteryService")
        self.temperature = temp.get_characteristic("CurrentTemperature")
        self.humidity = hum.get_characteristic("CurrentRelativeHumidity")
        self.battery_level = batt.get_characteristic("BatteryLevel")
        self.low_battery = batt.get_characteristic("StatusLowBattery")
        self.faults = [temp.get_characteristic("StatusFault"),
                       hum.get_characteristic("StatusFault")]
        batt.get_characteristic("ChargingState").set_value(_NOT_CHARGEABLE, should_notify=False)

    def apply(self, reading: Reading) -> None:
        self.temperature.set_value(reading.temperature_c)
        self.humidity.set_value(reading.humidity)
        self.battery_level.set_value(reading.battery)
        self.low_battery.set_value(1 if reading.battery < LOW_BATTERY_PERCENT else 0)

    def set_fault(self, fault: bool) -> None:
        for char in self.faults:
            char.set_value(1 if fault else 0)


class HomeKitSink:
    def __init__(self, state_file: str, names: Optional[Dict[str, str]] = None,
                 port: int = 51826, warmup: float = 60.0, stale_after: float = 600.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._state_file = os.path.abspath(os.path.expanduser(state_file))
        self._names = names or {}
        self._port = port
        self._warmup = warmup
        self._stale_after = stale_after
        self._clock = clock
        self._driver: Optional[AccessoryDriver] = None
        self._bridge: Optional[Bridge] = None
        self._published = False
        self._driver_started = False
        self._last: Dict[str, Reading] = {}
        self._last_seen: Dict[str, float] = {}
        self._accessories: Dict[str, MeterAccessory] = {}
        self._tasks = []

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        driver = AccessoryDriver(loop=loop, persist_file=self._state_file, port=self._port)
        self._attach(driver)
        self._tasks.append(loop.create_task(self._publish_after_warmup()))
        self._tasks.append(loop.create_task(self._stale_loop()))

    def _attach(self, driver) -> None:
        """Create the bridge on a driver (split from start() so tests can mock it)."""
        self._driver = driver
        self._bridge = Bridge(driver, BRIDGE_NAME)
        driver.add_accessory(self._bridge)  # loads the state file if present

    def update(self, device_id: str, reading: Reading, rssi: int) -> None:
        self._last[device_id] = reading
        self._last_seen[device_id] = self._clock()
        acc = self._accessories.get(device_id)
        if acc is None and self._bridge is not None and self._published:
            acc = self._create(device_id, reading)
            self._driver.config_changed()  # late device: bump config version
        if acc is not None:
            acc.apply(reading)
            acc.set_fault(False)

    def _create(self, device_id: str, reading: Reading) -> MeterAccessory:
        taken = set(self._bridge.accessories)
        acc = MeterAccessory(self._driver, display_name(device_id, self._names),
                             stable_aid(device_id, taken), device_id, reading.model)
        self._bridge.add_accessory(acc)
        self._accessories[device_id] = acc
        return acc

    def check_stale(self) -> None:
        now = self._clock()
        for device_id, acc in self._accessories.items():
            acc.set_fault(now - self._last_seen[device_id] >= self._stale_after)

    async def _stale_loop(self) -> None:
        interval = max(1.0, min(30.0, self._stale_after / 2))
        while True:
            await asyncio.sleep(interval)
            self.check_stale()

    async def _publish_after_warmup(self) -> None:
        try:
            await asyncio.sleep(self._warmup)
            await self._publish()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print("homekit publish failed: %r" % (exc,), file=sys.stderr, flush=True)

    async def _publish(self) -> None:
        """Build accessories for devices seen so far, then start the HAP driver."""
        for device_id, reading in list(self._last.items()):
            acc = self._create(device_id, reading)
            acc.apply(reading)
        self._published = True
        await self._driver.async_start()  # prints PIN/QR when unpaired
        self._driver_started = True

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._driver_started:
            self._driver_started = False
            await self._driver.async_stop()
        self._published = False
