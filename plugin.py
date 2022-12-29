import argparse
import asyncio
import datetime
import dataclasses
import json
import logging
import sys

from bleak.backends.device import BLEDevice
from victron_ble.devices import Device, detect_device_type, BatteryMonitor
from victron_ble.scanner import BaseScanner

logger = logging.getLogger("signalk-victron-ble")


@dataclasses.dataclass
class ConfiguredDevice:
    id: str
    mac: str
    advertisement_key: str


class SignalKScanner(BaseScanner):
    def __init__(self, devices):
        super().__init__()
        self._known_devices: dict[str, Device] = {}
        self._devices: dict[str:ConfiguredDevice] = devices

    async def start(self):
        logger.info("Starting")
        await super().start()
        logger.info("Started")

    def get_device(self, device, data):
        address = device.address.lower()
        if address not in self._known_devices:
            advertisement_key = self.load_key(address)

            device_klass = detect_device_type(data)
            if not device_klass:
                raise KeyError(f"Could not identify device type for {device}")

            self._known_devices[address] = device_klass(advertisement_key)
        return self._known_devices[address]

    def load_key(self, address):
        return self._devices[address].advertisement_key

    def callback(self, bl_device: BLEDevice, raw_data: bytes):
        logger.debug(
            f"Received data from {bl_device.address.lower()}: {raw_data.hex()}"
        )
        try:
            device = self.get_device(bl_device, raw_data)
        except KeyError as e:
            logger.info("Error", e)
            return
        data = device.parse(raw_data)
        id_ = self._devices[bl_device.address.lower()].id
        if isinstance(device, BatteryMonitor):
            self.log_battery(bl_device, data, id_)
        logger.debug("Unknown device", device)

    def log_battery(self, bl_device: BLEDevice, data: BatteryMonitor, id_: str):
        delta = {
            "updates": [
                {
                    "source": {
                        "label": "Victron",
                        "type": "Bluetooth",
                        "src": bl_device.address,
                    },
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "values": [
                        {
                            "path": f"electrical.batteries.{id_}.voltage",
                            "value": data.get_voltage(),
                        },
                        {
                            "path": f"electrical.batteries.{id_}.current",
                            "value": data.get_current(),
                        },
                        {
                            "path": f"electrical.batteries.{id_}.capacity.stateOfCharge",
                            "value": data.get_soc(),
                        },
                        {
                            "path": f"electrical.batteries.{id_}.capacity.timeRemaining",
                            "value": data.get_remaining_mins() * 60,
                        },
                    ],
                },
            ],
        }
        logger.info(delta)
        print(json.dumps(delta))
        sys.stdout.flush()


async def monitor(devices):
    scanner = SignalKScanner(devices)
    await scanner.start()
    await asyncio.Event().wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Increase the verbosity"
    )
    args = p.parse_args()

    logging.basicConfig(
        stream=sys.stderr, level=logging.DEBUG if args.verbose else logging.WARNING
    )

    logging.debug("Waiting for config...")
    config = json.loads(input())
    logging.info("Configured: %s", json.dumps(config))
    devices = {}
    for device in config["devices"]:
        devices[device["mac"].lower()] = ConfiguredDevice(
            id=device["id"],
            mac=device["mac"],
            advertisement_key=device["key"],
        )

    asyncio.run(monitor(devices))


if __name__ == "__main__":
    main()
