ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-pillow \
    bluez \
    bluez-libs \
    ttf-dejavu \
    font-noto-emoji

RUN find /usr/share/fonts -name "*moji*" -o -name "*noto*" 2>/dev/null | head -20

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
