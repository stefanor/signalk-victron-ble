import argparse
import asyncio
import datetime
import dataclasses
import json
import logging
import sys
from typing import Optional

from bleak.backends.device import BLEDevice
from victron_ble.devices import AuxMode, BatteryMonitor, SolarCharger, DcDcConverter
from victron_ble.exceptions import AdvertisementKeyMissingError, UnknownDeviceError
from victron_ble.scanner import Scanner

logger = logging.getLogger("signalk-victron-ble")


@dataclasses.dataclass
class ConfiguredDevice:
    id: str
    mac: str
    advertisement_key: str
    secondary_battery: Optional[str]


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
        configured_device = self._devices[bl_device.address.lower()]
        id_ = configured_device.id
        transformers = {
            BatteryMonitor: self.transform_battery_data,
            SolarCharger: self.transform_solar_charger_data,
            DcDcConverter: self.transform_dcdc_converter_data,
        }
        for device_type, transformer in transformers.items():
            if isinstance(device, device_type):
                delta = transformer(bl_device, configured_device, data, id_)
                logger.info(delta)
                print(json.dumps(delta))
                sys.stdout.flush()
                return
        else:
            logger.debug("Unknown device", device)

    def transform_battery_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: BatteryMonitor,
        id_: str,
    ):
        values = [
            {
                "path": f"electrical.batteries.{id_}.voltage",
                "value": data.get_voltage(),
            },
            {
                "path": f"electrical.batteries.{id_}.current",
                "value": data.get_current(),
            },
            {
                "path": f"electrical.batteries.{id_}.power",
                "value": data.get_voltage() * data.get_current(),
            },
            {
                "path": f"electrical.batteries.{id_}.capacity.stateOfCharge",
                "value": data.get_soc() / 100,
            },
            {
                "path": f"electrical.batteries.{id_}.capacity.dischargeSinceFull",
                "value": data.get_consumed_ah() * 3600,
            },
            {
                "path": f"electrical.batteries.{id_}.capacity.timeRemaining",
                "value": data.get_remaining_mins() * 60,
            },
        ]

        if data.get_aux_mode() == AuxMode.STARTER_VOLTAGE:
            if cfg_device.secondary_battery :
                values.append(
                    {
                        "path": f"electrical.batteries.{cfg_device.secondary_battery}.voltage",
                        "value": data.get_starter_voltage(),
                    }
                )
        elif data.get_aux_mode() == AuxMode.TEMPERATURE:
            values.append(
                {
                    "path": f"electrical.batteries.{id_}.temperature",
                    "value": data.get_temperature() + 273.15,
                }
            )

        return {
            "updates": [
                {
                    "source": {
                        "label": "Victron",
                        "type": "Bluetooth",
                        "src": bl_device.address,
                    },
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "values": values,
                },
            ],
        }

    def transform_solar_charger_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: SolarCharger,
        id_: str,
    ):
        return {
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
                        {
                            "path": f"electrical.solar.{id_}.panelPower",
                            "value": data.get_solar_power(),
                        },
                        {
                            "path": f"electrical.solar.{id_}.loadCurrent",
                            "value": data.get_external_device_load(),
                        },
                        {
                            "path": f"electrical.solar.{id_}.yieldToday",
                            "value": data.get_yield_today(),
                        },
                    ],
                },
            ],
        }

    def transform_dcdc_converter_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: DcDcConverter,
        id_: str,
    ):
        return {
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
                            "path": f"electrical.converters.{id_}.chargingMode",
                            "value": data.get_charge_state().name.lower(),
                        },
                        {
                            "path": f"electrical.converters.{id_}.chargerError",
                            "value": data.get_charger_error().name.lower(),
                        },
                        {
                            "path": f"electrical.converters.{id_}.input.voltage",
                            "value": data.get_input_voltage(),
                        },
                        {
                            "path": f"electrical.converters.{id_}.output.voltage",
                            "value": data.get_output_voltage(),
                        },
                        {
                            "path": f"electrical.converters.{id_}.chargerOffReason",
                            "value": data.get_off_reason().name.lower(),
                        },
                    ],
                },
            ],
        }


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
            secondary_battery=device.get("secondary_battery"),
        )

    asyncio.run(monitor(devices))


if __name__ == "__main__":
    main()
