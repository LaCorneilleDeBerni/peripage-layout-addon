#!/usr/bin/env python3
"""
PeriPage Layout Addon — layout_service.py
"""

import sys, json, logging, threading, base64, textwrap, urllib.request, io, os, time
import peripage as pp
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 6:
    print("Usage: layout_service.py <MAC> <MODEL> <FONT> <FONT_SIZE> <PORT> [CUSTOM_FONTS_JSON]")
    sys.exit(1)

PRINTER_MAC   = sys.argv[1]
PRINTER_MODEL = sys.argv[2]
FONT_NAME     = sys.argv[3]
FONT_SIZE     = int(sys.argv[4])
PORT          = int(sys.argv[5])
CUSTOM_FONTS_JSON = sys.argv[6] if len(sys.argv) > 6 else "[]"
PRINT_WIDTH   = 384

# Polices custom chargées au démarrage : {"NomPolice": ImageFont, ...}
CUSTOM_FONT_CACHE = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("peripage-layout")

FONT_MAP = {
    "DejaVu":     "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "DejaVuBold": "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "Liberation": "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
}

FONT_MAP_BOLD = {
    "DejaVu":     "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuBold": "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "Liberation": "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
}

def load_custom_fonts():
    """Télécharge et charge les polices custom déclarées dans la config."""
    global CUSTOM_FONT_CACHE
    # Lire depuis /data/options.json (fichier config généré par HA)
    fonts = []
    try:
        with open("/data/options.json", "r") as f:
            options = json.load(f)
        fonts = options.get("custom_fonts", [])
    except Exception:
        # Fallback sur l'argument CLI
        try:
            fonts = json.loads(CUSTOM_FONTS_JSON)
        except Exception:
            log.warning("Impossible de lire custom_fonts depuis la config")
            return
    if not fonts:
        return
    for entry in fonts:
        name = entry.get("name", "").strip()
        url  = entry.get("url", "").strip()
        if not name or not url:
            continue
        dest = f"/tmp/custom_font_{name}.ttf"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PeriPage-Layout-Addon/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            # Test que Pillow peut la lire
            ImageFont.truetype(dest, 24)
            CUSTOM_FONT_CACHE[name] = dest
            log.info(f"Police custom '{name}' chargée depuis {url}")
        except Exception as e:
            log.warning(f"Police custom '{name}' impossible à charger : {e}")

EMOJI_FONT_PATHS = [
    "/usr/share/fonts/NotoEmoji-Regular.ttf",
    "/usr/share/fonts/noto/NotoEmoji-Regular.ttf",
    "/usr/share/fonts/noto-emoji/NotoEmoji-Regular.ttf",
]

_emoji_font_cache = {}

def _get_emoji_font(size: int):
    if size in _emoji_font_cache:
        return _emoji_font_cache[size]
    for path in EMOJI_FONT_PATHS:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _emoji_font_cache[size] = f
                return f
            except Exception:
                pass
    _emoji_font_cache[size] = None
    return None

def _is_emoji(code: int) -> bool:
    return (
        0x1F300 <= code <= 0x1FAFF or
        0x2600  <= code <= 0x27BF  or
        0x1F000 <= code <= 0x1F02F or
        0x1F0A0 <= code <= 0x1F0FF or
        0x2300  <= code <= 0x23FF  or
        0x2B00  <= code <= 0x2BFF
    )

def load_font(size: int, bold: bool = False, font_name: str = None) -> ImageFont.FreeTypeFont:
    name = font_name if font_name else FONT_NAME
    # 1. Chercher dans les polices custom
    if name in CUSTOM_FONT_CACHE:
        try:
            return ImageFont.truetype(CUSTOM_FONT_CACHE[name], size)
        except Exception:
            pass
    # 2. Chercher dans les polices système
    font_map = FONT_MAP_BOLD if bold else FONT_MAP
    path = font_map.get(name)
    # 3. Fallback vers police globale puis DejaVu
    if not path or not os.path.exists(path):
        path = font_map.get(FONT_NAME)
    if not path or not os.path.exists(path):
        path = font_map.get("DejaVu")
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    log.warning(f"Police '{name}' introuvable, fallback PIL.")
    return ImageFont.load_default()

def line_height(font) -> int:
    dummy = Image.new("L", (PRINT_WIDTH, 10))
    draw  = ImageDraw.Draw(dummy)
    return draw.textbbox((0, 0), "Ay", font=font)[3] + 4

