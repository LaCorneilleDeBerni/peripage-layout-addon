ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

RUN apk add --no-cache \
    python3 \
    py3-pip \
    bluez \
    bluez-dev \
    bluez-deprecated \
    musl-dev \
    gcc \
    python3-dev \
    libjpeg-turbo \
    openjpeg \
    tiff \
    freetype \
    ttf-dejavu \
    ttf-liberation \
    wget \
    bash

RUN pip3 install --no-cache-dir --break-system-packages \
    "git+https://github.com/pybluez/pybluez@master#egg=pybluez" \
    Pillow \
    requests

RUN pip3 install --no-cache-dir --break-system-packages --no-deps peripage==1.2

RUN wget -q https://github.com/googlefonts/noto-emoji/raw/v2.034/fonts/NotoEmoji-Regular.ttf \
    -O /usr/share/fonts/NotoEmoji-Regular.ttf

COPY run.sh /
COPY layout_service.py /
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]
