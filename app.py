import io
import os
import time
import textwrap
import requests
from datetime import datetime
from collections import deque
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont, ImageFilter

app = Flask(__name__)
CORS(app)

GITHUB_REPO  = "LorenzStephan/kioti-image-api"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGO_URL     = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/kioti_logo.png"

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

# ─── CACHES ──────────────────────────────────────────────────────────────────
_img_cache  = {'images': [], 'ts': 0}
_logo_cache = {'logo': None}   # Logo wird einmal geladen + gecacht

# ─── LOGO: Hintergrund entfernen ─────────────────────────────────────────────

def _remove_bg(logo_pil, tolerance=5):
    """Entfernt hellen Hintergrund per Flood-Fill von den Ecken.
       Toleranz 5 → weißer Kojote (251-252) bleibt erhalten, BG (245) wird transparent."""
    result = logo_pil.convert('RGBA').copy()
    rd = result.load()
    w, h = result.size
    BG = 245
    visited = set()
    queue = deque()
    for x in range(w): queue.extend([(x, 0), (x, h-1)])
    for y in range(h): queue.extend([(0, y), (w-1, y)])
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or x < 0 or y < 0 or x >= w or y >= h:
            continue
        visited.add((x, y))
        pr, pg, pb, pa = rd[x, y]
        if abs(pr-BG) <= tolerance and abs(pg-BG) <= tolerance and abs(pb-BG) <= tolerance:
            rd[x, y] = (pr, pg, pb, 0)
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                if (x+dx, y+dy) not in visited:
                    queue.append((x+dx, y+dy))
    return result

def get_logo(target_w=320):
    """Lädt KIOTI-Logo von GitHub, entfernt Hintergrund, cached Ergebnis."""
    if _logo_cache['logo'] is not None:
        return _logo_cache['logo']
    try:
        r = requests.get(LOGO_URL, timeout=10)
        r.raise_for_status()
        raw = Image.open(io.BytesIO(r.content))
        logo = _remove_bg(raw)
        scale = target_w / logo.width
        logo = logo.resize((target_w, int(logo.height * scale)), Image.LANCZOS)
        _logo_cache['logo'] = logo
        return logo
    except Exception:
        return None   # Fallback: Text-Logo weiter unten

# ─── BILDER-LISTE ─────────────────────────────────────────────────────────────

