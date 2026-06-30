import io
import os
import re
import json
import time
import textwrap
import requests
from datetime import datetime
from collections import deque
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont, ImageFile, ImageFilter

ImageFile.LOAD_TRUNCATED_IMAGES = True   # falls ein Stream mal abbricht: trotzdem rendern statt crashen

app = Flask(__name__)
CORS(app)

GITHUB_REPO  = "LorenzStephan/kioti-image-api"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGO_URL     = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/logo.png"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"   # guenstigstes Modell, reicht fuer kurze Marketingtexte

DAYS   = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag']
MONTHS = ['Januar','Februar','Maerz','April','Mai','Juni',
          'Juli','August','September','Oktober','November','Dezember']

# ─── TAGESTHEMEN: liefern der KI nur die RICHTUNG, Text kommt live ──────────
THEME_META = [
    {"name": "Garantie",        "hint": "Verlaesslichkeit und Sicherheit beim Kauf betonen.",
     "fact": "7 Jahre Garantie auf den Antriebsstrang."},
    {"name": "Finanzierung",    "hint": "Leichter Einstieg ueber Rate/Finanzierung, ohne Zahlen zu erfinden."},
    {"name": "Probefahrt",      "hint": "Neugier wecken, zur Probefahrt einladen."},
    {"name": "Saison",          "hint": "Ganzjahres-Einsatz, passend zur aktuellen Jahreszeit."},
    {"name": "Leistung",        "hint": "PS und Leistung fuers Geld hervorheben."},
    {"name": "Service",         "hint": "Regionale Naehe, Beratung, Ersatzteile."},
    {"name": "Komfort",         "hint": "Einfache Bedienung, Komfort, gute Uebersicht."},
    {"name": "Direkter Aufruf", "hint": "Klar und direkt zum Melden einladen, ohne Umschweife."},
]

# Fallback-Texte, falls KI-Aufruf fehlschlaegt oder kein API-Key gesetzt ist.
# "sub" ist hier bewusst der direkte Call-to-Action (einziges CTA-Element im Bild).
THEMES = [
    {"slogan": "Stark. Zuverlaessig. Guenstig.",
     "sub": "Schreib mir - ich erklaer dir die Garantie genau.",
     "cta_titel": "Meld dich jetzt!", "cta_zeile": "7 Jahre Garantie auf den Antriebsstrang."},
    {"slogan": "Dein Traktor. Deine Rate.",
     "sub": "Meld dich, ich rechne dir dein Angebot durch.",
     "cta_titel": "Schreib mir!", "cta_zeile": "Ich rechne dir dein Angebot durch."},
    {"slogan": "Erst fahren. Dann staunen.",
     "sub": "Schreib mir fuer deine unverbindliche Probefahrt.",
     "cta_titel": "Probefahrt sichern!", "cta_zeile": "Eine Nachricht genuegt."},
    {"slogan": "Bereit fuer jede Saison.",
     "sub": "Meld dich, ich zeig dir den passenden Kioti.",
     "cta_titel": "Jetzt informieren!", "cta_zeile": "Der richtige Traktor fuer deinen Einsatz."},
    {"slogan": "Mehr PS. Weniger Kosten.",
     "sub": "Schreib mir, ich zeig dir was drinsteckt.",
     "cta_titel": "Meld dich!", "cta_zeile": "Ich zeig dir, was in deinem Modell steckt."},
    {"slogan": "Service, der nah ist.",
     "sub": "Meld dich - Beratung direkt aus deiner Region.",
     "cta_titel": "Kioti in deiner Naehe.", "cta_zeile": "Qualitaet mit Ruecken-Deckung."},
    {"slogan": "Einsteigen. Loslegen.",
     "sub": "Schreib mir, ich finde den passenden Kioti fuer dich.",
     "cta_titel": "Schreib mir!", "cta_zeile": "Ich finde den passenden Kioti fuer dich."},
    {"slogan": "Dein naechster Traktor wartet.",
     "sub": "Antworte einfach auf diesen Status - ich melde mich.",
     "cta_titel": "Eine Nachricht genuegt!", "cta_zeile": "Antworte auf diesen Status - ich melde mich."},
]

