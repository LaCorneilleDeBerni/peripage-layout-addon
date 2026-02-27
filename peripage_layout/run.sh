#!/usr/bin/with-contenv bashio

MAC=$(bashio::config 'printer_mac')
MODEL=$(bashio::config 'printer_model')
FONT=$(bashio::config 'font')
FONT_SIZE=$(bashio::config 'font_size')
PORT=$(bashio::config 'port')
BT_ADAPTER=$(bashio::config 'bluetooth_adapter')

bashio::log.info "PeriPage Layout — démarrage"
bashio::log.info "MAC: ${MAC} | Modèle: ${MODEL} | Port: ${PORT} | Adaptateur: ${BT_ADAPTER}"

trap 'bashio::log.info "Arrêt."; kill ${PID} 2>/dev/null; exit 0' SIGTERM SIGINT

python3 /layout_service.py "${MAC}" "${MODEL}" "${FONT}" "${FONT_SIZE}" "${PORT}" "${BT_ADAPTER}" &
PID=$!
wait ${PID}
