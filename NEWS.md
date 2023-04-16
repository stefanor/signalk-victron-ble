# Changelog

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
