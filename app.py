import io
import os
import time
import textwrap
import requests
from datetime import datetime
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
CORS(app)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

GITHUB_REPO  = "LorenzStephan/kioti-image-api"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

DAYS   = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag']
MONTHS = ['Januar','Februar','Maerz','April','Mai','Juni',
          'Juli','August','September','Oktober','November','Dezember']

MARKETING = [
    "Kioti Traktoren liefern erstklassige Qualitaet zu einem Preis, der dich nicht arm macht.",
    "Zuverlaessig. Kraftvoll. Erschwinglich. Das ist Kioti.",
    "Mehr Leistung. Weniger Kosten. 7 Jahre Garantie inklusive.",
    "Der smarte Einstieg in die professionelle Landtechnik.",
    "Qualitaet, die haelt. Garantie, die ueberzeugt. Preis, der begeistert.",
    "Stark im Feld. Stark im Preis. Stark in der Garantie.",
    "7 Jahre Sorglos-Garantie. Weil wir an unsere Traktoren glauben.",
]

MODEL_DB = {
    'CS2220':  {'series': 'CS SERIE', 'ps': '22 PS', 'display': 'CS2220'},
    'CS2520H': {'series': 'CS SERIE', 'ps': '25 PS', 'display': 'CS2520H'},
    'CS2520':  {'series': 'CS SERIE', 'ps': '25 PS', 'display': 'CS2520'},
    'CS2530':  {'series': 'CS SERIE', 'ps': '25 PS', 'display': 'CS2530CH'},
    'CK3530':  {'series': 'CK SERIE', 'ps': '35 PS', 'display': 'CK3530CH'},
    'CK4030':  {'series': 'CK SERIE', 'ps': '40 PS', 'display': 'CK4030'},
    'CK5030H': {'series': 'CK SERIE', 'ps': '50 PS', 'display': 'CK5030H'},
    'CK5030':  {'series': 'CK SERIE', 'ps': '50 PS', 'display': 'CK5030'},
    'K92410':  {'series': 'K9 SERIE', 'ps': '24 PS', 'display': 'K92410'},
    'K9':      {'series': 'K9 SERIE', 'ps': '24 PS', 'display': 'K92410'},
    'HX1402':  {'series': 'HX SERIE', 'ps': '140 PS', 'display': 'HX1402ATC'},
}

# ─── IMAGE LIST CACHE (1 Stunde) ─────────────────────────────────────────────

_cache = {'images': [], 'ts': 0}

def get_github_images():
    global _cache
    if time.time() - _cache['ts'] < 3600 and _cache['images']:
        return _cache['images']

    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    try:
        r = requests.get(GITHUB_API, headers=headers, timeout=10)
        r.raise_for_status()
        files = [f for f in r.json()
                 if isinstance(f, dict) and f.get('name', '').lower().endswith('.jpg')]
        if files:
            _cache = {'images': files, 'ts': time.time()}
            return files
    except Exception:
        pass

    # Fallback: Hard-coded Dateinamen wenn GitHub API nicht erreichbar
    raw_base = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
    fallback_names = [
        "1_Kioti_CS2220_CS2520H - Kopie.jpg",
        "48_Kioti_K92410_K92410C.jpg",
        "CK4030_P1076647.jpg",
        "CK4030_P1076665.jpg",
        "CK4030_P1076822.jpg",
        "CK5030H_P1075333.jpg",
        "CK5030_P1076911.jpg",
        "CK5030_P1076925.jpg",
        "CK_3530CH_FL_Oct_23 (1 von 25).jpg",
        "CS2220_P1073567.jpg",
        "CS2220_P1075471.jpg",
        "CS2520_P1073682.jpg",
        "CS2530CH_Kioti_025.jpg",
        "CS2530CH_Kioti_026.jpg",
        "CS2530CH_Kioti_027.jpg",
        "CS2530CH_Kioti_073.jpg",
        "CS2530CH_Kioti_078.jpg",
        "K9_2410C_01_Jagd_IMC07434.jpg",
        "KIOTI_HX1402ATC-EU_MediaWeek-.jpg",
    ]
    files = [{'name': n,
              'download_url': f"{raw_base}/{requests.utils.quote(n)}"}
             for n in fallback_names]
    _cache = {'images': files, 'ts': time.time()}
    return files

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def js_weekday():
    return (datetime.now().weekday() + 1) % 7

def extract_model(filename):
    name = filename.upper()
    for code in sorted(MODEL_DB, key=len, reverse=True):
        if code in name:
            return MODEL_DB[code]
    return {'series': 'KIOTI', 'ps': '', 'display': 'KIOTI'}

def build_context():
    now    = datetime.now()
    wd     = js_weekday()
    doy    = now.timetuple().tm_yday
    images = get_github_images()
    chosen = images[doy % len(images)] if images else None
    return {
        'day':       DAYS[wd],
        'date':      f"{now.day}. {MONTHS[now.month - 1]} {now.year}",
        'model':     extract_model(chosen['name'] if chosen else ''),
        'marketing': MARKETING[wd % len(MARKETING)],
        'image':     chosen,
    }

