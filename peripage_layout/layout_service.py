#!/usr/bin/env python3
"""
PeriPage Layout Addon — layout_service.py
Reçoit une liste de blocs JSON, compose la page, imprime via Bluetooth.

Endpoints :
  POST /print   — page complète via blocs
  GET  /health  — statut addon + Bluetooth
  GET  /status  — imprimante occupée ou non
"""

import sys
import json
import logging
import threading
import subprocess
import base64
import textwrap
import urllib.request
import io
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────
# Arguments
# ──────────────────────────────────────────────
if len(sys.argv) < 6:
    print("Usage: layout_service.py <MAC> <MODEL> <FONT> <FONT_SIZE> <PORT>")
    sys.exit(1)

PRINTER_MAC   = sys.argv[1]
PRINTER_MODEL = sys.argv[2]
FONT_NAME     = sys.argv[3]
FONT_SIZE     = int(sys.argv[4])
PORT          = int(sys.argv[5])

PRINT_WIDTH = 384  # Largeur PeriPage A6 en pixels

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("peripage-layout")

# ──────────────────────────────────────────────
# Polices
# ──────────────────────────────────────────────
FONT_MAP = {
    "DejaVu":     "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "DejaVuBold": "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "Liberation": "/usr/share/fonts/dejavu/DejaVuSans.ttf",   # fallback DejaVu
    "FreeSans":   "/usr/share/fonts/dejavu/DejaVuSans.ttf",   # fallback DejaVu
}

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuBold" if bold else FONT_NAME
    path = FONT_MAP.get(name)
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    log.warning(f"Police '{name}' introuvable, fallback PIL.")
    return ImageFont.load_default()

def line_height(font: ImageFont.FreeTypeFont) -> int:
    dummy = Image.new("L", (PRINT_WIDTH, 10))
    draw = ImageDraw.Draw(dummy)
    return draw.textbbox((0, 0), "Ay", font=font)[3] + 4

# ──────────────────────────────────────────────
# Verrou d'impression
# ──────────────────────────────────────────────
print_lock = threading.Lock()
printer_busy = False

# ──────────────────────────────────────────────
# Validation MAC
# ──────────────────────────────────────────────
def validate_mac(mac: str) -> bool:
    if mac.lower() == "xx:xx:xx:xx:xx:xx":
        return False
    parts = mac.split(":")
    if len(parts) != 6:
        return False
    try:
        [int(p, 16) for p in parts]
        return True
    except ValueError:
        return False

# ──────────────────────────────────────────────
# Renderers de blocs → PIL Image
# ──────────────────────────────────────────────

def render_separator(block: dict) -> Image.Image:
    """Ligne horizontale fine."""
    style = block.get("style", "line")  # line | dotted | blank
    height = 12
    img = Image.new("L", (PRINT_WIDTH, height), color=255)
    draw = ImageDraw.Draw(img)
    y = height // 2
    if style == "dotted":
        for x in range(10, PRINT_WIDTH - 10, 6):
            draw.point((x, y), fill=0)
    elif style != "blank":
        draw.line([(10, y), (PRINT_WIDTH - 10, y)], fill=180, width=1)
    return img


def render_text(block: dict) -> Image.Image:
    """Texte simple avec word-wrap."""
    text      = str(block.get("text", "")).strip()
    font_size = int(block.get("font_size", FONT_SIZE))
    bold      = bool(block.get("bold", False))
    align     = block.get("align", "left")
    padding   = int(block.get("padding", 4))

    font = load_font(font_size, bold)
    lh   = line_height(font)

    max_chars = max(10, int(PRINT_WIDTH / (font_size * 0.58)))
    lines = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.fill(paragraph, width=max_chars) if paragraph.strip() else ""
        lines.extend(wrapped.split("\n") if wrapped else [""])

    total_h = lh * len(lines) + padding * 2
    img  = Image.new("L", (PRINT_WIDTH, total_h), color=255)
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        if not line.strip():
            y += lh
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        w    = bbox[2] - bbox[0]
        if align == "center":
            x = (PRINT_WIDTH - w) // 2
        elif align == "right":
            x = PRINT_WIDTH - w - 8
        else:
            x = 8
        draw.text((x, y), line, font=font, fill=0)
        y += lh

    return img


def render_title(block: dict) -> Image.Image:
    """Titre : texte bold + taille augmentée."""
    return render_text({
        **block,
        "bold": True,
        "font_size": int(block.get("font_size", FONT_SIZE + 6)),
        "align": block.get("align", "center"),
        "padding": 6,
    })


