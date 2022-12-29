# signalk-victron-ble

A SignalK plugin that reads Victron data over Instant Readout Bluetooth
Low Energy (BLE) messages.

This is built on top of the
[victron_ble](https://github.com/keshavdv/victron-ble) Python library,
by Keshav Varma.

Currently supported: Battery Monitors.

## Development

- clone the plugin from Github
- `npm link` in the plugin directory
- `npm link signalk-victron-ble` in your server directory
