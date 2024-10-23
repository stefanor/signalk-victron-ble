import argparse
import asyncio
import datetime
import dataclasses
import json
import logging
import sys
from typing import Any, Callable, Optional, TypeAlias

from bleak.backends.device import BLEDevice
from victron_ble.devices import (
    AuxMode,
    BatteryMonitorData,
    BatterySenseData,
    DcDcConverterData,
    DeviceData,
    OrionXSData,
    SolarChargerData,
)
from victron_ble.exceptions import AdvertisementKeyMissingError, UnknownDeviceError
from victron_ble.scanner import Scanner

logger = logging.getLogger("signalk-victron-ble")

SignalKDelta: TypeAlias = dict[str, list[dict[str, Any]]]


@dataclasses.dataclass
class ConfiguredDevice:
    id: str
    mac: str
    advertisement_key: str
    secondary_battery: Optional[str]


class SignalKScanner(Scanner):
    _devices: dict[str, ConfiguredDevice]

    def __init__(self, devices: dict[str, ConfiguredDevice]) -> None:
        super().__init__()
        self._devices = devices

    def load_key(self, address: str) -> str:
        try:
            return self._devices[address].advertisement_key
        except KeyError:
            raise AdvertisementKeyMissingError(f"No key available for {address}")

    def callback(self, bl_device: BLEDevice, raw_data: bytes) -> None:
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
        transformers: dict[
            type[DeviceData],
            Callable[[BLEDevice, ConfiguredDevice, Any, str], SignalKDelta],
        ] = {
            BatteryMonitorData: self.transform_battery_data,
            BatterySenseData: self.transform_battery_sense_data,
            SolarChargerData: self.transform_solar_charger_data,
            DcDcConverterData: self.transform_dcdc_converter_data,
            OrionXSData: self.transform_orion_xs_data,
        }
        for data_type, transformer in transformers.items():
            if isinstance(data, data_type):
                delta = transformer(bl_device, configured_device, data, id_)
                logger.info(delta)
                print(json.dumps(delta))
                sys.stdout.flush()
                return
        else:
            logger.debug("Unknown device", device)

    def transform_battery_sense_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: BatterySenseData,
        id_: str,
    ) -> SignalKDelta:
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
                            "path": f"electrical.batteries.{id_}.voltage",
                            "value": data.get_voltage(),
                        },
                        {
                            "path": f"electrical.batteries.{id_}.temperature",
                            "value": data.get_temperature() + 273.15,
                        },
                    ],
                },
            ],
        }

    def transform_battery_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: BatteryMonitorData,
        id_: str,
    ) -> SignalKDelta:
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
            if cfg_device.secondary_battery:
                values.append(
                    {
                        "path": f"electrical.batteries.{cfg_device.secondary_battery}.voltage",
                        "value": data.get_starter_voltage(),
                    }
                )
        elif data.get_aux_mode() == AuxMode.TEMPERATURE:
            if temperature := data.get_temperature():
                values.append(
                    {
                        "path": f"electrical.batteries.{id_}.temperature",
                        "value": temperature + 273.15,
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

    def transform_dcdc_converter_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: DcDcConverterData,
        id_: str,
    ) -> SignalKDelta:
        values = [
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
        ]
        if off_reason := data.get_off_reason().name:
            values.append(
                {
                    "path": f"electrical.converters.{id_}.chargerOffReason",
                    "value": off_reason.lower(),
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

    def transform_orion_xs_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: OrionXSData,
        id_: str,
    ) -> SignalKDelta:
        values = [
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
                "path": f"electrical.converters.{id_}.input.current",
                "value": data.get_input_current(),
            },
            {
                "path": f"electrical.converters.{id_}.output.voltage",
                "value": data.get_output_voltage(),
            },
            {
                "path": f"electrical.converters.{id_}.output.current",
                "value": data.get_output_current(),
            },
        ]
        if off_reason := data.get_off_reason().name:
            values.append(
                {
                    "path": f"electrical.converters.{id_}.chargerOffReason",
                    "value": off_reason.lower(),
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
        data: SolarChargerData,
        id_: str,
    ) -> SignalKDelta:
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


async def monitor(devices: dict[str, ConfiguredDevice]) -> None:
    scanner = SignalKScanner(devices)
    await scanner.start()
    await asyncio.Event().wait()


def main() -> None:
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
    devices: dict[str, ConfiguredDevice] = {}
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