def render_list(block: dict) -> Image.Image:
    """Liste d'éléments avec puce •"""
    items     = block.get("items", [])
    font_size = int(block.get("font_size", FONT_SIZE))
    bold      = bool(block.get("bold", False))
    bullet    = block.get("bullet", "•")
    padding   = 4

    font = load_font(font_size, bold)
    lh   = line_height(font)

    # Pré-calculer toutes les lignes wrappées
    max_chars = max(10, int((PRINT_WIDTH - 24) / (font_size * 0.58)))
    rendered_lines = []
    for item in items:
        text    = str(item).strip()
        wrapped = textwrap.fill(text, width=max_chars)
        sub     = wrapped.split("\n")
        rendered_lines.append((sub[0], True))       # première ligne avec puce
        for continuation in sub[1:]:
            rendered_lines.append((continuation, False))  # suite indentée

    total_h = lh * len(rendered_lines) + padding * 2
    img  = Image.new("L", (PRINT_WIDTH, total_h), color=255)
    draw = ImageDraw.Draw(img)

    y = padding
    for line, is_first in rendered_lines:
        if is_first:
            draw.text((8, y), bullet, font=font, fill=0)
            draw.text((8 + font_size, y), line, font=font, fill=0)
        else:
            draw.text((8 + font_size, y), line, font=font, fill=0)
        y += lh

    return img


