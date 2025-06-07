# Changelog

## 0.1.7

* Restore `capacity.timeRemaining` for battery monitors, accidentally
  moved in 0.1.4 (#29)

## 0.1.6

* Support smart shunts in DC energy meter modes (#25)

## 0.1.5

* Restore support for Python 3.9 (#24)

## 0.1.4

* Update to victron_ble 0.9.2
* Support AC chargers

## 0.1.3

* Fix a critical syntax error in 0.1.2

## 0.1.2

* Restore the correct unit (J) for solar yield (#17)

## 0.1.1

* Restore support for Python 3.9 (#16)

## 0.1.0

* Update to victron_ble 0.9.0
* Add support for:
  * Inverters (untested)
  * Lynx Smart BMS
  * MultiPlus inverters (with VE.Bus Bluetooth dongle, untested)
  * Orion XS DC/DC chargers/converters
  * Smart Lithum batteries
* Change solar yield unit to correctly report Jules (old value * 3600).

## 0.0.6

* Add support for Battery Sense.

## 0.0.5

* Made the descriptions of the ID fields in settings easier to
  understand.

## 0.0.4

* Breaking Change: Report `electrical.batteries.*.stateOfCharge` as a
  ratio (0..1) not percentage.
* Add DC-DC Converters in a `electrical.converters.*` tree.
* Solar Chargers: Include `electrical.solar.*.panelPower`,
  `electrical.solar.*.loadCurrent`, and
  `electrical.solar.*.yieldToday`.
* BMVs: Include `electrical.batteries.*.power`.

## 0.0.3

* Bug fixes for 0.0.2.

## 0.0.2

* Improve documentation
* Report `electrical.batteries.*.capacity.dischargeSinceFull`.
* Report `electrical.batteries.*.temperature` when a BMV is in
  temperature aux mode.

## 0.0.1

* Initial Release
