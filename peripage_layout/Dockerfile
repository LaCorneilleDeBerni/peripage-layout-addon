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

RUN wget -q "https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoEmoji-Regular.ttf" \
    -O /usr/share/fonts/NotoEmoji-Regular.ttf || \
    echo "Téléchargement police emoji échoué, les emojis seront en carré"

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
