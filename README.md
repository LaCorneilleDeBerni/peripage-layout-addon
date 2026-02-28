# PeriPage Layout — Home Assistant Addon

Addon Home Assistant pour composer et imprimer des pages structurées sur une imprimante thermique **PeriPage** via Bluetooth.

L'addon reçoit une liste de **blocs de contenu** en JSON, compose la page automatiquement (mise en page, word-wrap, redimensionnement des images) et imprime en une seule connexion Bluetooth.

---

## Installation

1. Dans HA : **Paramètres → Addons → Store → ⋮ → Dépôts**
2. Ajoutez : `https://github.com/LaCorneilleDeBerni/peripage-layout-addon`
3. Installez **PeriPage Layout**
4. Configurez votre adresse MAC et démarrez

> ⚠️ Après toute modification de la configuration, **redémarrez l'addon**.

---

## Trouver l'adresse MAC de votre imprimante

Depuis le terminal SSH de Home Assistant :

```bash
hcitool scan
```

---

## Configuration

| Paramètre | Description | Défaut |
|---|---|---|
| `printer_mac` | Adresse MAC Bluetooth de l'imprimante | `XX:XX:XX:XX:XX:XX` |
| `printer_model` | Modèle : `A6`, `A6p`, `A40`, `A40p` | `A6` |
| `font` | Police par défaut : `DejaVu`, `DejaVuBold`, `Liberation` | `DejaVu` |
| `font_size` | Taille de police par défaut en pixels | `24` |
| `port` | Port HTTP du service | `8766` |
| `custom_fonts` | Polices personnalisées (nom + URL .ttf) | `[]` |

### Polices personnalisées

Vous pouvez charger vos propres polices `.ttf` depuis une URL (ex: votre serveur HA) :

```yaml
custom_fonts:
  - name: "PastelTrunk"
    url: "http://192.168.1.210:8123/local/fonts/PastelTrunk.ttf"
  - name: "BirdsOfParadise"
    url: "http://192.168.1.210:8123/local/fonts/BirdsOfParadise.ttf"
```

Placez vos fichiers `.ttf` dans `/config/www/fonts/` pour les rendre accessibles.

---

## Intégration Home Assistant

Ajoutez dans `/config/configuration.yaml` :

```yaml
rest_command:
  peripage_print:
    url: "http://192.168.1.210:8766/print"
    method: POST
    content_type: "application/json"
    payload: "{{ payload }}"
```

---

## Référence des blocs

### `text` — Texte

```json
{
  "type": "text",
  "text": "Votre texte ici",
  "align": "left",
  "font_size": 24,
  "bold": false,
  "font": "DejaVu"
}
```

| Champ | Valeurs | Défaut |
|---|---|---|
| `text` | string | requis |
| `align` | `left` / `center` / `right` | `left` |
| `font_size` | entier (pixels) | config addon |
| `bold` | `true` / `false` | `false` |
| `font` | nom de police | config addon |

---

### `title` — Titre

```json
{
  "type": "title",
  "text": "Mon titre",
  "align": "center",
  "font": "DejaVuBold"
}
```

Identique à `text` mais bold et taille augmentée par défaut.

---

### `list` — Liste

```json
{
  "type": "list",
  "items": ["Premier élément", "Deuxième élément"],
  "bullet": "•",
  "font_size": 22,
  "font": "DejaVu"
}
```

| Champ | Valeurs | Défaut |
|---|---|---|
| `items` | liste de strings | requis |
| `bullet` | string | `•` |
| `font_size` | entier | config addon |
| `font` | nom de police | config addon |

---

### `separator` — Séparateur

```json
{ "type": "separator", "style": "line" }
```

| Style | Rendu |
|---|---|
| `line` | Ligne horizontale (défaut) |
| `dotted` | Ligne pointillée |
| `blank` | Espace vide |

---

### `image_url` — Image depuis une URL

```json
{
  "type": "image_url",
  "url": "http://192.168.1.210:8123/local/images/photo.png"
}
```

L'image est automatiquement redimensionnée à 384px de large.

---

### `image_b64` — Image en base64

```json
{
  "type": "image_b64",
  "image": "iVBORw0KGgo..."
}
```

---

## Endpoints API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/print` | Compose et imprime une page |
| `GET` | `/health` | Statut de l'addon |
| `GET` | `/status` | Imprimante occupée ou disponible |

---

## Exemple complet — Script HA

> ⚠️ Dans un script HA, le payload JSON doit être sur **une seule ligne**. Le YAML multiligne casse le JSON.

```yaml
- service: rest_command.peripage_print
  data:
    payload: >-
      {"blocks": [{"type": "image_url", "url": "http://192.168.1.210:8123/local/Maurice/Maurice_00001.png"},{"type": "separator"},{"type": "title", "text": "Bonjour !","align": "center","font": "BirdsOfParadise"},{"type": "text","text": "Une chose à la fois.","align": "center"},{"type": "separator"},{"type": "title","text": "Aujourd'hui"},{"type": "list","items": ["09:30 - Médecin","14:00 - Boulot"]},{"type": "separator"},{"type": "text","text": "Tu es la meilleure 💙","align": "center"}]}
```

---

## Test depuis le terminal

```bash
curl -X POST http://192.168.1.210:8766/print \
  -H "Content-Type: application/json" \
  -d '{"blocks": [{"type": "text", "text": "Test !"}]}'

curl http://192.168.1.210:8766/health
curl http://192.168.1.210:8766/status
```

---

## Compatibilité

Testé sur Raspberry Pi 4 (aarch64) avec PeriPage A6.

---

## ⚠️ Disclaimer

Ce projet a été réalisé avec l'aide de [Claude.ai](https://claude.ai). Créé pour aider une personne ayant un TDAH via des routines imprimées sur papier.

Merci à [bitrate16](https://github.com/bitrate16) pour la librairie `peripage-python` et à [Elias Weingärtner](https://github.com/eliasweingaertner) pour le reverse engineering du protocole.

## Licence

GPL-3.0
