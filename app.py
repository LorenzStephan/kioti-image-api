from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
import requests
import io
import os
import base64
import random
from datetime import datetime

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
W, H = 1080, 1920
KIOTI_RED = (210, 35, 15)

PROMPTS = [
    "Schreibe einen WhatsApp-Post im Dirk-Kreuter-Stil für Kioti Traktoren. Zielgruppe: Landwirte in Deutschland. Max. 2 kurze Sätze. Direkt, provokant, ein Emoji, CTA: 'Meld dich jetzt!' Nur den Post.",
    "Schreibe einen WhatsApp-Post im Dirk-Kreuter-Stil für Kioti Traktoren. Zielgruppe: Lohnunternehmer. Max. 2 kurze Sätze. Thema: Zuverlässigkeit & keine Ausfallzeiten. Ein Emoji, CTA: 'Meld dich jetzt!' Nur den Post.",
    "Schreibe einen WhatsApp-Post im Dirk-Kreuter-Stil für Kioti Traktoren. Thema: 7 Jahre Garantie als Kaufargument. Max. 2 kurze Sätze. Provokant, ein Emoji, CTA: 'Meld dich jetzt!' Nur den Post.",
    "Schreibe einen WhatsApp-Post im Dirk-Kreuter-Stil für Kioti Traktoren. Thema: Faire Preise vs. andere Marken. Max. 2 kurze Sätze. Direkt, kein Weichspüler, ein Emoji, CTA: 'Meld dich jetzt!' Nur den Post.",
    "Schreibe einen WhatsApp-Post im Dirk-Kreuter-Stil für Kioti Traktoren. Thema: Sofortige Verfügbarkeit. Max. 2 kurze Sätze. Dringlichkeit, ein Emoji, CTA: 'Meld dich jetzt!' Nur den Post.",
]

def fnt(size, bold=True):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def get_claude_text(prompt):
    """Call Claude API to generate post text"""
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 120,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = res.json()
        return data["content"][0]["text"].strip()
    except Exception as e:
        return f"🚜 Kioti HX1403 – robust, zuverlässig, sofort verfügbar. Meld dich jetzt!"

