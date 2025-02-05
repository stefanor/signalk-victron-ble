# Victron BLE Plugin: Raspberry Pi 4 Stability & Multi-Adapter Support

## Summary  
This update adds critical support for **external Bluetooth adapters** to address instability with Raspberry Pi 4's built-in Bluetooth hardware when used with Victron devices. Users can now select between adapters (e.g., `hci1` for USB dongles) via SignalK UI to bypass Pi 4's unreliable native Bluetooth stack.

## Key Changes  
### 🛠️ Pi 4 Hardware Workarounds  
- **Adapters now selectable in UI** (hci0/hci1) to support external BLE dongles  
- Default changed to **external adapters (hci1)** for stable operation  
- Added auto-recovery for adapter disconnects  

### 🪲 Why This Matters for Pi 4 Users  
Pi 4's built-in Bluetooth:  
➔ Fails to maintain stable GATT connections  
➔ Causes packet loss with Victron devices  
External dongles (e.g., CSR4.0/Plugable BT4LE) resolve these issues.

---

## Full Changelog  
### Features  
- `007d6c8`: Core Bluetooth adapter selection logic  
- `9471a9d`: UI configuration for adapter switching  
- `ee255ed`: Packet logging (size/timestamp/RSSI) for debugging  


### Fixes & Stability  
- `d9ba0c3`: Compatibility with Bleak 0.20+ APIs  
- `3e7aa1c`: Adapter selection via OS environment  
- `6a21b55`: Health monitoring and restart logic  


### Code Quality  
- `c62a146`/`a911e39`: Type hint improvements  
- `4dcba99`: Reduced log noise for production  

---

## Verification Steps  
1. **Adapter Selection** (Pi 4 + USB dongle):  
   - Set to `hci1` → Confirm logs show `[DEBUG] Using Bluetooth adapter hci1`  
2. **Stability Test**:  
   - Unplug dongle → Verify auto-restart after 5s  
3. **Device Naming**:  
   - Ensure Victron-reported names appear under `electrical.devices.*.deviceName`  

**Tested Hardware**: Raspberry Pi 4 (Buster) + Victron Orion XS/SmartShunt + Plugable USB-BT4LE dongle.  
**Requires**: [`bleak>=0.20.0`](https://pypi.org/project/bleak/)  

