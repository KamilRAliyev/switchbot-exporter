# switchbot-exporter

Passively scans BLE advertisements from SwitchBot Meter / Meter Plus sensors and fans readings out to sinks: stdout, Prometheus `/metrics`, and a HomeKit bridge. No pairing with the sensors needed.

    MeterScanner (bleak) -> [StdoutSink, PrometheusSink, HomeKitSink]

## Setup

macOS Python 3.9 ships with pip 21, which tries to build pyobjc-core from source and fails. Upgrade pip first so prebuilt wheels are used.

    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt

## Run

    .venv/bin/python -m switchbot_exporter [--stdout] [--metrics-port N] [--homekit --homekit-state PATH] [--address ADDR ...] [--adapter hci0] [--interval 60]

Sinks combine freely. With no sink flag, stdout is used. Examples:

    # just print
    .venv/bin/python -m switchbot_exporter
    # print, Prometheus on :9101, HomeKit bridge
    .venv/bin/python -m switchbot_exporter --stdout --metrics-port 9101 --homekit --homekit-state ./homekit.state

Stdout line: `time  name  id  model  temp  humidity  battery  rssi`. A line prints when values change, or every `--interval` seconds per device. Temperature is always in C.

SIGINT and SIGTERM stop the scanner, then every sink.

## Configuration

Every flag has an env var (the flag wins).

| Flag | Env var | Notes |
| --- | --- | --- |
| `--stdout` | `SWITCHBOT_STDOUT` | `1/true/yes/on` |
| `--metrics-port` | `SWITCHBOT_METRICS_PORT` | Prometheus off unless set |
| `--homekit` | `SWITCHBOT_HOMEKIT` | `1/true/yes/on` |
| `--homekit-state` | `SWITCHBOT_HOMEKIT_STATE` | default `homekit.state` |
| `--address` (repeatable) | `SWITCHBOT_ADDRESSES` | comma separated; empty means all meters |
| `--adapter` | `SWITCHBOT_ADAPTER` | Linux only, ignored on macOS |
| `--interval` | `SWITCHBOT_INTERVAL` | default 60 |
| (none) | `SWITCHBOT_NAMES` | `1065=Office,4a22=Bedroom` |

Without `SWITCHBOT_NAMES`, a device is named `meter-<last 4 chars of id>`. Keep full addresses out of git; pass them via env or an untracked file.

Friendly names:

    SWITCHBOT_NAMES="1065=Office,4a22=Bedroom"

A key is a full device id or a suffix of one (4 or more chars). Case, `:` and `-` are ignored. Lookup order: exact id match, then the longest matching suffix, then `meter-<last 4 chars of id>`. A 4-char suffix is not a full address, so it is fine to commit.

On Linux the id is the real MAC, so the suffix is stable. On macOS ids are per-Mac CoreBluetooth UUIDs, so the suffixes differ there and a Linux-oriented mapping will not match.

## Metrics

Gauges, each labelled `device`, `name`, `model`:

- `switchbot_temperature_celsius`
- `switchbot_humidity_percent`
- `switchbot_battery_percent`
- `switchbot_rssi_dbm`
- `switchbot_last_seen_timestamp_seconds`

## HomeKit

1. Start with `--homekit --homekit-state ./homekit.state`.
2. On first start the pairing PIN (and QR code) is printed. The bridge waits for a warmup period to discover devices before publishing.
3. In the Home app on an iPhone on the same Wi-Fi: Add Accessory, scan the QR code or enter the PIN.
4. Pairing keys persist in the state file (gitignored). Keep it to stay paired; delete it to re-pair. The state is per instance, so remove the old pairing in the Home app before pairing a different machine.

The pairing code is stored in `<state file>.pin` (for example `homekit.state.pin`), next to the state file, and stays the same across restarts. Once a phone is paired the code is not needed again.

Each meter shows as temperature, humidity and battery. Without an Apple TV or HomePod acting as a home hub, the Home app shows tiles only while the phone is on the home LAN. Remote viewing needs a hub (or use Grafana via Prometheus).

## Notes

- macOS: allow your terminal app in System Settings > Privacy & Security > Bluetooth, or the scan fails or returns nothing.
- On macOS the device id is a CoreBluetooth UUID, stable only on that Mac. On Linux it is the MAC. Run once without `--address` to find yours; do not commit them.

## Tests

    .venv/bin/python -m unittest discover tests