def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width"""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0,0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines

def shadow_text(draw, x, y, text, font, col, alpha=255):
    r, g, b = col
    for ox, oy in [(4,4),(3,3),(2,2)]:
        draw.text((x+ox, y+oy), text, font=font, fill=(0,0,0,min(210,alpha)))
    draw.text((x,y), text, font=font, fill=(r,g,b,alpha))

def generate_image(photo_bytes, text, model_name="HX1403"):
    """Generate the WhatsApp post image"""

    # Load & crop photo to 9:16
    img = Image.open(io.BytesIO(photo_bytes))

    # Auto-rotate based on EXIF if needed
    try:
        from PIL import ExifTags
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    if val == 3: img = img.rotate(180, expand=True)
                    elif val == 6: img = img.rotate(-90, expand=True)
                    elif val == 8: img = img.rotate(90, expand=True)
    except:
        pass

    ow, oh = img.size
    tr = W / H
    ir = ow / oh
    if ir > tr:
        nw = int(oh * tr); x0 = (ow - nw) // 2
        img = img.crop((x0, 0, x0+nw, oh))
    else:
        nh = int(ow / tr); y0 = (oh - nh) // 2
        img = img.crop((0, y0, ow, y0+nh))

    img = img.resize((W, H), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Color(img).enhance(1.3)
    img = img.convert('RGBA')

    # Gradient overlay
    grad = Image.new('RGBA', (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grad)
    for i in range(H):
        if i < 350:
            a = int(190 * (350-i) / 350)
        elif i > int(H * 0.35):
            a = int(245 * (i - H*0.35) / (H*0.65))
        else:
            a = 0
        gd.line([(0,i),(W,i)], fill=(0,0,0,a))
    img = Image.alpha_composite(img, grad)

    # Load logo
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    logo_raw = Image.open(logo_path).convert('RGBA')
    data = np.array(logo_raw)
    black = (data[:,:,0]<40) & (data[:,:,1]<40) & (data[:,:,2]<40)
    data[:,:,3] = np.where(black, 0, 255)
    logo = Image.fromarray(data)
    lw = 320; lh = int(lw * logo.height / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.paste(logo, (55, 45), logo)

    # Load badge
    badge_path = os.path.join(os.path.dirname(__file__), "badge.png")
    badge = Image.open(badge_path).convert('RGBA')
    bw = 210; bh = int(bw * badge.height / badge.width)
    badge = badge.resize((bw, bh), Image.LANCZOS)
    img.paste(badge, (W-bw-50, 42), badge)

    draw = ImageDraw.Draw(img)

    # Red bars
    draw.rectangle([(0,0),(W,10)], fill=(*KIOTI_RED,255))
    draw.rectangle([(0,H-10),(W,H)], fill=(*KIOTI_RED,255))

    # Fonts
    f_label = fnt(44)
    f_model = fnt(150)
    f_text  = fnt(58)
    f_sub   = fnt(44, bold=False)
    f_cta   = fnt(60)
    f_url   = fnt(38, bold=False)

    Y = H - 860

    # Series label
    shadow_text(draw, 65, Y, "KIOTI  •  HX SERIE", f_label, (170,170,170))
    Y += 68

    # Red line
    draw.rectangle([(65, Y),(270, Y+4)], fill=(*KIOTI_RED,255))
    for gi in range(3,8,2):
        draw.rectangle([(65,Y-gi//2),(270,Y+gi//2)], fill=(*KIOTI_RED, int(60*(1-gi/10))))
    Y += 26

    # Model name
    tmp = Image.new('RGBA', (W,H), (0,0,0,0))
    td = ImageDraw.Draw(tmp)
    shadow_text(td, 50, Y, model_name, f_model, (255,255,255))
    glow = tmp.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    shadow_text(draw, 50, Y, model_name, f_model, (255,255,255))
    Y += 165

    # Post text — wrap to fit
    lines = wrap_text(text, f_text, W - 130, draw)
    for i, line in enumerate(lines[:4]):  # max 4 lines
        col = KIOTI_RED if i == len(lines)-1 else (255,255,255)
        shadow_text(draw, 65, Y, line, f_text, col)
        Y += 72

    Y += 10

    # URL sub line
    shadow_text(draw, 65, Y, "kioti-anfragen.netlify.app", f_url, (180,180,180))
    Y += 62

    # CTA button
    cta = "Meld dich jetzt!"
    bb = draw.textbbox((0,0), cta, font=f_cta)
    bw2 = bb[2]-bb[0]+70; bh2 = 88
    g2 = Image.new('RGBA',(W,H),(0,0,0,0))
    gd2 = ImageDraw.Draw(g2)
    gd2.rounded_rectangle([(52,Y-8),(52+bw2+14,Y+bh2+8)], radius=10, fill=(*KIOTI_RED,80))
    g2 = g2.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img, g2)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(58,Y),(58+bw2,Y+bh2)], radius=6, fill=(*KIOTI_RED,255))
    shadow_text(draw, 80, Y+14, cta, f_cta, (255,255,255))

    # Return as JPEG bytes
    buf = io.BytesIO()
    img.convert('RGB').save(buf, "JPEG", quality=92)
    buf.seek(0)
    return buf

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Kioti Image Generator"})

@app.route('/generate', methods=['POST'])
def generate():
    """
    POST /generate
    Body: multipart/form-data
      - photo: image file (JPEG/PNG)
      - text: (optional) custom text
      - model: (optional) model name, default HX1403
    Returns: JPEG image
    """
    try:
        # Get photo
        if 'photo' not in request.files:
            return jsonify({"error": "No photo provided"}), 400

        photo_file = request.files['photo']
        photo_bytes = photo_file.read()

        # Get or generate text
        text = request.form.get('text', '').strip()
        if not text:
            prompt = random.choice(PROMPTS)
            text = get_claude_text(prompt)

        model_name = request.form.get('model', 'HX1403')

        # Generate image
        img_buf = generate_image(photo_bytes, text, model_name)

        return send_file(
            img_buf,
            mimetype='image/jpeg',
            as_attachment=False,
            download_name=f'kioti_post_{datetime.now().strftime("%Y%m%d")}.jpg'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate-with-text', methods=['POST'])
def generate_with_text():
    """
    POST /generate-with-text
    Body: JSON
      - photo_url: URL of photo to download
      - model: (optional) model name
    Returns: JSON with base64 image + generated text
    """
    try:
        data = request.get_json()
        photo_url = data.get('photo_url')
        model_name = data.get('model', 'HX1403')

        # Download photo
        photo_res = requests.get(photo_url, timeout=30)
        photo_bytes = photo_res.content

        # Generate text
        prompt = random.choice(PROMPTS)
        text = get_claude_text(prompt)

        # Generate image
        img_buf = generate_image(photo_bytes, text, model_name)

        # Return as base64 + text
        img_b64 = base64.b64encode(img_buf.read()).decode()

        return jsonify({
            "image_base64": img_b64,
            "text": text,
            "model": model_name,
            "date": datetime.now().strftime("%d.%m.%Y")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
