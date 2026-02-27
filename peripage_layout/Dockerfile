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

# Symbola — police Unicode complète noir et blanc, idéale impression thermique
RUN wget -q "https://github.com/nicowillis/fonts/raw/master/Symbola.ttf" \
    -O /usr/share/fonts/Symbola.ttf \
    && echo "Symbola installée OK" \
    || echo "Téléchargement Symbola échoué"

COPY run.sh /
COPY layout_service.py /

RUN chmod +x /run.sh

CMD ["/run.sh"]
