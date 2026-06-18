## v0.4.1 — 2026-06-18
**Bugfix: Einheit beim Akku-Term korrigiert**
`battery_w` wird jetzt mit `kw_multiplier` multipliziert. Der Akku-Term wurde zuvor in kW statt W berechnet, wodurch der Abzug der PV-Akku-Entladung praktisch wirkungslos war (≈6 W statt ≈5800 W).

## v0.4.0 — 2026-06-18
**Neu: Hybrid-WR-Akkuschutz in Überschuss-Ampere-Regelung**
Neuer optionaler Input `battery_discharge_sensor` im Ampere-Blueprint. Akkuentladung wird vom verfügbaren PV-Überschuss abgezogen, damit die Wallbox nicht auf Kosten des Hausspeichers lädt.

## v0.3.4 — 2026-05-11
**Fix: Watchdog-Automation robuster gestaltet**
Trigger auf `time_pattern` (alle 10 Minuten) + `last_updated > 20 min`-Bedingung umgestellt. Greift zuverlässig auch wenn `expire_after` noch nicht in der aktiven Discovery-Config enthalten ist.

## v0.3.3 — 2026-04-21
**Fix: Dockerfile auf BUILD_ARCH umgestellt**
`BUILD_ARCH` ersetzt `BUILD_FROM` — wird vom Supervisor immer übergeben, `BUILD_FROM` nur noch mit `build.yaml`.

## v0.3.2 — 2026-04-21
**Fix: build.yaml entfernt**
Vom HA Supervisor als deprecated markiert.

## v0.3.1 — 2026-04-21
**Fix: Veraltete Architekturen entfernt**
`armhf`, `armv7`, `i386` aus `config.yaml` entfernt.

## v0.3.0 — 2026-04-17
**Neu: Blueprints integriert + Ampere-Stabilisierung**
Alle Blueprints direkt im Addon-Repo. Ladestrom wird nur noch angepasst wenn Änderung ≥3A.

## v0.2.10 — 2026-04-17
**Verbesserung: 60s Cooldown nach Neustart**
Verhindert kaskadierte Stop/Start-Zyklen bei schwankender PV-Leistung.

## v0.1.14 — 2026-03-26
**Verbesserung: `expire_after` für Lade-Topic-Entitäten**
HA markiert Entitäten automatisch als nicht verfügbar nach 90s ohne MQTT-Update.

## v0.1.13 — 2026-03-24
**Bugfix: `config_topic` aus MQTT-Discovery-Payload entfernt**
HA lehnte Discovery-Configs mit unbekannten Feldern ab — Switch, Number, Text, Select blieben dauerhaft unavailable.

## v0.1.6 — 2026-03-23
**Bugfix: Automatischer Reconnect ohne App-Eingriff**
Session Recovery via Heartbeat (cmd=3) ohne vollen Login-Beacon-Flow.

## v0.1.0 — 2026-03-01
Erstes stabiles Release.
