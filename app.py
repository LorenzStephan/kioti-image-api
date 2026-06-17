from flask import Flask, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime
import os
import textwrap

app = Flask(__name__)
CORS(app)

DAYS = [
    'Sonntag', 'Montag', 'Dienstag', 'Mittwoch',
    'Donnerstag', 'Freitag', 'Samstag'
]
MONTHS = [
    'Januar', 'Februar', 'Maerz', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
]
QUOTES = [
    'Dein Gebiet. Deine Entscheidung. Dein Erfolg.',
    'Ein Nein heute ist ein Ja morgen - bleib dran.',
    'Jeder Haendler, den du entwickelst, multipliziert deinen Umsatz.',
    'Verkauf beginnt nicht beim Produkt, sondern bei der Beziehung.',
    'Champions arbeiten nicht haerter - sie arbeiten smarter.',
    'Konstanz schlaegt Talent - jeden Tag ein bisschen mehr.',
    'Wer kein Ziel hat, trifft auch keines.',
]

FOCUS_ITEMS = [
    ('Haendlerkontakte',      '3'),
    ('Vorführung / Demo',     '1'),
    ('Neuer Haendlerkontakt', '1'),
]

TERRITORIES = ['BW', 'RLP', 'SL', 'CH']

def js_weekday():
    return (datetime.now().weekday() + 1) % 7

def build_data():
    now = datetime.now()
    wd  = js_weekday()
    return {
        'day':   DAYS[wd],
        'date':  f"{now.day}. {MONTHS[now.month - 1]} {now.year}",
        'quote': QUOTES[wd % len(QUOTES)],
    }

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    suffix = '-Bold' if bold else '-Regular'
    candidates = [
        f'/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf',
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf',
        f'/usr/share/fonts/truetype/freefont/FreeSans{"Bold" if bold else ""}.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def draw_card(data: dict) -> Image.Image:
    W, H = 1080, 1920

    BG     = (2,   4,  9)
    ORANGE = (232, 90, 43)
    WHITE  = (255, 255, 255)
    LGRAY  = (160, 160, 160)
    DGRAY  = (60,  60,  60)
    CARDBG = (14,  20,  40)

    img = Image.new('RGB', (W, H), BG)
    d   = ImageDraw.Draw(img)

    f_xs  = load_font(34)
    f_sm  = load_font(42)
    f_md  = load_font(56)
    f_lg  = load_font(78, bold=True)
    f_xl  = load_font(132, bold=True)
    f_hdr = load_font(96, bold=True)

    PAD = 90

    d.rectangle([(0, 0), (10, H)], fill=ORANGE)

    d.text((PAD, 100), "KIOTI", fill=ORANGE, font=f_hdr)
    d.text((PAD, 215), "TERRITORIAL SALES MANAGER", fill=LGRAY, font=f_xs)
    d.line([(PAD, 295), (W - PAD, 295)], fill=ORANGE, width=4)

    d.text((PAD, 335), data['day'].upper(), fill=ORANGE, font=f_md)
    d.text((PAD, 408), data['date'],        fill=LGRAY,  font=f_sm)

    d.text((PAD, 540), "Heute",     fill=WHITE,  font=f_xl)
    d.text((PAD, 682), "gewinnen.", fill=ORANGE, font=f_xl)
    d.text((PAD, 855), "Jeder Kontakt zaehlt - jede Stunde entscheidet.",
           fill=DGRAY, font=f_sm)

    d.text((PAD, 960), "MEIN GEBIET", fill=DGRAY, font=f_xs)
    bx = PAD
    for badge in TERRITORIES:
        bw = 140
        d.rounded_rectangle(
            [(bx, 1005), (bx + bw, 1068)],
            radius=22, outline=ORANGE, width=3, fill=CARDBG
        )
        bb = d.textbbox((0, 0), badge, font=f_md)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        d.text((bx + (bw - tw) // 2, 1005 + (63 - th) // 2),
               badge, fill=ORANGE, font=f_md)
        bx += 158

    d.line([(PAD, 1118), (W - PAD, 1118)], fill=DGRAY, width=1)
    d.text((PAD, 1142), "TAGESFOKUS", fill=DGRAY, font=f_xs)

    fy = 1205
    for txt, num in FOCUS_ITEMS:
        box_h = 98
        d.rounded_rectangle(
            [(PAD, fy), (W - PAD, fy + box_h)],
            radius=14, fill=CARDBG, outline=DGRAY, width=1
        )
        d.text((PAD + 28, fy + (box_h - 56) // 2), txt,
               fill=WHITE, font=f_md)
        nb = d.textbbox((0, 0), num, font=f_lg)
        nw = nb[2] - nb[0]
        d.text((W - PAD - nw - 24, fy + 8), num, fill=ORANGE, font=f_lg)
        fy += 118

    fy += 48
    d.rectangle([(PAD, fy), (PAD + 6, fy + 130)], fill=ORANGE)
    wrapped_quote = textwrap.fill(data['quote'], width=40)
    d.text((PAD + 26, fy + 8), wrapped_quote, fill=LGRAY, font=f_sm)

    tx, ty = W - 340, fy - 20
    sc = 1.3
    d.ellipse([(tx, ty), (tx+130*sc, ty+130*sc)], outline=ORANGE, width=10)
    d.ellipse([(tx+48*sc, ty+48*sc), (tx+82*sc, ty+82*sc)], fill=ORANGE)
    body_pts = [
        (tx+130*sc, ty+40*sc), (tx+220*sc, ty+40*sc),
        (tx+228*sc, ty+52*sc), (tx+260*sc, ty+52*sc),
        (tx+260*sc, ty+84*sc), (tx+130*sc, ty+84*sc),
    ]
    d.polygon(body_pts, fill=ORANGE)
    d.rounded_rectangle([(tx+132*sc, ty+5*sc), (tx+198*sc, ty+84*sc)], radius=4, fill=ORANGE)
    d.rounded_rectangle([(tx+138*sc, ty+11*sc), (tx+192*sc, ty+46*sc)], radius=3, fill=BG)
    d.rounded_rectangle([(tx+182*sc, ty-4*sc), (tx+192*sc, ty+16*sc)], radius=3, fill=ORANGE)
    fw_cx, fw_cy = tx + 242*sc, ty + 97*sc
    d.ellipse([(fw_cx-22*sc, fw_cy-22*sc), (fw_cx+22*sc, fw_cy+22*sc)], outline=ORANGE, width=8)

    d.line([(0, H - 140), (W, H - 140)], fill=DGRAY, width=1)
    d.text((PAD, H - 120), "TSM Sued & Schweiz", fill=WHITE, font=f_md)
    d.text((PAD, H - 62), "Daedong-Kioti  |  BW  |  RLP  |  SL  |  CH", fill=LGRAY, font=f_sm)

    return img

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'Kioti Daily Image API'})

@app.route('/daily')
def daily():
    return jsonify(build_data())

@app.route('/image')
def image():
    data = build_data()
    img  = draw_card(data)
    buf  = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name='kioti_daily.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
