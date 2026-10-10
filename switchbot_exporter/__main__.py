"""CLI: python -m switchbot_exporter"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from typing import List, Optional

from .sink import Sink, parse_names
from .source import MeterScanner
from .sinks.stdout import StdoutSink

TRUE = ("1", "true", "yes", "on")


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE


def build_parser() -> argparse.ArgumentParser:
    env = os.environ.get
    metrics_env = env("SWITCHBOT_METRICS_PORT")
    p = argparse.ArgumentParser(
        prog="switchbot_exporter",
        description="Scan SwitchBot Meters and fan readings out to sinks. "
                    "Each flag falls back to a SWITCHBOT_* env var. "
                    "Display names come from SWITCHBOT_NAMES=\"addr=name,addr=name\".")
    p.add_argument("--stdout", action="store_true", default=_env_bool("SWITCHBOT_STDOUT"),
                   help="print readings (env SWITCHBOT_STDOUT; default if no other sink)")
    p.add_argument("--metrics-port", type=int, default=int(metrics_env) if metrics_env else None,
                   help="serve Prometheus /metrics on this port (env SWITCHBOT_METRICS_PORT)")
    p.add_argument("--homekit", action="store_true", default=_env_bool("SWITCHBOT_HOMEKIT"),
                   help="expose a HomeKit bridge (env SWITCHBOT_HOMEKIT)")
    p.add_argument("--homekit-state", default=env("SWITCHBOT_HOMEKIT_STATE", "homekit.state"),
                   help="HomeKit pairing state file (env SWITCHBOT_HOMEKIT_STATE, default homekit.state)")
    p.add_argument("--address", action="append", default=None,
                   help="only this device address (repeatable; env SWITCHBOT_ADDRESSES, comma separated)")
    p.add_argument("--adapter", default=env("SWITCHBOT_ADAPTER") or None,
                   help="Bluetooth adapter, Linux only, e.g. hci0 (env SWITCHBOT_ADAPTER)")
    p.add_argument("--interval", type=float, default=float(env("SWITCHBOT_INTERVAL") or 60),
                   help="stdout: reprint unchanged readings after N seconds (env SWITCHBOT_INTERVAL, default 60)")
    return p


def build_sinks(args: argparse.Namespace, names) -> List[Sink]:
    sinks: List[Sink] = []
    use_stdout = args.stdout or (args.metrics_port is None and not args.homekit)
    if use_stdout:
        sinks.append(StdoutSink(args.interval, names))
    if args.metrics_port is not None:
        from .sinks.prometheus import PrometheusSink
        sinks.append(PrometheusSink(args.metrics_port, names))
    if args.homekit:
        from .sinks.homekit import HomeKitSink
        sinks.append(HomeKitSink(args.homekit_state, names))
    return sinks


async def run(args: argparse.Namespace) -> None:
    names = parse_names(os.environ.get("SWITCHBOT_NAMES"))
    addresses = args.address
    if addresses is None:
        addresses = [a for a in os.environ.get("SWITCHBOT_ADDRESSES", "").split(",") if a.strip()]
    sinks = build_sinks(args, names)
    scanner = MeterScanner(sinks, addresses, args.adapter)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    started: List[Sink] = []
    scanner_started = False
    try:
        for sink in sinks:
            await sink.start()
            started.append(sink)
        await scanner.start()
        scanner_started = True
        await stop_event.wait()
    finally:
        if scanner_started:
            await scanner.stop()
        for sink in reversed(started):
            try:
                await sink.stop()
            except Exception as exc:
                print("sink %s stop failed: %r" % (type(sink).__name__, exc),
                      file=sys.stderr, flush=True)


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
