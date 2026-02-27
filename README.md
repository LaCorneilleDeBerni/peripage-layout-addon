# PeriPage Layout — Home Assistant Addon

Addon Home Assistant pour composer et imprimer des pages structurées sur une imprimante thermique **PeriPage** via Bluetooth.

L'addon reçoit une liste de **blocs de contenu** en JSON, compose la page automatiquement (mise en page, word-wrap, redimensionnement des images) et imprime en une seule connexion Bluetooth.

---

## Installation

1. Dans Home Assistant, allez dans **Settings > Add-ons > Add-on Store**
2. Cliquez sur les **⋮** (menu) > **Repositories**
3. Ajoutez : `https://github.com/LaCorneilleDeBerni/peripage-layout-addon`
4. Installez **PeriPage Layout**
5. Configurez votre adresse MAC et démarrez

---

## Configuration

| Paramètre | Description | Défaut |
|---|---|---|
| `printer_mac` | Adresse MAC Bluetooth de l'imprimante | `XX:XX:XX:XX:XX:XX` |
| `printer_model` | Modèle : `A6`, `A6p`, `A40`, `A40p` | `A6` |
| `font` | Police : `DejaVu`, `DejaVuBold`, `Liberation`, `FreeSans` | `DejaVu` |
| `font_size` | Taille de police par défaut en pixels | `24` |
| `port` | Port HTTP du service | `8766` |

---

## Utilisation

### rest_command (configuration.yaml)

```yaml
rest_command:
  peripage_print:
    url: "http://YOUR_HA_IP:8766/print"
    method: POST
    content_type: "application/json"
    payload: "{{ payload }}"
```

### Appel depuis un script HA

```yaml
- service: rest_command.peripage_print
  data:
    payload: >
      {
        "blocks": [
          { "type": "title", "text": "Bonjour !" },
          { "type": "separator" },
          { "type": "text", "text": "Une chose à la fois.", "align": "center" },
          { "type": "list", "items": ["09:30 - Médecin", "14:00 - Boulot"] }
        ]
      }
```

---

## Référence des blocs

### `text` — Texte simple

```json
{
  "type": "text",
  "text": "Votre texte ici",
  "align": "left",
  "font_size": 24,
  "bold": false
}
```

| Champ | Valeurs | Défaut |
|---|---|---|
| `text` | string | requis |
| `align` | `left` / `center` / `right` | `left` |
| `font_size` | entier (pixels) | config addon |
| `bold` | `true` / `false` | `false` |

---

### `title` — Titre

```json
{
  "type": "title",
  "text": "Mon titre",
  "align": "center"
}
```

Identique à `text` mais bold et taille augmentée par défaut.

---

### `list` — Liste d'éléments

```json
{
  "type": "list",
  "items": ["Premier élément", "Deuxième élément"],
  "bullet": "•",
  "font_size": 22
}
```

| Champ | Valeurs | Défaut |
|---|---|---|
| `items` | liste de strings | requis |
| `bullet` | string | `•` |
| `font_size` | entier | config addon |

---

### `separator` — Séparateur

```json
{ "type": "separator", "style": "line" }
```

| Style | Rendu |
|---|---|
| `line` | Ligne horizontale fine (défaut) |
| `dotted` | Ligne pointillée |
| `blank` | Espace vide |

---

### `image_url` — Image depuis une URL

```json
{
  "type": "image_url",
  "url": "http://192.168.1.10:8123/local/images/photo.png"
}
```

L'image est automatiquement redimensionnée à la largeur d'impression (384px).

---

### `image_b64` — Image encodée en base64

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
| `GET` | `/status` | État de l'imprimante (occupée ou non) |

### Réponse `/print` succès

```json
{
  "status": "printed",
  "blocks_rendered": 5,
  "warnings": []
}
```

### Réponse `/print` erreur

```json
{
  "error": "Imprimante occupée",
  "warnings": []
}
```

---

## Blueprints

Des exemples complets de scripts et automations HA sont disponibles dans le dossier [`blueprints/`](./blueprints/) :

- **`morning_routine.yaml`** — Routine du matin : image aléatoire, phrase d'encouragement, RDV du jour, phrase finale
- **`task_list.yaml`** — Impression d'une liste de tâches

---

## Compatibilité

Testé sur :
- Raspberry Pi 4 (aarch64)
- PeriPage A6

---

## Licence

GPL-3.0
