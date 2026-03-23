# Besen Wallbox WiFi (UDP)

Verbindet die Besen BS20 Wallbox mit Home Assistant über **WiFi (UDP)** oder Bluetooth (BLE) und stellt alle Sensoren und Steuerungen automatisch per MQTT Discovery bereit.

## Voraussetzungen

- Besen BS20 Wallbox (oder kompatibles Gerät)
- **Mosquitto MQTT Broker** Addon installiert und gestartet
- Für WiFi-Modus: Wallbox im gleichen Subnetz wie der HA-Host

## WiFi-Modus (empfohlen)

Setze `WIFI_ENABLED` auf `true`. Die Wallbox wird automatisch per UDP-Broadcast erkannt — **keine IP-Adresse nötig**.

Der Standard-Port ist `28376`. Änderung nur nötig wenn deine Wallbox einen anderen Port verwendet.

## BLE-Modus

Setze `WIFI_ENABLED` auf `false` und trage die MAC-Adresse deiner Wallbox unter `BLE_ADDRESS` ein.

MAC-Adresse auf dem HA-Host ermitteln:
```bash
bluetoothctl scan le
```

## MQTT

Bei Verwendung des Mosquitto-Addons: `MQTT_BROKER` auf `core-mosquitto` setzen.

## Leistungseinheit

`UNIT` auf `W` (Watt) oder `kW` (Kilowatt) setzen.

## Reconnect-Verhalten

Das Addon verbindet sich nach einem HA-Neustart oder Verbindungsabbruch **automatisch** neu:

- Sendet die Wallbox noch Heartbeats (sie hält die Session für aktiv), erkennt das Addon das und antwortet sofort — ohne neue Login-Beacons abzuwarten.
- Sendet die Wallbox neue Login-Beacons, läuft der vollständige Login-Flow erneut durch.
- Hört die Wallbox ganz auf zu senden, verschickt das Addon alle 10 Sekunden einen Wakeup-Broadcast (und Unicast an die zuletzt bekannte IP), um sie wieder zu aktivieren.

## Troubleshooting

- `LOGGING_LEVEL` auf `DEBUG` setzen für detaillierte Logs
- Bei BLE-Abstürzen: `SYS_MODULE_TO_RELOAD` auf `btusb` (USB-Dongle) oder `hci_uart` (Raspberry Pi) setzen
- PIN der Wallbox unter `BLE_PASSWORD` prüfen (Standard: `123456`)
- Im Log nach `Session recovery via heartbeat` suchen — das bestätigt, dass der automatische Reconnect funktioniert hat
