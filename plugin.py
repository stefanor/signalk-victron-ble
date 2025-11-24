import argparse
import asyncio
import datetime
import dataclasses
import enum
import json
import logging
import sys
from typing import Any, Callable, Union

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from victron_ble.devices import (
    AcChargerData,
    AuxMode,
    BatteryMonitorData,
    BatterySenseData,
    DcDcConverterData,
    DcEnergyMeterData,
    DeviceData,
    InverterData,
    LynxSmartBMSData,
    OrionXSData,
    SmartLithiumData,
    SolarChargerData,
    VEBusData,
)
from victron_ble.devices.dc_energy_meter import MeterType
from victron_ble.exceptions import AdvertisementKeyMissingError, UnknownDeviceError
from victron_ble.scanner import Scanner

logger = logging.getLogger("signalk-victron-ble")

# 3.9 compatible TypeAliases
SignalKDelta = dict[str, list[dict[str, Any]]]
SignalKDeltaValues = list[dict[str, Union[int, float, str, None]]]


@dataclasses.dataclass
class ConfiguredDevice:
    id: str
    mac: str
    advertisement_key: str
    secondary_battery: Union[str, None]


def transformer(
    prefix: str,
    data: dict[str, Union[str, float, None]],
) -> SignalKDeltaValues:
    return [
        {
            "path": f"{prefix}.{key}",
            "value": value,
        }
        for key, value in data.items()
        if value is not None
    ]


def tempK(tempC: Union[float, None]) -> Union[float, None]:
    if tempC is None:
        return None
    return tempC + 273.15


def power(
    voltage: Union[float, None], current: Union[float, None]
) -> Union[float, None]:
    if voltage is None or current is None:
        return None
    return voltage * current


def percentage(percent: Union[float, None]) -> Union[float, None]:
    if percent is None:
        return None
    return percent / 100


def coulomb(ah: Union[float, None]) -> Union[float, None]:
    if ah is None:
        return None
    return ah * 3600


def joule(wh: Union[float, None]) -> Union[float, None]:
    if wh is None:
        return None
    return wh * 3600


def seconds(minutes: Union[float, None]) -> Union[float, None]:
    if minutes is None:
        return None
    return minutes * 60