def measure_text(text: str, font, size: int) -> int:
    emoji_font = _get_emoji_font(size)
    dummy = Image.new("L", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    total = 0
    for char in text:
        f    = emoji_font if (_is_emoji(ord(char)) and emoji_font) else font
        bbox = draw.textbbox((0, 0), char, font=f)
        total += bbox[2] - bbox[0]
    return total

def draw_text_with_emoji(draw, pos, text: str, font, size: int, fill=0):
    emoji_font = _get_emoji_font(size)
    x, y = pos
    for char in text:
        f = emoji_font if (_is_emoji(ord(char)) and emoji_font) else font
        try:
            draw.text((x, y), char, font=f, fill=fill)
        except Exception:
            draw.text((x, y), char, font=font, fill=fill)
            f = font
        bbox = draw.textbbox((0, 0), char, font=f)
        x += bbox[2] - bbox[0]
    return x

print_lock   = threading.Lock()
printer_busy = False

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

def render_separator(block: dict) -> Image.Image:
    style  = block.get("style", "line")
    height = 12
    img  = Image.new("L", (PRINT_WIDTH, height), color=255)
    draw = ImageDraw.Draw(img)
    y = height // 2
    if style == "dotted":
        for x in range(10, PRINT_WIDTH - 10, 6):
            draw.point((x, y), fill=0)
    elif style != "blank":
        draw.line([(10, y), (PRINT_WIDTH - 10, y)], fill=180, width=1)
    return img

def render_text(block: dict) -> Image.Image:
    text      = str(block.get("text", "")).strip()
    font_size = int(block.get("font_size", FONT_SIZE))
    bold      = bool(block.get("bold", False))
    align     = block.get("align", "left")
    padding   = int(block.get("padding", 4))
    font_name = block.get("font", None)
    font = load_font(font_size, bold, font_name)
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
        w = measure_text(line, font, font_size)
        if align == "center":
            x = max(0, (PRINT_WIDTH - w) // 2)
        elif align == "right":
            x = max(0, PRINT_WIDTH - w - 8)
        else:
            x = 8
        draw_text_with_emoji(draw, (x, y), line, font, font_size, fill=0)
        y += lh
    return img

def render_title(block: dict) -> Image.Image:
    return render_text({**block, "bold": True, "font_size": int(block.get("font_size", FONT_SIZE + 6)), "align": block.get("align", "center"), "padding": 6})

def render_list(block: dict) -> Image.Image:
    items     = block.get("items", [])
    font_size = int(block.get("font_size", FONT_SIZE))
    bold      = bool(block.get("bold", False))
    bullet    = block.get("bullet", "•")
    padding   = 4
    font_name = block.get("font", None)
    font = load_font(font_size, bold, font_name)
    lh   = line_height(font)
    max_chars = max(10, int((PRINT_WIDTH - 24) / (font_size * 0.58)))
    rendered_lines = []
    for item in items:
        text    = str(item).strip()
        wrapped = textwrap.fill(text, width=max_chars)
        sub     = wrapped.split("\n")
        rendered_lines.append((sub[0], True))
        for continuation in sub[1:]:
            rendered_lines.append((continuation, False))
    total_h = lh * len(rendered_lines) + padding * 2
    img  = Image.new("L", (PRINT_WIDTH, total_h), color=255)
    draw = ImageDraw.Draw(img)
    y = padding
    for line, is_first in rendered_lines:
        if is_first:
            draw_text_with_emoji(draw, (8, y), bullet, font, font_size, fill=0)
            draw_text_with_emoji(draw, (8 + font_size, y), line, font, font_size, fill=0)
        else:
            draw_text_with_emoji(draw, (8 + font_size, y), line, font, font_size, fill=0)
        y += lh
    return img

def render_image_url(block: dict) -> Image.Image:
    url = block.get("url", "").strip()
    if not url:
        raise ValueError("Bloc image_url : champ 'url' manquant")
    req = urllib.request.Request(url, headers={"User-Agent": "PeriPage-Layout-Addon/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    return _fit_image(Image.open(io.BytesIO(data)).convert("L"))

def render_image_b64(block: dict) -> Image.Image:
    b64 = block.get("image", "").strip()
    if not b64:
        raise ValueError("Bloc image_b64 : champ 'image' manquant")
    return _fit_image(Image.open(io.BytesIO(base64.b64decode(b64))).convert("L"))

def _fit_image(img: Image.Image) -> Image.Image:
    w, h  = img.size
    new_h = int(h * PRINT_WIDTH / w)
    return img.resize((PRINT_WIDTH, new_h), Image.LANCZOS)

BLOCK_RENDERERS = {
    "text": render_text, "title": render_title, "list": render_list,
    "separator": render_separator, "image_url": render_image_url, "image_b64": render_image_b64,
}

def compose_page(blocks: list) -> tuple:
    images, warnings = [], []
    for i, block in enumerate(blocks):
        block_type = block.get("type", "")
        renderer   = BLOCK_RENDERERS.get(block_type)
        if not renderer:
            warnings.append(f"Bloc #{i} : type inconnu '{block_type}', ignoré")
            continue
        try:
            images.append(renderer(block))
        except Exception as e:
            warnings.append(f"Bloc #{i} ({block_type}) : erreur de rendu — {e}")
            log.warning(f"Bloc #{i} ({block_type}) ignoré : {e}")
    if not images:
        return None, warnings
    images.append(Image.new("L", (PRINT_WIDTH, 40), color=255))
    total_h = sum(img.height for img in images)
    page    = Image.new("L", (PRINT_WIDTH, total_h), color=255)
    y = 0
    for img in images:
        page.paste(img, (0, y))
        y += img.height
    return page, warnings

MODEL_MAP = {
    "A6":  pp.PrinterType.A6,
    "A6p": pp.PrinterType.A6p,
    "A40": pp.PrinterType.A40,
    "A40p": pp.PrinterType.A40p,
}

def _classify_error(error_str: str) -> str:
    """Retourne un message clair selon le type d'erreur Bluetooth."""
    e = error_str.lower()
    if "host is down" in e or "112" in e:
        return "Imprimante éteinte ou hors de portée Bluetooth"
    if "timeout" in e:
        return "Timeout — imprimante éteinte, hors de portée ou occupée par une autre connexion"
    if "busy" in e or "resource" in e or "16" in e:
        return "Imprimante occupée — peut-être connectée à l'application mobile"
    if "connection refused" in e or "111" in e:
        return "Connexion refusée par l'imprimante"
    if "no such device" in e or "19" in e:
        return "Imprimante introuvable — vérifiez l'adresse MAC"
    return f"Erreur Bluetooth : {error_str}"

def _attempt_print(image: Image.Image) -> dict:
    """Une tentative d'impression. Retourne success + error."""
    result = {"success": False, "error": None}
    def _thread():
        try:
            printer_type = MODEL_MAP.get(PRINTER_MODEL, pp.PrinterType.A6)
            printer = pp.Printer(PRINTER_MAC, printer_type)
            printer.connect()
            log.info(f"Connecte, envoi image {image.size}...")
            img_rgb = image.convert("RGB")
            printer.printImage(img_rgb)
            printer.printBreak(100)
            printer.disconnect()
            result["success"] = True
            log.info("Impression transmise avec succes.")
        except Exception as e:
            result["error"] = str(e)
    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    t.join(timeout=30)
    if t.is_alive():
        result["error"] = "timeout"
    return result

def _do_print(image: Image.Image) -> dict:
    """Tente l'impression jusqu'a 2 fois. Notifie HA en cas d'echec."""
    max_attempts = 2
    last_error = None
    for attempt in range(1, max_attempts + 1):
        log.info(f"Tentative {attempt}/{max_attempts}...")
        result = _attempt_print(image)
        if result["success"]:
            return result
        last_error = _classify_error(result["error"] or "inconnue")
        log.warning(f"Tentative {attempt} echouee : {last_error}")
        if attempt < max_attempts:
            log.info("Nouvelle tentative dans 5 secondes...")
            time.sleep(5)
    # Toutes les tentatives ont échoué
    log.error(f"Echec apres {max_attempts} tentatives : {last_error}")
    fire_ha_notification(last_error)
    return {"success": False, "error": last_error}

def fire_ha_notification(error_msg: str):
    """Envoie une notification persistante dans HA."""
    try:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return
        payload = json.dumps({
            "message": f"Impossible de se connecter à l'imprimante.\n{error_msg}",
            "title": "PeriPage — Erreur d'impression",
            "notification_id": "peripage_print_error"
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://supervisor/core/api/services/persistent_notification/create",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        log.info("Notification HA envoyee.")
    except Exception as e:
        log.warning(f"Impossible d'envoyer la notification HA : {e}")

def get_todo_items(entity_id: str) -> tuple:
    """Recupere les items non completes d une liste Todo via l API HA."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return [], "SUPERVISOR_TOKEN absent"
    try:
        req = urllib.request.Request(
            f"http://supervisor/core/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            state = json.loads(resp.read())
        items = []
        for item in state.get("attributes", {}).get("items", []):
            if item.get("status") != "completed":
                summary = item.get("summary", "").strip()
                if summary:
                    items.append(summary)
        return items, None
    except Exception as e:
        return [], f"Erreur API HA : {e}"


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
        try: print_lock.release()
        except RuntimeError: pass

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

class LayoutHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(fmt % args)

    def do_GET(self):
        if self.path == "/health":
            ok = validate_mac(PRINTER_MAC)
            _send(self, 200 if ok else 503, {"status": "ok" if ok else "error", "mac": PRINTER_MAC, "model": PRINTER_MODEL, "font": FONT_NAME, "font_size": FONT_SIZE, "port": PORT, "supported_blocks": list(BLOCK_RENDERERS.keys()), "endpoints": ["/print", "/print_todo", "/health", "/status"]})
        elif self.path == "/status":
            _send(self, 200, {"busy": printer_busy, "mac": PRINTER_MAC})
        else:
            _send(self, 404, {"error": "Route inconnue"})

    def do_POST(self):
        if self.path == "/print":
            data, err = _read_json(self)
            if err:
                return _send(self, 400, {"error": err})
            blocks = data.get("blocks", [])
            if not isinstance(blocks, list) or len(blocks) == 0:
                return _send(self, 400, {"error": "Champ 'blocks' manquant ou vide"})
            page, warnings = compose_page(blocks)
            if page is None:
                return _send(self, 422, {"error": "Aucun bloc n'a pu être rendu", "warnings": warnings})
            ok, error = send_to_printer(page)
            if not ok:
                return _send(self, 503 if "occupée" in str(error) else 500, {"error": error, "warnings": warnings})
            _send(self, 200, {"status": "printed", "blocks_rendered": len(blocks) - len(warnings), "warnings": warnings})

        elif self.path == "/print_todo":
            data, err = _read_json(self)
            if err:
                return _send(self, 400, {"error": err})
            entity_id = data.get("entity_id", "").strip()
            title     = data.get("title", "Ma liste")
            if not entity_id:
                return _send(self, 400, {"error": "Champ 'entity_id' manquant"})
            items, err = get_todo_items(entity_id)
            if err:
                return _send(self, 500, {"error": err})
            if not items:
                items = ["Aucun élément dans cette liste."]
            blocks = [
                {"type": "title",     "text": title, "align": "center"},
                {"type": "separator"},
                {"type": "text",      "text": f"{len(items)} élément(s)", "align": "center", "font_size": 20},
                {"type": "separator"},
                {"type": "list",      "items": items},
            ]
            page, warnings = compose_page(blocks)
            if page is None:
                return _send(self, 422, {"error": "Impossible de composer la page", "warnings": warnings})
            ok, error = send_to_printer(page)
            if not ok:
                return _send(self, 503 if "occupée" in str(error) else 500, {"error": error, "warnings": warnings})
            _send(self, 200, {"status": "printed", "items_count": len(items), "warnings": warnings})

        else:
            _send(self, 404, {"error": "Route inconnue"})

def main():
    if not validate_mac(PRINTER_MAC):
        log.error(f"Adresse MAC invalide ou placeholder : '{PRINTER_MAC}'")
        sys.exit(1)

    log.info(f"PeriPage Layout Addon démarré — port {PORT}")
    log.info(f"Imprimante : {PRINTER_MODEL} @ {PRINTER_MAC}")
    load_custom_fonts()
    log.info(f"Police par défaut : {FONT_NAME} {FONT_SIZE}px")
    # Avertir si une police système est absente
    for name in FONT_MAP:
        if not os.path.exists(FONT_MAP[name]) and not os.path.exists(FONT_MAP_BOLD.get(name, "")):
            log.warning(f"Police '{name}' absente du système")
    if not any(os.path.exists(p) for p in EMOJI_FONT_PATHS):
        log.warning("Police emoji introuvable — les emojis s'afficheront en carré")

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