def load_font(size, bold=False):
    suffix = '-Bold' if bold else '-Regular'
    for path in [
        f'/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf',
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf',
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ─── IMAGE COMPOSER ──────────────────────────────────────────────────────────

def compose(ctx) -> Image.Image:
    TW, TH = 1080, 1920
    RED   = (220, 30,  30)
    WHITE = (255, 255, 255)
    LGRAY = (200, 200, 200)
    DGRAY = (140, 140, 140)

    # 1. Hintergrundbild von GitHub laden
    if ctx['image']:
        try:
            r = requests.get(ctx['image']['download_url'], timeout=20)
            r.raise_for_status()
            bg = Image.open(io.BytesIO(r.content)).convert('RGB')
        except Exception:
            bg = Image.new('RGB', (TW, TH), (15, 15, 15))
    else:
        bg = Image.new('RGB', (TW, TH), (15, 15, 15))

    # 2. Auf 9:16 Portrait zuschneiden
    if bg.width / bg.height > TW / TH:
        nw = int(bg.height * TW / TH)
        bg = bg.crop(((bg.width - nw) // 2, 0,
                      (bg.width - nw) // 2 + nw, bg.height))
    else:
        nh = int(bg.width * TH / TW)
        bg = bg.crop((0, 0, bg.width, nh))
    bg = bg.resize((TW, TH), Image.LANCZOS)

    # 3. Dunkler Gradient unten + oben
    ov  = Image.new('RGBA', (TW, TH), (0, 0, 0, 0))
    dov = ImageDraw.Draw(ov)
    s = int(TH * 0.32)
    for y in range(TH - s):
        a = int(220 * (y / (TH - s)) ** 1.15)
        dov.line([(0, s + y), (TW, s + y)], fill=(0, 0, 0, min(a, 220)))
    for y in range(180):
        a = int(120 * (1 - y / 180))
        dov.line([(0, y), (TW, y)], fill=(0, 0, 0, a))

    canvas = Image.alpha_composite(bg.convert('RGBA'), ov).convert('RGB')
    d = ImageDraw.Draw(canvas)

    # 4. Fonts
    f_logo   = load_font(100, bold=True)
    f_series = load_font(48)
    f_model  = load_font(130, bold=True)
    f_body   = load_font(50,  bold=True)
    f_cta    = load_font(62,  bold=True)
    f_small  = load_font(40)
    f_btn    = load_font(52,  bold=True)
    f_date   = load_font(36)

    PAD   = 80
    model = ctx['model']

    # 5. KIOTI Logo oben links
    d.text((PAD, 70), "KIOTI", fill=RED, font=f_logo)

    # 6. Textblock unten
    base_y = TH - 760

    d.text((PAD, base_y),
           f"{model['series']}  •  {model['ps']}", fill=LGRAY, font=f_series)
    d.text((PAD, base_y + 58), model['display'], fill=WHITE, font=f_model)

    wrapped = textwrap.fill(ctx['marketing'], width=26)
    d.text((PAD, base_y + 225), wrapped, fill=WHITE, font=f_body)

    cta_y = base_y + 465
    d.text((PAD, cta_y), "Meld dich jetzt!", fill=RED, font=f_cta)
    d.text((PAD, cta_y + 82),
           "7 Jahre Garantie auf den Antriebsstrang.", fill=DGRAY, font=f_small)

    # Roter Button
    btn_y = cta_y + 148
    bw, bh = 500, 82
    d.rounded_rectangle([(PAD, btn_y), (PAD + bw, btn_y + bh)],
                         radius=10, fill=RED)
    bb  = d.textbbox((0, 0), "Meld dich jetzt!", font=f_btn)
    tw  = bb[2] - bb[0]
    tbh = bb[3] - bb[1]
    d.text((PAD + (bw - tw) // 2, btn_y + (bh - tbh) // 2),
           "Meld dich jetzt!", fill=WHITE, font=f_btn)

    # Datum unten
    d.text((PAD, TH - 50),
           f"{ctx['day']}, {ctx['date']}", fill=DGRAY, font=f_date)

    return canvas

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'Kioti Daily Image API'})


@app.route('/daily')
def daily():
    ctx = build_context()
    m   = ctx['model']
    text = (
        f"Guten Morgen! \U0001f305\n\n"
        f"{ctx['day']}, {ctx['date']}\n\n"
        f"\U0001f69c {m['display']} \u2013 {m['series']} {m['ps']}\n\n"
        f"{ctx['marketing']}\n\n"
        f"\u2705 Meld dich jetzt!\n"
        f"7 Jahre Garantie auf den Antriebsstrang."
    )
    return jsonify({
        'day':       ctx['day'],
        'date':      ctx['date'],
        'model':     m['display'],
        'series':    m['series'],
        'ps':        m['ps'],
        'marketing': ctx['marketing'],
        'text':      text,
        'quote':     text,        # ← Make.com Outlook "content" Feld
        'photo_url': ctx['image']['download_url'] if ctx['image'] else '',  # ← NEU: Querformat-Original für E-Mail
    })


@app.route('/image')
def image():
    ctx = build_context()
    img = compose(ctx)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=92, optimize=True)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg',
                     download_name='kioti_daily.jpg')


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
