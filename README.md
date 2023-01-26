# signalk-victron-ble

A SignalK plugin that reads Victron data over Instant Readout Bluetooth
Low Energy (BLE) messages.

This is built on top of the
[victron_ble](https://github.com/keshavdv/victron-ble) Python library,
by Keshav Varma.

Currently supported:

* BMV 712 Battery Monitors.
* BlueSolar MPPT chargers (but untested in production).

## Installation

- Before installing, you need to have `python3` installed, with a
  working `venv` module.
  - On Debian/Ubuntu/Raspbian, this means installing the `python3-venv` package.
- Install this plugin through SignalK / npm.
- Use the native Victron app to obtain advertisement keys for
  communicating with your Victron devices.
  There are instructions for this
  [here](https://github.com/keshavdv/victron-ble#usage).
- Enter the MAC address and advertisment key for each device in the
  plugin settings in SignalK.
- Restart SignalK.

## Development

- clone the plugin from Github
- `npm link` in the plugin directory
- `npm link signalk-victron-ble` in your server directory

## License

Copyright 2022-2023 Stefano Rivera <stefano@rivera.za.net>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
