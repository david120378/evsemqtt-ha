#!/usr/bin/env sh

# Parse Home Assistant addon options from /data/options.json
if [ -f "/data/options.json" ]; then
    echo "Parsing /data/options.json ..."
    export $(jq -r 'to_entries | .[] | "\(.key)=\(.value)"' "/data/options.json")
fi

SYS_MODULE_TO_RELOAD=${SYS_MODULE_TO_RELOAD:-""}
RSSI=${RSSI:-"false"}
WIFI_ENABLED=${WIFI_ENABLED:-"false"}
WIFI_SERVER=${WIFI_SERVER:-"false"}
WIFI_PORT=${WIFI_PORT:-6722}
EXTRA_ARGS=""

if [ "${WIFI_ENABLED}" = "true" ]; then
    if [ "${WIFI_SERVER}" = "true" ]; then
        EXTRA_ARGS="${EXTRA_ARGS} --wifi --wifi_server --wifi_port ${WIFI_PORT}"
    else
        EXTRA_ARGS="${EXTRA_ARGS} --wifi --wifi_address ${WIFI_ADDRESS} --wifi_port ${WIFI_PORT}"
    fi
else
    if [ "${RSSI}" = "true" ]; then
        EXTRA_ARGS="${EXTRA_ARGS} --rssi"
    fi
fi

if [ -n "${SYS_MODULE_TO_RELOAD}" ]; then
    echo "Sys module reload enabled for: ${SYS_MODULE_TO_RELOAD}"
    if [ -d /lib/modules/ ]; then
        echo "Reloading module: ${SYS_MODULE_TO_RELOAD}"
        modprobe -r "${SYS_MODULE_TO_RELOAD}"
        sleep 2
        modprobe "${SYS_MODULE_TO_RELOAD}"
        sleep 2
        echo "Sys module reload done"
    else
        echo "Modules folder '/lib/modules/' not mounted, skipping reload."
    fi
fi

echo "Starting evseMQTT ..."

set -ex

if [ "${WIFI_ENABLED}" = "true" ]; then
    evseMQTT \
        --password "${BLE_PASSWORD}" \
        --unit "${UNIT}" \
        --mqtt \
        --mqtt_broker "${MQTT_BROKER}" \
        --mqtt_port "${MQTT_PORT}" \
        --mqtt_user "${MQTT_USER}" \
        --mqtt_password "${MQTT_PASSWORD}" \
        --logging_level "${LOGGING_LEVEL}" \
        ${EXTRA_ARGS}
else
    evseMQTT \
        --address "${BLE_ADDRESS}" \
        --password "${BLE_PASSWORD}" \
        --unit "${UNIT}" \
        --mqtt \
        --mqtt_broker "${MQTT_BROKER}" \
        --mqtt_port "${MQTT_PORT}" \
        --mqtt_user "${MQTT_USER}" \
        --mqtt_password "${MQTT_PASSWORD}" \
        --logging_level "${LOGGING_LEVEL}" \
        ${EXTRA_ARGS}
fi