def get_github_images():
    global _img_cache
    if time.time() - _img_cache['ts'] < 3600 and _img_cache['images']:
        return _img_cache['images']
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    try:
        r = requests.get(GITHUB_API, headers=headers, timeout=10)
        r.raise_for_status()
        files = [f for f in r.json()
                 if isinstance(f, dict) and f.get('name','').lower().endswith('.jpg')]
        if files:
            _img_cache = {'images': files, 'ts': time.time()}
            return files
    except Exception:
        pass
    raw_base = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
    fallback = [
        "1_Kioti_CS2220_CS2520H - Kopie.jpg","48_Kioti_K92410_K92410C.jpg",
        "CK4030_P1076647.jpg","CK4030_P1076665.jpg","CK4030_P1076822.jpg",
        "CK5030H_P1075333.jpg","CK5030_P1076911.jpg","CK5030_P1076925.jpg",
        "CK_3530CH_FL_Oct_23 (1 von 25).jpg","CS2220_P1073567.jpg",
        "CS2220_P1075471.jpg","CS2520_P1073682.jpg","CS2530CH_Kioti_025.jpg",
        "CS2530CH_Kioti_026.jpg","CS2530CH_Kioti_027.jpg","CS2530CH_Kioti_073.jpg",
        "CS2530CH_Kioti_078.jpg","K9_2410C_01_Jagd_IMC07434.jpg",
        "KIOTI_HX1402ATC-EU_MediaWeek-.jpg",
    ]
    files = [{'name': n, 'download_url': f"{raw_base}/{requests.utils.quote(n)}"}
             for n in fallback]
    _img_cache = {'images': files, 'ts': time.time()}
    return files

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

    # 1. Traktorfoto laden
    if ctx['image']:
        try:
            r = requests.get(ctx['image']['download_url'], timeout=20)
            r.raise_for_status()
            bg = Image.open(io.BytesIO(r.content)).convert('RGB')
        except Exception:
            bg = Image.new('RGB', (1920, 1080), (15, 15, 15))
    else:
        bg = Image.new('RGB', (1920, 1080), (15, 15, 15))

    # 2. Blur-Hintergrund füllt ganzen 9:16 Frame (kein schwarzes Loch)
    bg_blur = bg.resize((TW, TH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    dark    = Image.new('RGB', (TW, TH), (0, 0, 0))
    canvas  = Image.blend(bg_blur, dark, alpha=0.60)

    # 3. Scharfes Originalfoto (fit-to-width, KEIN Zuschneiden) oben drauf
    scale   = TW / bg.width
    photo_h = int(bg.height * scale)
    photo   = bg.resize((TW, photo_h), Image.LANCZOS)
    canvas.paste(photo, (0, 0))

    # 4. Übergänge: Logo-Bereich + Foto-Unterkante + Textbereich
    ov  = Image.new('RGBA', (TW, TH), (0, 0, 0, 0))
    dov = ImageDraw.Draw(ov)
    for y in range(180):
        a = int(160 * (1 - y / 180))
        dov.line([(0, y), (TW, y)], fill=(0, 0, 0, a))
    for y in range(photo_h - 140, photo_h):
        a = int(230 * ((y - (photo_h - 140)) / 140))
        dov.line([(0, y), (TW, y)], fill=(0, 0, 0, min(a, 230)))
    for y in range(int(TH * 0.6), TH):
        a = int(80 * ((y - int(TH * 0.6)) / (TH * 0.4)))
        dov.line([(0, y), (TW, y)], fill=(0, 0, 0, min(a, 80)))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), ov).convert('RGB')

    # 5. KIOTI-Logo (roter Text + weißer Kojote) oben links
    logo = get_logo(target_w=320)
    if logo:
        canvas_rgba = canvas.convert('RGBA')
        canvas_rgba.paste(logo, (50, 30), mask=logo.split()[3])
        canvas = canvas_rgba.convert('RGB')
    else:
        # Fallback: Text wenn Logo nicht erreichbar
        d_tmp = ImageDraw.Draw(canvas)
        d_tmp.text((80, 55), "KIOTI", fill=RED, font=load_font(100, bold=True))

    d = ImageDraw.Draw(canvas)

    # 6. Fonts
    f_series = load_font(48)
    f_model  = load_font(130, bold=True)
    f_body   = load_font(50,  bold=True)
    f_cta    = load_font(62,  bold=True)
    f_small  = load_font(40)
    f_btn    = load_font(52,  bold=True)
    f_date   = load_font(36)

    PAD    = 80
    model  = ctx['model']
    base_y = TH - 760   # ← identisch zu Original-Bild 1

    d.text((PAD, base_y),
           f"{model['series']}  •  {model['ps']}", fill=LGRAY, font=f_series)
    d.text((PAD, base_y + 58), model['display'], fill=WHITE, font=f_model)

    wrapped = textwrap.fill(ctx['marketing'], width=26)
    d.text((PAD, base_y + 225), wrapped, fill=WHITE, font=f_body)

    cta_y = base_y + 465
    d.text((PAD, cta_y), "Meld dich jetzt!", fill=RED, font=f_cta)
    d.text((PAD, cta_y + 82),
           "7 Jahre Garantie auf den Antriebsstrang.", fill=DGRAY, font=f_small)

    btn_y = cta_y + 148
    bw, bh = 500, 82
    d.rounded_rectangle([(PAD, btn_y), (PAD + bw, btn_y + bh)],
                         radius=10, fill=RED)
    bb  = d.textbbox((0, 0), "Meld dich jetzt!", font=f_btn)
    tw  = bb[2] - bb[0]
    tbh = bb[3] - bb[1]
    d.text((PAD + (bw - tw) // 2, btn_y + (bh - tbh) // 2),
           "Meld dich jetzt!", fill=WHITE, font=f_btn)

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
        'day': ctx['day'], 'date': ctx['date'],
        'model': m['display'], 'series': m['series'], 'ps': m['ps'],
        'marketing': ctx['marketing'], 'text': text, 'quote': text,
        'photo_url': ctx['image']['download_url'] if ctx['image'] else '',
    })

@app.route('/image')
def image():
    ctx = build_context()
    img = compose(ctx)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=92, optimize=True)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg', download_name='kioti_daily.jpg')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