def lower_name(value: Union[enum.Enum, None]) -> Union[str, None]:
    if value is None:
        return None
    return value.name.lower()


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

    def callback(
        self, bl_device: BLEDevice, raw_data: bytes, advertisement: AdvertisementData
    ) -> None:
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
            Callable[[BLEDevice, ConfiguredDevice, Any, str], SignalKDeltaValues],
        ] = {
            AcChargerData: self.transform_ac_charger_data,
            BatteryMonitorData: self.transform_battery_data,
            BatterySenseData: self.transform_battery_sense_data,
            DcDcConverterData: self.transform_dcdc_converter_data,
            DcEnergyMeterData: self.transform_dc_energy_meter_data,
            InverterData: self.transform_inverter_data,
            LynxSmartBMSData: self.transform_lynx_smart_bms_data,
            OrionXSData: self.transform_orion_xs_data,
            SmartLithiumData: self.transform_smart_lithium_data,
            SolarChargerData: self.transform_solar_charger_data,
            VEBusData: self.transform_ve_bus_data,
        }
        for data_type, transformer in transformers.items():
            if isinstance(data, data_type):
                values = transformer(bl_device, configured_device, data, id_)
                delta = self.prepare_signalk_delta(bl_device, values)
                logger.info(delta)
                print(json.dumps(delta))
                sys.stdout.flush()
                return
        else:
            logger.debug("Unknown device", device)

    def prepare_signalk_delta(
        self, bl_device: BLEDevice, values: SignalKDeltaValues
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
                    "values": values,
                }
            ]
        }

    def transform_ac_charger_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: AcChargerData,
        id_: str,
    ) -> SignalKDeltaValues:
        values = transformer(
            f"electrical.chargers.{id_}_1",
            {
                "chargingMode": lower_name(data.get_charge_state()),
                "current": data.get_output_current1(),
                "temperature": tempK(data.get_temperature()),
                "voltage": data.get_output_voltage1(),
            },
        )
        if data.get_output_voltage2() is not None:
            values += transformer(
                f"electrical.chargers.{id_}_2",
                {
                    "chargingMode": lower_name(data.get_charge_state()),
                    "current": data.get_output_current2(),
                    "temperature": tempK(data.get_temperature()),
                    "voltage": data.get_output_voltage2(),
                },
            )
        if data.get_output_voltage3() is not None:
            values += transformer(
                f"electrical.chargers.{id_}_3",
                {
                    "chargingMode": lower_name(data.get_charge_state()),
                    "current": data.get_output_current3(),
                    "temperature": tempK(data.get_temperature()),
                    "voltage": data.get_output_voltage3(),
                },
            )
        return values

    def transform_battery_sense_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: BatterySenseData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.batteries.{id_}",
            {
                "temperature": tempK(data.get_temperature()),
                "voltage": data.get_voltage(),
            },
        )

    def transform_battery_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: BatteryMonitorData,
        id_: str,
    ) -> SignalKDeltaValues:
        values = transformer(
            f"electrical.batteries.{id_}",
            {
                "capacity.dischargeSinceFull": coulomb(ah=data.get_consumed_ah()),
                "capacity.stateOfCharge": percentage(percent=data.get_soc()),
                "capacity.timeRemaining": seconds(minutes=data.get_remaining_mins()),
                "current": data.get_current(),
                "power": power(voltage=data.get_voltage(), current=data.get_current()),
                "voltage": data.get_voltage(),
            },
        )

        if data.get_aux_mode() == AuxMode.STARTER_VOLTAGE:
            if cfg_device.secondary_battery:
                values.append(
                    {
                        "path": f"electrical.batteries.{cfg_device.secondary_battery}.voltage",
                        "value": data.get_starter_voltage(),
                    }
                )
        elif data.get_aux_mode() == AuxMode.TEMPERATURE:
            values += transformer(
                f"electrical.batteries.{id_}",
                {"temperature": tempK(data.get_temperature())},
            )

        return values

    def transform_dcdc_converter_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: DcDcConverterData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.converters.{id_}",
            {
                "chargerError": lower_name(data.get_charger_error()),
                "chargerOffReason": lower_name(data.get_off_reason()),
                "chargingMode": lower_name(data.get_charge_state()),
                "input.voltage": data.get_input_voltage(),
                "output.voltage": data.get_output_voltage(),
            },
        )

    # Typically, a SmartShunt in DC Energy Meter mode
    def transform_dc_energy_meter_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: DcEnergyMeterData,
        id_: str,
    ) -> SignalKDeltaValues:
        # The SmartShunt in DC Energy Meter mode can be configured with various
        # measurement types, so we use that to determine the best possible path on SignalK
        prefix = f"electrical.batteries.{id_}"
        meter_type = data.get_meter_type()
        if meter_type in {
            MeterType.GENERIC_LOAD,
            MeterType.ELECTRIC_DRIVE,
            MeterType.FRIDGE,
            MeterType.WATER_PUMP,
            MeterType.BILGE_PUMP,
            MeterType.DC_SYSTEM,
            MeterType.WATER_HEATER,
        }:
            # 'dcload' is used by the Victron Venus plugin, it's not standard
            # in the SignalK spec, but at least we're consistent across plugins
            prefix = f"electrical.dcload.{id_}"
        elif meter_type == MeterType.SOLAR_CHARGER:
            prefix = f"electrical.solar.{id_}"
        elif meter_type in {
            MeterType.WIND_CHARGER,
            MeterType.SHAFT_GENERATOR,
            MeterType.FUEL_CELL,
            MeterType.WATER_GENERATOR,
            MeterType.DC_DC_CHARGER,
            MeterType.AC_CHARGER,
            MeterType.GENERIC_SOURCE,
        }:
            prefix = f"electrical.chargers.{id_}"
        elif meter_type == MeterType.ALTERNATOR:
            prefix = f"electrical.alternators.{id_}"
        elif meter_type == MeterType.INVERTER:
            prefix = f"electrical.inverters.{id_}.dc"

        values = transformer(
            prefix,
            {
                "current": data.get_current(),
                "power": power(voltage=data.get_voltage(), current=data.get_current()),
                "voltage": data.get_voltage(),
            },
        )

        if data.get_aux_mode() == AuxMode.STARTER_VOLTAGE:
            if cfg_device.secondary_battery:
                values.append(
                    {
                        "path": f"electrical.batteries.{cfg_device.secondary_battery}.voltage",
                        "value": data.get_starter_voltage(),
                    }
                )
        elif data.get_aux_mode() == AuxMode.TEMPERATURE:
            values += transformer(
                f"electrical.batteries.{id_}",
                {"temperature": tempK(data.get_temperature())},
            )

        return values

    def transform_inverter_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: InverterData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.inverters.{id_}",
            {
                "ac.apparentPower": data.get_ac_apparent_power(),
                "ac.current": data.get_ac_current(),
                "ac.lineNeutralVoltage": data.get_ac_voltage(),
                "dc.voltage": data.get_battery_voltage(),
                "inverterMode": lower_name(data.get_device_state()),
            },
        )

    def transform_lynx_smart_bms_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: LynxSmartBMSData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.batteries.{id_}",
            {
                "capacity.dischargeSinceFull": coulomb(ah=data.get_consumed_ah()),
                "capacity.stateOfCharge": percentage(percent=data.get_soc()),
                "capacity.timeRemaining": seconds(minutes=data.get_remaining_mins()),
                "current": data.get_current(),
                "power": power(voltage=data.get_voltage(), current=data.get_current()),
                "temperature": tempK(data.get_battery_temperature()),
                "voltage": data.get_voltage(),
            },
        )

    def transform_orion_xs_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: OrionXSData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.converters.{id_}",
            {
                "chargingMode": lower_name(data.get_charge_state()),
                "chargerError": lower_name(data.get_charger_error()),
                "chargerOffReason": lower_name(data.get_off_reason()),
                "input.voltage": data.get_input_voltage(),
                "input.current": data.get_input_current(),
                "output.voltage": data.get_output_voltage(),
                "output.current": data.get_output_current(),
            },
        )

    def transform_smart_lithium_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: SmartLithiumData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.batteries.{id_}",
            {
                "voltage": data.get_battery_voltage(),
                "temperature": tempK(data.get_battery_temperature()),
            },
        )

    def transform_solar_charger_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: SolarChargerData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.solar.{id_}",
            {
                "chargingMode": lower_name(data.get_charge_state()),
                "current": data.get_battery_charging_current(),
                "loadCurrent": data.get_external_device_load(),
                "panelPower": data.get_solar_power(),
                "voltage": data.get_battery_voltage(),
                "yieldToday": joule(wh=data.get_yield_today()),
            },
        )

    def transform_ve_bus_data(
        self,
        bl_device: BLEDevice,
        cfg_device: ConfiguredDevice,
        data: VEBusData,
        id_: str,
    ) -> SignalKDeltaValues:
        return transformer(
            f"electrical.inverters.{id_}",
            {
                "ac.apparentPower": data.get_ac_out_power(),
                "dc.current": data.get_battery_current(),
                "dc.temperature": tempK(data.get_battery_temperature()),
                "dc.voltage": data.get_battery_voltage(),
                "inverterMode": lower_name(data.get_device_state()),
            },
        )


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
