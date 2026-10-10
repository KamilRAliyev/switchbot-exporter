"""Pure decoder for SwitchBot Meter / Meter Plus service data. No BLE imports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SERVICE_UUID = "0000fd3d-0000-1000-8000-00805f9b34fb"

MODELS = {0x54: "Meter", 0x69: "MeterPlus"}  # 'T', 'i'


@dataclass(frozen=True)
class Reading:
    model: str
    temperature_c: float
    humidity: int
    battery: int


def decode_meter(service_data: bytes) -> Optional[Reading]:
    """Decode service data under SERVICE_UUID. Returns None if not a Meter."""
    if service_data is None or len(service_data) < 6:
        return None
    model = MODELS.get(service_data[0] & 0x7F)
    if model is None:
        return None
    battery = service_data[2] & 0x7F
    temp = (service_data[4] & 0x7F) + (service_data[3] & 0x0F) / 10
    if not service_data[4] & 0x80:
        temp = -temp
    humidity = service_data[5] & 0x7F
    return Reading(model, round(temp, 1), humidity, battery)
