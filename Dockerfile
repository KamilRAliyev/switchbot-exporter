# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# No bluez package and no compiler: the app talks to the host's BlueZ over the
# D-Bus socket mounted at /run/dbus. Compiled deps (dbus-fast from bleak,
# cryptography, orjson, zeroconf from HAP-python) must come from prebuilt
# wheels, so fail the build loudly instead of silently needing gcc.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --only-binary=dbus-fast,cryptography,orjson,zeroconf \
        -r requirements.txt

COPY switchbot_exporter/ ./switchbot_exporter/

# Metrics (Prometheus) and HomeKit (HAP).
EXPOSE 9101 51826

# Runs as root on purpose: the BlueZ D-Bus policy only allows root (or members
# of the bluetooth group) to talk to org.bluez.
ENTRYPOINT ["python", "-m", "switchbot_exporter"]
