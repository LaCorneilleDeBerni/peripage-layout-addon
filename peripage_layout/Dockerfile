ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-pillow \
    bluez \
    bluez-libs \
    bluez-dev \
    python3-dev \
    musl-dev \
    gcc \
    ttf-dejavu \
    ttf-liberation \
    font-freefont \
    wget \
    git

# PyBluez depuis git master (compatible Python 3.12)
RUN pip3 install --break-system-packages \
    git+https://github.com/pybluez/pybluez.git#egg=PyBluez

# Librairie peripage
RUN pip3 install --break-system-packages peripage==1.2 Pillow requests

# NotoEmoji v2.034 — format TTF classique compatible Pillow
RUN wget -q "https://github.com/googlefonts/noto-emoji/raw/v2.034/fonts/NotoEmoji-Regular.ttf" \
    -O /usr/share/fonts/NotoEmoji-Regular.ttf \
    && echo "Police emoji installée OK" \
    || echo "Téléchargement échoué"

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
