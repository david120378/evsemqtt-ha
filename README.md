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
| `WIFI_IP` | Optionale statische IP der Wallbox (verbessert Reconnect-Zuverlässigkeit) | — |
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

---

## Changelog

### v0.1.15 — 2026-04-15
**Bugfix: Fehlerbehandlung für fehlerhafte/zu kurze Pakete**

Empfängt die Wallbox ein fehlerhaftes oder zu kurzes UDP-Paket (z. B. `system_time`-Paket mit weniger als 5 Bytes), crashte der `system_time`-Parser mit `IndexError: bytearray index out of range`. Die Exception wurde von asyncio still geschluckt (`Task exception was never retrieved`) und tauchte nur im Log auf.

Zwei Fixes:
- **`parsers.py` – `system_time`**: Explizite Längenprüfung (`len(data) < 5 → return {}`) bevor auf die Bytes zugegriffen wird.
- **`event_handlers.py` – `handle_notification`**: Zentrales `try/except` um alle Parser-Aufrufe — fängt künftige Parser-Fehler aller Handler ab, loggt sie als `WARNING` mit Cmd-ID und Datenlänge, und bricht den Task sauber ab statt ihn crashen zu lassen.

### v0.1.6 — 2026-03-23
**Bugfix: Automatischer Reconnect ohne App-Eingriff**

Nach einem HA-Neustart oder einem kurzzeitigen Verbindungsabbruch sendete die Wallbox weiterhin **Heartbeat-Pakete** (statt neue Login-Beacons) — da sie die Session noch als aktiv betrachtete. Das Addon ignorierte diese Heartbeats, weil `initialization_state = False` war. Die Wallbox wartete vergeblich auf eine Antwort, timeout-te schließlich und hörte ganz auf zu senden. Danach half nur noch das Öffnen der App.

Zwei Fixes:
- **Session Recovery via Heartbeat**: Empfängt das Addon einen Heartbeat (cmd=3) ohne initialisiert zu sein, extrahiert es den Serial aus dem Paket-Header, stellt den Geräte-State wieder her (`initialization_state=True`, `logged_in=True`), beantwortet den Heartbeat sofort und fragt die Konfiguration neu ab — ohne den vollen Login-Beacon-Flow.
- **`software_version` Reset bei Timeout**: Beim Reconnect-Watchdog wurde `software_version` nicht zurückgesetzt, was den Login-Flow nach einem Timeout blockiert hat.

### v0.1.4 — 2026-03-13
**Verbesserung: Robusterer Reconnect-Mechanismus im WiFi-Modus**

Wenn die Wallbox kurzzeitig aufhört, UDP-Broadcasts zu senden (z. B. nach einem Stromausfall oder App-Zugriff), reichte der bisherige Broadcast-Wakeup (`255.255.255.255`) allein nicht immer aus — insbesondere wenn die Wallbox zwar erreichbar, aber im Broadcast-"Schlaf" war.

Neue Funktionen:
- **IP-Caching**: Die zuletzt gesehene Wallbox-IP wird in `/data/last_wallbox_ip.txt` gespeichert und nach einem Add-on-Neustart sofort für direkten Wakeup genutzt.
- **Direkter Unicast-Wakeup**: Wakeup-Pakete werden jetzt an Broadcast UND an die bekannte/konfigurierte Wallbox-IP gesendet, was die Reconnect-Zuverlässigkeit deutlich verbessert.
- **Schnellere Retry-Schleife**: Nach einem Verbindungsabbruch werden Wakeup-Pakete alle 10 Sekunden wiederholt (statt alle 35 Sekunden).
- **Neues Konfigurations-Feld `WIFI_IP`**: Optionale statische IP der Wallbox — nützlich wenn DHCP-Adressänderungen vorkommen.

### v0.1.3 — 2026-03-08
**Bugfix: Stabilitätsproblem bei eingehenden MQTT-Kommandos im WiFi-Modus behoben**

Im WiFi-Modus konnte das Addon abstürzen, wenn ein MQTT-Kommando (z. B. Laden starten/stoppen) eintraf, während die UDP-Verbindung zur Wallbox kurzzeitig unterbrochen war. Ursache war die Verwendung von `asyncio.run()` im MQTT-Callback, das bei jedem Aufruf einen neuen Event Loop erzeugt — inkompatibel mit der `asyncio.Queue`, die an den Haupt-Event-Loop gebunden ist.

Fix: `asyncio.run()` ersetzt durch `asyncio.run_coroutine_threadsafe()`, das Coroutinen thread-sicher in den laufenden Haupt-Event-Loop einreiht. Zusätzlich wird die Queue jetzt innerhalb von `serve()` initialisiert, um sicherzustellen, dass sie immer im richtigen Loop-Kontext erstellt wird.

### v0.1.2 — 2026-02-xx
Reconnect-Watchdog direkt beim Start von `serve()` aktiviert.

### v0.1.1 — 2026-02-xx
Wakeup-Broadcast bei Verbindungsabbruch statt Prozess-Neustart.

### v0.1.0 — 2026-01-xx
Erstes stabiles Release.