# ─── BAUREIHEN: bekannte bzw. generisch erkannte Serien ─────────────────────
# PS-Angaben aus den offiziellen Kioti-Serienseiten (Stand Recherche 06/2026).
# NX/PX bewusst weggelassen - dafuer fehlt mir eine verifizierte PS-Spanne.
SERIES_INFO = {
    'CS':  {'series': 'CS SERIE', 'ps': '21-26 PS',  'use': 'Garten, Reitplatz, kleine Flaechen'},
    'CX':  {'series': 'CX SERIE', 'ps': '25 PS',     'use': 'Hof, Reitstall, Gewaechshaus, kleine Flaechen'},
    'CK':  {'series': 'CK SERIE', 'ps': '25-50 PS',  'use': 'Vielseitig, Kommune, mittlere Betriebe'},
    'DK':  {'series': 'DK SERIE', 'ps': 'bis 60 PS', 'use': 'Kraftvoll, Kommune, Golfplatz'},
    'RX':  {'series': 'RX SERIE', 'ps': '66-74 PS',  'use': 'Profi-Landwirtschaft, Utility'},
    'HX':  {'series': 'HX SERIE', 'ps': '91-140 PS', 'use': 'Profi-Landwirtschaft, autonome Technik'},
    'K9':  {'series': 'K9 SERIE', 'ps': '24 PS',     'use': 'Kompakt, Hobby, Kommunal'},
    'ZXR': {'series': 'ZXR',      'ps': '',          'use': 'Rasenpflege, Nullwendekreismaeher'},
    'ZXS': {'series': 'ZXS',      'ps': '',          'use': 'Rasenpflege, Nullwendekreismaeher'},
}
# Feinkorrektur fuer konkrete Dateinamen (genaue Anzeige-Bezeichnung/PS)
MODEL_OVERRIDES = {
    'CS2220':  {'ps': '22 PS',  'display': 'CS2220'},
    'CS2520H': {'ps': '25 PS',  'display': 'CS2520H'},
    'CS2520':  {'ps': '25 PS',  'display': 'CS2520'},
    'CS2530':  {'ps': '25 PS',  'display': 'CS2530CH'},
    'CK3530':  {'ps': '35 PS',  'display': 'CK3530CH'},
    'CK4030':  {'ps': '40 PS',  'display': 'CK4030'},
    'CK5030H': {'ps': '50 PS',  'display': 'CK5030H'},
    'CK5030':  {'ps': '50 PS',  'display': 'CK5030'},
    'K92410':  {'ps': '24 PS',  'display': 'K92410'},
    'HX1402':  {'ps': '140 PS', 'display': 'HX1402ATC'},
}
SEP = r'[_\s-]?'   # echte Dateinamen trennen Praefix/Zahl manchmal mit _ oder Leerzeichen
SERIES_PATTERN = re.compile(
    r'(CS' + SEP + r'\d{3,4}[A-Z]*|CX' + SEP + r'\d{3,4}[A-Z]*|CK' + SEP + r'\d{3,4}[A-Z]*'
    r'|DK' + SEP + r'\d{2,4}[A-Z]*|RX' + SEP + r'\d{3,4}[A-Z]*|HX' + SEP + r'\d{3,4}[A-Z]*'
    r'|K9(?:' + SEP + r'\d{3,4}[A-Z]*)?|ZXR\d*|ZXS\d*)'
)

def _prefix_of(code):
    # K9 zuerst pruefen: die '9' ist eine Ziffer, das reine Buchstaben-Regex unten wuerde sie verpassen
    if code.upper().startswith('K9'):
        return 'K9'
    return re.match(r'[A-Z]+', code).group(0)

def _clean_display(code):
    return code.replace('_', '').replace(' ', '').replace('-', '').upper()

def extract_model(filename):
    name = filename.upper()
    for code in sorted(MODEL_OVERRIDES, key=len, reverse=True):
        if code in name:
            ov   = MODEL_OVERRIDES[code]
            base = SERIES_INFO.get(_prefix_of(code), {'series': 'KIOTI', 'use': ''})
            return {'series': base['series'], 'ps': ov['ps'], 'display': ov['display'], 'use': base['use']}
    m = SERIES_PATTERN.search(name)
    if m:
        code = m.group(1)
        info = SERIES_INFO.get(_prefix_of(code))
        if info:
            return {'series': info['series'], 'ps': info['ps'], 'display': _clean_display(code), 'use': info['use']}
    return {'series': 'KIOTI', 'ps': '', 'display': 'KIOTI', 'use': 'Vielseitig im Einsatz'}

