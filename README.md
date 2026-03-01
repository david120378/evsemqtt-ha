# Besen Wallbox WiFi (UDP) — Home Assistant Addon

Dieses Addon verbindet die **Besen BS20 Wallbox** mit Home Assistant über WiFi (UDP) oder Bluetooth (BLE) und stellt alle Sensoren und Steuerungen automatisch per **MQTT Discovery** bereit.

---

## Ziel

Die Besen BS20 Wallbox kommuniziert über ein proprietäres Binärprotokoll — entweder per Bluetooth oder über UDP-Broadcasts im lokalen Netzwerk. Dieses Addon lauscht auf diese UDP-Broadcasts, authentifiziert sich bei der Wallbox und veröffentlicht alle Daten in Home Assistant via MQTT.

**Kein Cloud-Zugang, keine App-Abhängigkeit** — die Wallbox wird vollständig lokal gesteuert.

---

## Wie es funktioniert

Die Wallbox sendet alle ~3 Sekunden einen **UDP-Broadcast** (Port `28376`) ins lokale Netzwerk. Das Addon:

1. Lauscht auf UDP-Port `28376`
2. Erkennt die Wallbox automatisch anhand des Broadcasts (keine IP-Konfiguration nötig)
3. Authentifiziert sich mit dem Geräte-PIN
4. Empfängt Lade- und Statusdaten
5. Veröffentlicht alles in Home Assistant via MQTT Discovery

---

## Installation

### 1. Addon-Repository in Home Assistant hinzufügen

1. **Einstellungen → Addons → Addon Store** öffnen
2. Oben rechts auf **⋮ → Custom repositories** klicken
3. URL eintragen:
   ```
   https://github.com/david120378/evsemqtt-ha
   ```
4. **Hinzufügen** klicken — das Addon erscheint danach im Store

### 2. Voraussetzungen

- **Mosquitto MQTT Broker** Addon muss installiert und gestartet sein
  (`Einstellungen → Addons → Mosquitto broker`)
- Die Wallbox muss mit dem **gleichen WLAN** verbunden sein wie der Home Assistant Host
- Der HA-Host und die Wallbox müssen im **gleichen Subnetz** liegen (damit UDP-Broadcasts ankommen)

### 3. Addon installieren und konfigurieren

1. Addon im Store suchen: **„Besen Wallbox WiFi (UDP)"**
2. **Installieren**
3. **Konfiguration** öffnen und folgende Felder ausfüllen:

---

## Konfiguration

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| `WIFI_ENABLED` | `true` für WiFi-Modus (UDP), `false` für BLE | `false` |
| `WIFI_PORT` | UDP-Port auf dem die Wallbox Broadcasts sendet | `28376` |
| `BLE_ADDRESS` | MAC-Adresse der Wallbox (nur BLE-Modus) | — |
| `BLE_PASSWORD` | 6-stelliger PIN der Wallbox | `123456` |
| `UNIT` | Einheit für Leistungsanzeige: `W` oder `kW` | `W` |
| `MQTT_BROKER` | Hostname des MQTT-Brokers | `core-mosquitto` |
| `MQTT_PORT` | Port des MQTT-Brokers | `1883` |
| `MQTT_USER` | MQTT-Benutzername | — |
| `MQTT_PASSWORD` | MQTT-Passwort | — |
| `LOGGING_LEVEL` | Log-Verbosität: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SYS_MODULE_TO_RELOAD` | Bluetooth-Kernelmodul bei Crash neu laden (BLE) | — |

### Minimale WiFi-Konfiguration

```yaml
WIFI_ENABLED: true
BLE_PASSWORD: "123456"   # dein Wallbox-PIN
MQTT_BROKER: core-mosquitto
MQTT_USER: dein_mqtt_user
MQTT_PASSWORD: dein_mqtt_passwort
```

> **Hinweis:** Im WiFi-Modus wird keine IP-Adresse der Wallbox benötigt — sie wird automatisch per UDP-Broadcast erkannt.

---

## Home Assistant Integration

Sobald das Addon läuft und die Wallbox erkannt wurde, erscheint unter
**Einstellungen → Geräte & Dienste → MQTT** ein neues Gerät mit allen Entitäten:

**Sensoren:**
- Aktuelle Ladeleistung (W / kW)
- Spannung und Strom pro Phase
- Gesamtenergie der aktuellen Session
- Innen- und Außentemperatur
- Lade- und Verbindungsstatus
- Fehlerzustand

**Steuerungen:**
- Laden starten / stoppen
- Maximale Stromstärke setzen
- Gerätename, Sprache, Temperatureinheit

---

## Troubleshooting

**Wallbox wird nicht erkannt**
- Prüfen ob HA-Host und Wallbox im gleichen Subnetz sind
- UDP-Broadcasts mit tcpdump prüfen: `sudo tcpdump -n -i en0 src host <wallbox-ip> and udp`
- `LOGGING_LEVEL` auf `DEBUG` setzen

**Authentifizierung schlägt fehl**
- `BLE_PASSWORD` prüfen (6-stelliger PIN, Standard `123456`)

**BLE-Adapter stürzt ab**
- `SYS_MODULE_TO_RELOAD` auf `btusb` (USB-Dongle) oder `hci_uart` (Raspberry Pi) setzen

---

## Technische Details

- Protokoll: proprietäres Binärformat (`0x0601` Header, `0x0f02` Tail)
- Transport WiFi: UDP-Broadcast, Port `28376`, Auto-Discovery
- Transport BLE: GATT Notifications (bleak)
- Basiert auf: [slespersen/evseMQTT](https://github.com/slespersen/evseMQTT)
