import argparse
import asyncio
import datetime
import dataclasses
import json
import logging
import sys

from bleak.backends.device import BLEDevice
from victron_ble.devices import (
    detect_device_type, BatteryMonitor, Device, SolarCharger)
from victron_ble.exceptions import (
    AdvertisementKeyMissingError, UnknownDeviceError)
from victron_ble.scanner import Scanner

logger = logging.getLogger("signalk-victron-ble")


@dataclasses.dataclass
class ConfiguredDevice:
    id: str
    mac: str
    advertisement_key: str


class SignalKScanner(Scanner):
    def __init__(self, devices):
        super().__init__()
        self._devices: dict[str:ConfiguredDevice] = devices

    def load_key(self, address):
        try:
            return self._devices[address].advertisement_key
        except KeyError:
            raise AdvertisementKeyMissingError(f"No key available for {address}")

    def callback(self, bl_device: BLEDevice, raw_data: bytes):
        logger.debug(
            f"Received data from {bl_device.address.lower()}: {raw_data.hex()}"
        )
        try:
            device = self.get_device(bl_device, raw_data)
        except AdvertisementKeyMissingError:
            return
        except UnknownDeviceError as e:
            logger.error(e)
            return
        data = device.parse(raw_data)
        id_ = self._devices[bl_device.address.lower()].id
        if isinstance(device, BatteryMonitor):
            self.log_battery(bl_device, data, id_)
        elif isinstance(device, SolarCharger):
            self.log_solar_charger(bl_device, data, id_)
        else:
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

    def log_solar_charger(self, bl_device: BLEDevice, data: SolarCharger, id_: str):
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
                            "path": f"electrical.solar.{id_}.voltage",
                            "value": data.get_battery_voltage(),
                        },
                        {
                            "path": f"electrical.solar.{id_}.current",
                            "value": data.get_battery_charging_current(),
                        },
                        {
                            "path": f"electrical.solar.{id_}.chargingMode",
                            "value": data.get_charge_state().name.lower(),
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