# ─── CACHES ──────────────────────────────────────────────────────────────────
_img_cache  = {'images': [], 'ts': 0}
_logo_cache = {'logo': None}
_text_cache = {'date': None, 'theme': None}

# ─── Sicheres Laden externer Inhalte ──────────────────────────────────────────
# Render Free-Tier hat ein hartes 30s Gunicorn-Worker-Limit. Knapper Timeout +
# gestreamtes Lesen mit Obergrenze verhindert, dass ein einzelner langsamer
# Request (v.a. nach Cold-Start) den ganzen Request killt.
def _safe_fetch(url, max_bytes=8_000_000, timeout=(4, 6)):
    with requests.get(url, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        return r.raw.read(max_bytes)

# ─── LOGO: Hintergrund entfernen (Logik unveraendert) ────────────────────────
def _remove_bg(logo_pil, thresh=70):
    """Entfernt SCHWARZEN Hintergrund per Flood-Fill von den Ecken.
       Dunkle Randpixel (R,G,B alle < thresh) werden transparent.
       Roter Schriftzug + weisser Kojote bleiben erhalten, da sie hell sind."""
    result = logo_pil.convert('RGBA').copy()
    rd = result.load()
    w, h = result.size
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
        if pr < thresh and pg < thresh and pb < thresh:
            rd[x, y] = (0, 0, 0, 0)
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                if (x+dx, y+dy) not in visited:
                    queue.append((x+dx, y+dy))
    for yy in range(h):
        for xx in range(w):
            pr, pg, pb, pa = rd[xx, yy]
            if pa != 0 and pr < thresh and pg < thresh and pb < thresh:
                rd[xx, yy] = (0, 0, 0, 0)
    return result

def get_logo(target_w=320):
    if _logo_cache['logo'] is not None:
        return _logo_cache['logo']
    try:
        raw_bytes = _safe_fetch(LOGO_URL, max_bytes=3_000_000)
        raw = Image.open(io.BytesIO(raw_bytes))
        logo = _remove_bg(raw)
        scale = target_w / logo.width
        logo = logo.resize((target_w, int(logo.height * scale)), Image.LANCZOS)
        _logo_cache['logo'] = logo
        return logo
    except Exception:
        return None

# ─── BILDER-LISTE (Logik unveraendert) ────────────────────────────────────────
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

def group_by_series(images):
    groups = {}
    for img in images:
        s = extract_model(img['name'])['series']
        groups.setdefault(s, []).append(img)
    return groups

def js_weekday():
    return (datetime.now().weekday() + 1) % 7

# ─── KI: Tagestext live generieren ────────────────────────────────────────────
SYSTEM_PROMPT = """Du schreibst taegliche Marketingtexte fuer KIOTI-Traktoren (Daedong KIOTI Europe), gerichtet an Landwirte, Pferdehof-Betreiber, Kommunen sowie Garten- und Landschaftsbauer in Deutschland, Oesterreich und der Schweiz.

MARKENSTIMME (strikt einhalten):
- Selbstbewusst, direkt, klar - wie ein verlaesslicher Kumpel, der die Arbeit kennt ("Tough Ally"). Kein Verkaeufer-Ton.
- Kurze, kraftvolle Saetze. Wenige Worte, starke Wirkung. Keine Schachtelsaetze, keine Floskeln, kein Fachjargon.
- Calls-to-Action MOTIVIEREN und UNTERSTUETZEN, sie befehlen nie ("Schreib mir!" statt "Kaufen Sie jetzt!").
- Informelle Anrede ("du", "dein").
- Erfinde NIEMALS Zahlen, Preise oder technische Daten, die dir nicht explizit mitgegeben wurden.

AUSGABE: Antworte AUSSCHLIESSLICH mit einem JSON-Objekt - keine Erklaerung, kein Markdown:
{"slogan": "...", "sub": "...", "cta_titel": "...", "cta_zeile": "..."}

Auf dem Bild selbst erscheinen NUR slogan (grosse weisse Headline) und sub (kleinere
weisse Zeile direkt darunter, kein Kasten, keine Farbe). sub ist hier der einzige
Call-to-Action im Bild - sub MUSS deshalb direkt zum Meld en/Schreiben auffordern,
nicht nur ein Produktmerkmal beschreiben. Beispiel: nicht "Perfekt fuer Garten und
Reitplatz" (das ist nur eine Beschreibung), sondern "Schreib mir - ich finde den
passenden Kioti fuer dich" oder "Jetzt melden, ich beantworte alle Fragen" (das
laedt aktiv zum Kontakt ein). cta_titel/cta_zeile werden zusaetzlich fuer den
Status-Begleittext gebraucht (nicht im Bild) und duerfen das nochmal aufgreifen.

LAENGEN (hart einhalten, sonst laeuft das Bild-Layout ueber):
- slogan: max. 2 kurze Zeilen, insgesamt max. 38 Zeichen
- sub: 1 kurzer Satz, max. 60 Zeichen, MUSS zum Melden/Schreiben auffordern
- cta_titel: max. 18 Zeichen
- cta_zeile: max. 45 Zeichen"""

def generate_daily_theme(model, theme_meta):
    today_str = datetime.now().strftime('%Y-%m-%d')
    if _text_cache['date'] == today_str and _text_cache['theme']:
        return _text_cache['theme']

    doy = datetime.now().timetuple().tm_yday
    fallback = THEMES[doy % len(THEMES)]

    if not ANTHROPIC_API_KEY:
        _text_cache.update({'date': today_str, 'theme': fallback})
        return fallback

    user_msg = (
        f"Tagesthema: {theme_meta['name']} ({theme_meta['hint']})\n"
        f"Modell heute: KIOTI {model['display']} - {model['series']}"
        f"{(' - ' + model['ps']) if model['ps'] else ''}\n"
        f"Einsatzgebiet: {model['use']}\n"
        f"Bekannter Fakt, den du nutzen darfst: {theme_meta.get('fact', '(keiner - nichts erfinden)')}\n\n"
        f"Schreibe jetzt slogan, sub, cta_titel und cta_zeile."
    )
    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=(4, 8),
        )
        r.raise_for_status()
        raw_text = r.json()["content"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        data = json.loads(raw_text)
        for k in ("slogan", "sub", "cta_titel", "cta_zeile"):
            if not data.get(k):
                raise ValueError(f"Feld fehlt: {k}")
        _text_cache.update({'date': today_str, 'theme': data})
        return data
    except Exception:
        _text_cache.update({'date': today_str, 'theme': fallback})
        return fallback

def build_context():
    now    = datetime.now()
    wd     = js_weekday()
    doy    = now.timetuple().tm_yday
    images = get_github_images()
    groups = group_by_series(images)
    series_list = sorted(groups.keys())
    if series_list:
        today_series = series_list[doy % len(series_list)]
        bucket = groups[today_series]
        chosen = bucket[(doy // len(series_list)) % len(bucket)]
    else:
        chosen = images[doy % len(images)] if images else None

    model = extract_model(chosen['name']) if chosen else \
        {'series': 'KIOTI', 'ps': '', 'display': 'KIOTI', 'use': ''}
    theme_meta = THEME_META[doy % len(THEME_META)]
    theme = generate_daily_theme(model, theme_meta)

    return {
        'day':   DAYS[wd],
        'date':  f"{now.day}. {MONTHS[now.month - 1]} {now.year}",
        'model': model,
        'theme': theme,
        'image': chosen,
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
    RED   = (205, 25, 25)
    WHITE = (255, 255, 255)

    if ctx['image']:
        try:
            raw_bytes = _safe_fetch(ctx['image']['download_url'], max_bytes=8_000_000)
            bg = Image.open(io.BytesIO(raw_bytes)).convert('RGB')
        except Exception:
            bg = Image.new('RGB', (1280, 800), (15, 15, 15))
    else:
        bg = Image.new('RGB', (1280, 800), (15, 15, 15))

    # Foto bleibt UNVERAENDERT in Groesse und Seitenverhaeltnis - kein Resize,
    # kein Zuschneiden. Text/Logo werden proportional zur tatsaechlichen
    # Bildgroesse eingepasst, egal welches Format das Foto mitbringt.
    W, H = bg.size
    canvas = bg.copy()

    # Verlauf: oben dezent (Logo-Lesbarkeit), unten kraeftig (Text-Lesbarkeit)
    ov  = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dov = ImageDraw.Draw(ov)
    top_h = max(1, int(H * 0.22))
    for y in range(top_h):
        a = int(85 * (1 - y / top_h))
        dov.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    grad_start = int(H * 0.50)
    for y in range(grad_start, H):
        a = int(205 * ((y - grad_start) / max(1, H - grad_start)))
        dov.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 205)))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), ov).convert('RGB')

    # Logo oben rechts, proportional zur Bildbreite
    pad     = max(20, int(W * 0.045))
    logo_w  = max(90, int(W * 0.26))
    logo = get_logo(target_w=logo_w)
    if logo:
        canvas_rgba = canvas.convert('RGBA')
        lx = W - logo.width - pad
        ly = max(10, int(H * 0.035))
        canvas_rgba.paste(logo, (lx, ly), mask=logo.split()[3])
        canvas = canvas_rgba.convert('RGB')
    else:
        d_tmp = ImageDraw.Draw(canvas)
        d_tmp.text((W - logo_w, pad), "KIOTI", fill=RED, font=load_font(max(18, int(H * 0.07)), bold=True))

    d  = ImageDraw.Draw(canvas)
    th = ctx['theme']

    f_headline = load_font(max(16, int(H * 0.072)), bold=True)
    f_sub      = load_font(max(14, int(H * 0.048)), bold=True)

    wrap_h = max(8, int(W / (f_headline.size * 0.60)))
    wrap_s = max(8, int(W / (f_sub.size * 0.56)))
    headline_lines = textwrap.fill(th['slogan'], width=wrap_h).split('\n')
    sub_lines      = textwrap.fill(th['sub'],    width=wrap_s).split('\n')

    line_h     = int(f_headline.size * 1.18)
    headline_h = len(headline_lines) * line_h

    box_px = int(f_sub.size * 0.55)   # Innenabstand links/rechts
    box_py = int(f_sub.size * 0.42)   # Innenabstand oben/unten
    sub_lh = int(f_sub.size * 1.28)
    box_h  = box_py * 2 + len(sub_lines) * sub_lh
    box_w  = W - 2 * pad               # Kasten zieht von Rand zu Rand (minus Rand-Pad)

    gap     = max(10, int(H * 0.024))
    total_h = headline_h + gap + box_h
    y       = H - max(14, int(H * 0.038)) - total_h

    # Weisse Headline
    for line in headline_lines:
        d.text((pad, y), line, fill=WHITE, font=f_headline)
        y += line_h

    # Roter Kasten mit weißer CTA-Schrift
    box_y = y + gap
    d.rectangle([(pad, box_y), (pad + box_w, box_y + box_h)], fill=RED)
    ty = box_y + box_py
    for line in sub_lines:
        d.text((pad + box_px, ty), line, fill=WHITE, font=f_sub)
        ty += sub_lh

    return canvas

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'Kioti Daily Image API'})

@app.route('/daily')
def daily():
    ctx = build_context()
    m   = ctx['model']
    th  = ctx['theme']
    series_ps = f"{m['series']} {m['ps']}".strip()
    text = (
        f"Guten Morgen! \U0001f305\n\n"
        f"{ctx['day']}, {ctx['date']}\n\n"
        f"\U0001f69c {m['display']} \u2013 {series_ps}\n\n"
        f"{th['slogan']}\n{th['sub']}\n\n"
        f"\u2705 {th['cta_titel']}\n"
        f"{th['cta_zeile']}"
    )
    return jsonify({
        'day': ctx['day'], 'date': ctx['date'],
        'model': m['display'], 'series': m['series'], 'ps': m['ps'],
        'marketing': th['slogan'], 'text': text, 'quote': text,
        'slogan': th['slogan'], 'cta': th['cta_titel'],
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
