# Kioti Image API

Automatischer WhatsApp-Post-Generator für KIOTI Traktoren.

## Setup auf Render.com

1. GitHub Account erstellen (github.com)
2. Neues Repository erstellen: "kioti-image-api"
3. Alle Dateien hochladen (app.py, requirements.txt, render.yaml, Procfile, logo.png, badge.png)
4. Render.com Account erstellen (render.com)
5. "New Web Service" → GitHub Repository verbinden
6. Environment Variable setzen: ANTHROPIC_API_KEY = dein Key
7. Deploy klicken

## API Endpunkte

### Health Check
GET /health

### Bild generieren (mit Foto-URL)
POST /generate-with-text
Body (JSON):
{
  "photo_url": "https://...",
  "model": "HX1403"
}

### Bild generieren (mit Foto-Upload)
POST /generate
Body (multipart):
  - photo: Bilddatei
  - text: (optional) eigener Text
  - model: (optional) Modellname

## Make.com Workflow

1. Schedule: täglich 07:45 Uhr
2. OneDrive: zufälliges Foto aus "Kioti-Fotos" Ordner holen
3. HTTP POST an /generate-with-text mit photo_url
4. E-Mail senden mit Bild als Anhang
