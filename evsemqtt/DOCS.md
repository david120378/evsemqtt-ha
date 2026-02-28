# evseMQTT

Controls the Besen BS20 Electric Vehicle Charging Wallbox and exposes it to Home Assistant via MQTT Discovery. Supports both Bluetooth (BLE) and WiFi (TCP) connections.

## Prerequisites

- A Besen BS20 Wallbox (or compatible device)
- The **Mosquitto MQTT broker** addon installed and running in Home Assistant
- For BLE mode: a Bluetooth adapter on your Home Assistant host
- For WiFi mode: the Wallbox connected to your local network

## Configuration

### WiFi Mode (Recommended)

Set `WIFI_ENABLED` to `true` and enter the IP address of your Wallbox under `WIFI_ADDRESS`.

To find the Wallbox's IP, check your router's DHCP client list for a device starting with `ACP#`.

The default TCP port is `6722`. Change `WIFI_PORT` only if your device uses a different port.

### BLE Mode

Set `WIFI_ENABLED` to `false` and enter the MAC address of your Wallbox under `BLE_ADDRESS`.

To find the MAC address, scan for BLE devices and look for one whose name starts with `ACP#`:

```bash
bluetoothctl scan le
```

### MQTT Settings

If you are using the Mosquitto broker addon, set `MQTT_BROKER` to `core-mosquitto`.

### Power Unit

Set `UNIT` to `W` (watts) or `kW` (kilowatts) depending on your preference.

## Home Assistant Integration

Once the addon is running, your Wallbox will automatically appear as a device in Home Assistant through MQTT Discovery. You will find controls for:

- Start / Stop charging
- Set maximum amperage
- Device name, language, temperature unit

And sensors for:

- Current power consumption
- Voltage and current per phase
- Total energy consumed
- Temperature (inner and outer)
- Plug and charging state
- Error state

## Troubleshooting

- Set `LOGGING_LEVEL` to `DEBUG` for detailed output in the addon log.
- If the BLE adapter crashes, set `SYS_MODULE_TO_RELOAD` to `btusb` (USB dongle) or `hci_uart` (Raspberry Pi built-in).
- If no data arrives after connecting, verify your password with `BLE_PASSWORD` / WiFi password.
