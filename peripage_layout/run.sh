#!/usr/bin/with-contenv bashio

MAC=$(bashio::config 'printer_mac')
MODEL=$(bashio::config 'printer_model')
FONT=$(bashio::config 'font')
FONT_SIZE=$(bashio::config 'font_size')
PORT=$(bashio::config 'port')

bashio::log.info "PeriPage Layout — démarrage"
bashio::log.info "MAC: ${MAC} | Modèle: ${MODEL} | Police: ${FONT} ${FONT_SIZE}px | Port: ${PORT}"

trap 'bashio::log.info "Arrêt du service."; kill ${PID}; exit 0' SIGTERM SIGINT

python3 /layout_service.py "${MAC}" "${MODEL}" "${FONT}" "${FONT_SIZE}" "${PORT}" &
PID=$!
wait ${PID}
