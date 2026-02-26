ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-pillow \
    bluez \
    bluez-libs \
    ttf-dejavu \
    gcc \
    musl-dev \
    python3-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev

COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