def render_image_url(block: dict) -> Image.Image:
    """Télécharge et redimensionne une image depuis une URL."""
    url = block.get("url", "").strip()
    if not url:
        raise ValueError("Bloc image_url : champ 'url' manquant")
    req = urllib.request.Request(url, headers={"User-Agent": "PeriPage-Layout-Addon/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    return _fit_image(Image.open(io.BytesIO(data)).convert("L"))


def render_image_b64(block: dict) -> Image.Image:
    """Décode et redimensionne une image base64."""
    b64 = block.get("image", "").strip()
    if not b64:
        raise ValueError("Bloc image_b64 : champ 'image' manquant")
    data = base64.b64decode(b64)
    return _fit_image(Image.open(io.BytesIO(data)).convert("L"))


def _fit_image(img: Image.Image) -> Image.Image:
    """Redimensionne une image à PRINT_WIDTH en conservant le ratio."""
    w, h = img.size
    new_h = int(h * PRINT_WIDTH / w)
    return img.resize((PRINT_WIDTH, new_h), Image.LANCZOS)


# ──────────────────────────────────────────────
# Dispatcher de blocs
# ──────────────────────────────────────────────
BLOCK_RENDERERS = {
    "text":       render_text,
    "title":      render_title,
    "list":       render_list,
    "separator":  render_separator,
    "image_url":  render_image_url,
    "image_b64":  render_image_b64,
}

def compose_page(blocks: list) -> tuple:
    """
    Compose une liste de blocs en une seule image PIL.
    Retourne (Image, liste d'erreurs non fatales).
    """
    images = []
    warnings = []

    for i, block in enumerate(blocks):
        block_type = block.get("type", "")
        renderer   = BLOCK_RENDERERS.get(block_type)

        if not renderer:
            warnings.append(f"Bloc #{i} : type inconnu '{block_type}', ignoré")
            continue

        try:
            img = renderer(block)
            images.append(img)
        except Exception as e:
            warnings.append(f"Bloc #{i} ({block_type}) : erreur de rendu — {e}")
            log.warning(f"Bloc #{i} ({block_type}) ignoré : {e}")

    if not images:
        return None, warnings

    # Marge basse
    images.append(Image.new("L", (PRINT_WIDTH, 40), color=255))

    total_h = sum(img.height for img in images)
    page    = Image.new("L", (PRINT_WIDTH, total_h), color=255)
    y = 0
    for img in images:
        page.paste(img, (0, y))
        y += img.height

    return page, warnings

# ──────────────────────────────────────────────
# Impression Bluetooth
# ──────────────────────────────────────────────
def _image_to_printer_bytes(image: Image.Image) -> bytes:
    """
    Convertit une image PIL en bytes protocole PeriPage A6.
    Protocole : SPP RFCOMM, format Peripage natif.
    Header ligne : 0x1D 0x76 0x30 0x00 <w_lo> <w_hi> <h_lo> <h_hi>
    suivi des bytes bitmap (1 bit par pixel, MSB en premier).
    """
    img = image.convert("L")
    w, h = img.size
    if w != PRINT_WIDTH:
        new_h = int(h * PRINT_WIDTH / w)
        img = img.resize((PRINT_WIDTH, new_h), Image.LANCZOS)
        w, h = img.size

    img = img.convert("1", dither=Image.FLOYDSTEINBERG)

    BYTES_PER_LINE = PRINT_WIDTH // 8  # 48

    # Commande ESC/POS raster bitmap :
    # GS v 0 — impression bitmap raster
    # 0x1D 0x76 0x30 0x00 <xL> <xH> <yL> <yH> <data>
    xL = BYTES_PER_LINE & 0xFF
    xH = (BYTES_PER_LINE >> 8) & 0xFF
    yL = h & 0xFF
    yH = (h >> 8) & 0xFF

    data = bytearray()
    data += bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH])

    for y in range(h):
        line_bytes = bytearray(BYTES_PER_LINE)
        for x in range(PRINT_WIDTH):
            if img.getpixel((x, y)) == 0:  # noir
                line_bytes[x // 8] |= (0x80 >> (x % 8))
        data += bytes(line_bytes)

    # Avance papier : ESC d n (n lignes)
    data += bytes([0x1B, 0x64, 0x04])

    return bytes(data)


def _do_print(image: Image.Image) -> dict:
    result = {"success": False, "error": None}

    def _thread():
        import socket
        sock = None
        try:
            printer_bytes = _image_to_printer_bytes(image)
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                                 socket.BTPROTO_RFCOMM)
            sock.settimeout(15)
            sock.connect((PRINTER_MAC, 1))
            chunk_size = 256
            for i in range(0, len(printer_bytes), chunk_size):
                sock.send(printer_bytes[i:i + chunk_size])
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            log.error(f"Erreur Bluetooth : {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    t.join(timeout=30)

    if t.is_alive():
        result["error"] = "Timeout Bluetooth (30s)"

    return result


def send_to_printer(image: Image.Image) -> tuple:
    global printer_busy
    if not print_lock.acquire(blocking=False):
        return False, "Imprimante occupée"
    printer_busy = True
    try:
        result = _do_print(image)
        return result["success"], result.get("error")
    finally:
        printer_busy = False
        try:
            print_lock.release()
        except RuntimeError:
            pass

# ──────────────────────────────────────────────
# Helpers HTTP
# ──────────────────────────────────────────────
def _read_json(handler) -> tuple:
    try:
        length = int(handler.headers.get("Content-Length", 0))
        raw    = handler.rfile.read(length)
        log.info(f"BODY RECU ({length} bytes): {raw[:200]}")
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"JSON invalide : {e}"
    except Exception as e:
        return None, f"Erreur lecture body : {e}"


def _send(handler, code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)

# ──────────────────────────────────────────────
# Handler HTTP
# ──────────────────────────────────────────────
class LayoutHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        log.info(fmt % args)

    def do_GET(self):
        if self.path == "/health":
            ok = validate_mac(PRINTER_MAC)
            _send(self, 200 if ok else 503, {
                "status": "ok" if ok else "error",
                "mac": PRINTER_MAC,
                "model": PRINTER_MODEL,
                "font": FONT_NAME,
                "font_size": FONT_SIZE,
                "port": PORT,
                "supported_blocks": list(BLOCK_RENDERERS.keys()),
            })

        elif self.path == "/status":
            _send(self, 200, {
                "busy": printer_busy,
                "mac": PRINTER_MAC,
            })

        else:
            _send(self, 404, {"error": "Route inconnue"})

    def do_POST(self):
        if self.path != "/print":
            return _send(self, 404, {"error": "Route inconnue"})

        data, err = _read_json(self)
        if err:
            return _send(self, 400, {"error": err})

        blocks = data.get("blocks", [])
        if not isinstance(blocks, list) or len(blocks) == 0:
            return _send(self, 400, {"error": "Champ 'blocks' manquant ou vide"})

        # Composition de la page
        page, warnings = compose_page(blocks)

        if page is None:
            return _send(self, 422, {
                "error": "Aucun bloc n'a pu être rendu",
                "warnings": warnings,
            })

        # Impression
        ok, error = send_to_printer(page)

        if not ok:
            code = 503 if "occupée" in str(error) else 500
            return _send(self, code, {"error": error, "warnings": warnings})

        _send(self, 200, {
            "status": "printed",
            "blocks_rendered": len(blocks) - len(warnings),
            "warnings": warnings,
        })

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    if not validate_mac(PRINTER_MAC):
        log.error(f"Adresse MAC invalide ou placeholder : '{PRINTER_MAC}'")
        sys.exit(1)

    try:
        result = subprocess.run(["hciconfig", "-a"], capture_output=True, text=True, timeout=5)
        log.info("Adaptateurs Bluetooth :")
        for line in result.stdout.splitlines():
            log.info(f"  {line}")
    except Exception as e:
        log.warning(f"hciconfig non disponible : {e}")

    log.info(f"PeriPage Layout Addon démarré — port {PORT}")
    log.info(f"Imprimante : {PRINTER_MODEL} @ {PRINTER_MAC}")
    log.info(f"Police : {FONT_NAME} {FONT_SIZE}px")
    log.info(f"Blocs supportés : {', '.join(BLOCK_RENDERERS.keys())}")


    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LayoutHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Arrêt.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
