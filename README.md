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

## Messe-Kontakte-App

Mobile-optimierte Web-App zur Erfassung von Kontakten auf Messen (Anrede, Name,
Adresse, Baureihe, Notizen). Läuft im Browser auf jedem Handy/Tablet und lässt
sich per "Zum Startbildschirm hinzufügen" wie eine App installieren (PWA).

Nach dem Speichern erhält der Kontakt automatisch eine Dankes-E-Mail mit ersten
Produktinformationen zur ausgewählten Baureihe.

### Seiten

- `/kontakt` — Eingabeformular (für den Messestand)
- `/kontakte` — Kontaktliste mit Suche + CSV-Export (passwortgeschützt)
- `/kontakte/export.csv` — CSV-Export aller Kontakte

### Nötige Umgebungsvariablen

| Variable | Zweck |
|---|---|
| `FLASK_SECRET_KEY` | Zufälliger String für Sessions/Flash-Messages |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Zugang zur Kontaktliste (`/kontakte`) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Versand der Dankes-Mail |
| `SMTP_USE_SSL` | `true` für Port 465 (SSL), sonst STARTTLS auf z.B. Port 587 |
| `DB_PATH` | Pfad zur SQLite-Datenbank (siehe unten) |

Ohne `ADMIN_PASSWORD` ist `/kontakte` gesperrt (503). Ohne SMTP-Konfiguration
werden Kontakte trotzdem gespeichert, nur die Dankes-Mail schlägt fehl (Status
in der Kontaktliste sichtbar).

### Datenspeicherung (wichtig für Render)

Die Kontakte werden in einer SQLite-Datei gespeichert. Render-Webservices haben
standardmäßig ein **flüchtiges Dateisystem** — bei jedem Deploy/Neustart gehen
lokale Dateien verloren. Für dauerhafte Speicherung:

1. In Render einen **Persistent Disk** anlegen, gemountet z.B. auf `/var/data`
   (siehe `render.yaml`)
2. `DB_PATH=/var/data/contacts.db` setzen

Regelmäßig per CSV-Export (`/kontakte/export.csv`) sichern wird trotzdem empfohlen.
