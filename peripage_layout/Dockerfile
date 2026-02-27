ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-pillow \
    bluez \
    bluez-libs \
    ttf-dejavu \
    wget

# NotoEmoji v2.034 — format TTF classique compatible Pillow
RUN wget -q "https://github.com/googlefonts/noto-emoji/raw/v2.034/fonts/NotoEmoji-Regular.ttf" \
    -O /usr/share/fonts/NotoEmoji-Regular.ttf \
    && echo "Police emoji installée OK" \
    || echo "Téléchargement échoué"

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
