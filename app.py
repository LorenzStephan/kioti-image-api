from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
import requests
import re
import urllib.parse
import io
import os
import random
import math
from datetime import datetime

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

GW, GH = 540, 960
W, H = 1080, 1920
KIOTI_RED = (210, 35, 15)

GITHUB_USER = "LorenzStephan"
GITHUB_REPO = "kioti-image-api"

_cached_image = None
_cached_text = None
_cached_filename = None
_cached_mimetype = 'image/gif'

ANIMATION_STYLES = ["slide_left", "slide_bottom", "fade_scale", "typewriter", "bounce"]

PROMPTS = [
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Max. 2 kurze Sätze. Direkt, stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: 7 Jahre Garantie. Max. 2 Sätze. Provokant, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Fairer Preis. Max. 2 Sätze. Direkt, kein Weichspüler, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Sofort verfügbar, keine Wartezeit. Max. 2 Sätze. Dringlichkeit, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Zuverlässigkeit für Lohnunternehmer. Max. 2 Sätze. Stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Weinbau und Obstbau. Max. 2 Sätze. Präzise, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Kommunale Fahrzeuge. Max. 2 Sätze. Sachlich, stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
]

def fnt(size, bold=True, scale=1.0):
    path = FONT_BOLD if bold else FONT_REG
    try: return ImageFont.truetype(path, int(size * scale))
    except: return ImageFont.load_default()

def ease_out(t): return 1 - (1-t)**3
def ease_bounce(t):
    if t < 0.5: return 4*t*t*t
    return 1 - (-2*t+2)**3/2

def get_github_photos():
    try:
        res = requests.get(f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}", timeout=15)
        pattern = r'href="[^"]+/blob/main/([^"]+\.(?:jpg|jpeg|png|webp))"'
        matches = re.findall(pattern, res.text, re.IGNORECASE)
        seen = set()
        images = []
        for m in matches:
            decoded = urllib.parse.unquote(m)
            if decoded not in seen:
                seen.add(decoded)
                images.append(decoded)
        return images
    except Exception as e:
        print(f"GitHub list error: {e}")
        return []

def get_random_github_photo():
    try:
        images = get_github_photos()
        if not images: return None, None
        safe = [f for f in images if " " not in f and "(" not in f]
        chosen = random.choice(safe if safe else images)
        encoded = urllib.parse.quote(chosen)
        res = requests.get(f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{encoded}", timeout=30)
        if res.status_code == 200:
            return res.content, chosen
        return None, None
    except Exception as e:
        print(f"GitHub photo error: {e}")
        return None, None

def get_claude_text(prompt):
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 120, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        return res.json()["content"][0]["text"].strip()
    except:
        return "🚜 Kioti – robust, zuverlässig, fair. Meld dich jetzt!"

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0,0), test, font=font)
        if bbox[2]-bbox[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current: lines.append(" ".join(current))
    return lines

def shadow_text(draw, x, y, text, font, col, alpha=255):
    r, g, b = col
    for ox, oy in [(2,2),(1,1)]:
        draw.text((x+ox, y+oy), text, font=font, fill=(0,0,0,min(200,alpha)))
    draw.text((x,y), text, font=font, fill=(r,g,b,alpha))

def detect_model(filename):
    fn = filename.upper()
    if "HX1403" in fn or "HX140" in fn: return "HX1403", "HX SERIE  •  140 PS"
    if "HX1402" in fn: return "HX1402", "HX SERIE  •  140 PS"
    if "HX1201" in fn or "HX120" in fn: return "HX1201", "HX SERIE  •  120 PS"
    if "CS2530" in fn: return "CS2530CH", "CS SERIE  •  25 PS  •  KABINE"
    if "CS2520" in fn: return "CS2520H", "CS SERIE  •  25 PS"
    if "CS2220" in fn: return "CS2220", "CS SERIE  •  22 PS"
    if "CK4030" in fn: return "CK4030", "CK SERIE  •  40 PS"
    if "CK5030" in fn: return "CK5030", "CK SERIE  •  50 PS"
    if "CK3530" in fn: return "CK3530CH", "CK SERIE  •  35 PS  •  KABINE"
    if "CK2510" in fn or "CK25" in fn: return "CK2510", "CK SERIE  •  25 PS"
    if "CK3510" in fn or "CK35" in fn: return "CK3510", "CK SERIE  •  35 PS"
    if "CX2510" in fn: return "CX2510", "CX SERIE  •  25 PS"
    if "DK5020" in fn: return "DK5020H", "DK SERIE  •  50 PS"
    if "DK6020" in fn: return "DK6020", "DK SERIE  •  60 PS"
    if "DK6030" in fn: return "DK6030", "DK SERIE  •  60 PS"
    if "DK4510" in fn or "DK45" in fn: return "DK4510", "DK SERIE  •  45 PS"
    if "RX6010" in fn or "RX60" in fn: return "RX6010", "RX SERIE  •  60 PS"
    if "RX7320" in fn or "RX73" in fn: return "RX7320", "RX SERIE  •  73 PS"
    if "RX8040" in fn or "RX80" in fn: return "RX8040", "RX SERIE  •  80 PS"
    if "K92410" in fn or "K9_2410" in fn: return "K92410C", "K SERIE  •  92 PS"
    if "ZXS" in fn: return "KIOTI ZXS", "UTILITY VEHICLE"
    return "KIOTI", "KIOTI TRAKTOREN"

def prepare_base(photo_bytes, w, h):
    img = Image.open(io.BytesIO(photo_bytes))
    try:
        from PIL import ExifTags
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    if val == 3: img = img.rotate(180, expand=True)
                    elif val == 6: img = img.rotate(-90, expand=True)
                    elif val == 8: img = img.rotate(90, expand=True)
    except: pass

    ow, oh = img.size
    tr = w/h; ir = ow/oh
    if ir > tr:
        nw=int(oh*tr); x0=(ow-nw)//2; img=img.crop((x0,0,x0+nw,oh))
    else:
        nh=int(ow/tr); y0=(oh-nh)//2; img=img.crop((0,y0,ow,y0+nh))
    img = img.resize((w,h), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Color(img).enhance(1.3)
    img = img.convert('RGBA')

    grad = Image.new('RGBA',(w,h),(0,0,0,0))
    gd = ImageDraw.Draw(grad)
    for i in range(h):
        if i < int(h*0.18): a=int(190*(h*0.18-i)/(h*0.18))
        elif i > int(h*0.35): a=int(245*(i-h*0.35)/(h*0.65))
        else: a=0
        gd.line([(0,i),(w,i)], fill=(0,0,0,a))
    img = Image.alpha_composite(img, grad)

    scale = w/W
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    logo_raw = Image.open(logo_path).convert('RGBA')
    data = np.array(logo_raw)
    black = (data[:,:,0]<40)&(data[:,:,1]<40)&(data[:,:,2]<40)
    data[:,:,3] = np.where(black,0,255)
    logo = Image.fromarray(data)
    lw=int(320*scale); lh=int(lw*logo.height/logo.width)
    logo = logo.resize((lw,lh), Image.LANCZOS)
    img.paste(logo,(int(55*scale),int(45*scale)),logo)

    badge_path = os.path.join(os.path.dirname(__file__), "badge.png")
    badge = Image.open(badge_path).convert('RGBA')
    bw=int(210*scale); bh=int(bw*badge.height/badge.width)
    badge = badge.resize((bw,bh), Image.LANCZOS)
    img.paste(badge,(w-bw-int(50*scale),int(42*scale)),badge)

    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0),(w,int(10*scale))], fill=(*KIOTI_RED,255))
    draw.rectangle([(0,h-int(10*scale)),(w,h)], fill=(*KIOTI_RED,255))
    return img

def draw_frame(base, style, t, text, model_name, series_label, w, h):
    scale = w/W
    frame = base.copy()
    d = ImageDraw.Draw(frame)
    f_label = fnt(44, scale=scale)
    f_model = fnt(130, scale=scale)
    f_text = fnt(62, scale=scale)
    f_sub = fnt(44, bold=False, scale=scale)
    f_cta = fnt(60, scale=scale)
    Y = h - int(850*scale)
    lines = wrap_text(text, f_text, w-int(130*scale), d)
    x0 = int(65*scale)

    if style == "slide_left":
        p1=ease_out(min(1.0,t*3.0)); p2=ease_out(min(1.0,max(0,t*3.0-0.25)))
        p3=ease_out(min(1.0,max(0,t*3.0-0.55))); p4=ease_out(min(1.0,max(0,t*3.0-0.85)))
        shadow_text(d,int(-500*scale+p1*(500*scale+x0)),Y,series_label,f_label,(170,170,170))
        shadow_text(d,int(-600*scale+p2*(600*scale+x0-int(15*scale))),Y+int(94*scale),model_name,f_model,(255,255,255))
        ty=Y+int(249*scale)
        for i,line in enumerate(lines[:4]):
            shadow_text(d,int(-500*scale+p3*(500*scale+x0)),ty,line,f_text,KIOTI_RED if i==len(lines)-1 else (255,255,255))
            ty+=int(76*scale)
        a4=int(p4*255)
        shadow_text(d,x0,ty+int(10*scale),"7 Jahre Garantie auf den Antriebsstrang.",f_sub,(185,185,185),a4)
        shadow_text(d,x0,ty+int(72*scale),"Meld dich jetzt!",f_cta,KIOTI_RED,a4)

    elif style == "slide_bottom":
        p1=ease_out(min(1.0,t*2.5)); p2=ease_out(min(1.0,max(0,t*2.5-0.2)))
        p3=ease_out(min(1.0,max(0,t*2.5-0.45))); p4=ease_out(min(1.0,max(0,t*2.5-0.75)))
        off=int(350*scale)
        shadow_text(d,x0,Y+int((1-p1)*off),series_label,f_label,(170,170,170))
        shadow_text(d,x0,Y+int(94*scale)+int((1-p2)*off),model_name,f_model,(255,255,255))
        ty=Y+int(249*scale)
        for i,line in enumerate(lines[:4]):
            shadow_text(d,x0,ty+int((1-p3)*off),line,f_text,KIOTI_RED if i==len(lines)-1 else (255,255,255))
            ty+=int(76*scale)
        a4=int(p4*255)
        shadow_text(d,x0,ty+int(10*scale),"7 Jahre Garantie auf den Antriebsstrang.",f_sub,(185,185,185),a4)
        shadow_text(d,x0,ty+int(72*scale),"Meld dich jetzt!",f_cta,KIOTI_RED,a4)

    elif style == "fade_scale":
        p1=min(1.0,t*3.0); p2=min(1.0,max(0,t*3.0-0.3))
        p3=min(1.0,max(0,t*3.0-0.6)); p4=min(1.0,max(0,t*3.0-0.85))
        shadow_text(d,x0,Y,series_label,f_label,(170,170,170),int(p1*255))
        shadow_text(d,x0,Y+int(94*scale),model_name,f_model,(255,255,255),int(p2*255))
        ty=Y+int(249*scale)
        for i,line in enumerate(lines[:4]):
            shadow_text(d,x0,ty,line,f_text,KIOTI_RED if i==len(lines)-1 else (255,255,255),int(p3*255))
            ty+=int(76*scale)
        a4=int(p4*255)
        shadow_text(d,x0,ty+int(10*scale),"7 Jahre Garantie auf den Antriebsstrang.",f_sub,(185,185,185),a4)
        shadow_text(d,x0,ty+int(72*scale),"Meld dich jetzt!",f_cta,KIOTI_RED,a4)

    elif style == "typewriter":
        full_text=" ".join(lines[:4])
        shown_model=model_name[:int(min(len(model_name),t*len(model_name)*4))]
        shown_text=full_text[:int(min(len(full_text),max(0,(t-0.3)*len(full_text)*3)))]
        shadow_text(d,x0,Y,series_label,f_label,(170,170,170))
        shadow_text(d,x0,Y+int(94*scale),shown_model,f_model,(255,255,255))
        if int(t*12)%2==0 and len(shown_model)<len(model_name):
            bb=d.textbbox((x0,Y+int(94*scale)),shown_model,font=f_model)
            shadow_text(d,bb[2]+int(8*scale),Y+int(94*scale),"|",f_model,KIOTI_RED)
        ty=Y+int(249*scale)
        tw=wrap_text(shown_text,f_text,w-int(130*scale),d)
        for line in tw[:4]:
            shadow_text(d,x0,ty,line,f_text,(255,255,255)); ty+=int(76*scale)
        if int(t*12)%2==0 and shown_text:
            shadow_text(d,x0,ty,"|",f_text,KIOTI_RED)
        a4=int(min(255,max(0,(t-0.8)*8*255)))
        shadow_text(d,x0,Y+int(249*scale)+4*int(76*scale)+int(10*scale),"7 Jahre Garantie auf den Antriebsstrang.",f_sub,(185,185,185),a4)
        shadow_text(d,x0,Y+int(249*scale)+4*int(76*scale)+int(72*scale),"Meld dich jetzt!",f_cta,KIOTI_RED,a4)

    elif style == "bounce":
        p1=ease_bounce(min(1.0,t*2.5)); p2=ease_bounce(min(1.0,max(0,t*2.5-0.2)))
        p3=ease_bounce(min(1.0,max(0,t*2.5-0.5))); p4=ease_bounce(min(1.0,max(0,t*2.5-0.8)))
        shadow_text(d,x0,Y+int((1-p1)*-250*scale),series_label,f_label,(170,170,170))
        shadow_text(d,x0,Y+int(94*scale)+int((1-p2)*300*scale),model_name,f_model,(255,255,255))
        ty=Y+int(249*scale)
        for i,line in enumerate(lines[:4]):
            shadow_text(d,x0,ty+int((1-p3)*200*scale),line,f_text,KIOTI_RED if i==len(lines)-1 else (255,255,255))
            ty+=int(76*scale)
        a4=int(p4*255)
        shadow_text(d,x0,ty+int(10*scale),"7 Jahre Garantie auf den Antriebsstrang.",f_sub,(185,185,185),a4)
        shadow_text(d,x0,ty+int(72*scale),"Meld dich jetzt!",f_cta,KIOTI_RED,a4)

    return frame.convert('RGB')

def generate_animated_gif(photo_bytes, text, model_name, series_label, style):
    base = prepare_base(photo_bytes, GW, GH)
    fps = 12
    total_frames = int(fps * 2.5)
    frames = [draw_frame(base, style, i/total_frames, text, model_name, series_label, GW, GH)
              for i in range(total_frames)]
    for _ in range(fps): frames.append(frames[-1])
    buf = io.BytesIO()
    frames[0].save(buf, format='GIF', save_all=True, append_images=frames[1:],
                   duration=int(1000/fps), loop=0, optimize=True)
    buf.seek(0)
    return buf

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status":"ok","service":"Kioti Image Generator","photos":len(get_github_photos()),"styles":ANIMATION_STYLES})

@app.route('/daily', methods=['GET'])
def daily():
    global _cached_image, _cached_text, _cached_filename, _cached_mimetype
    try:
        photo_bytes, filename = get_random_github_photo()
        if not photo_bytes:
            return jsonify({"error":"Could not fetch photo from GitHub"}), 500
        model_name, series_label = detect_model(filename)
        text = get_claude_text(random.choice(PROMPTS))
        style = random.choice(ANIMATION_STYLES)
        img_buf = generate_animated_gif(photo_bytes, text, model_name, series_label, style)
        _cached_image = img_buf.read()
        _cached_text = text
        _cached_filename = "kioti_daily.gif"
        _cached_mimetype = 'image/gif'
        return jsonify({
            "image_url": "https://kioti-image-api.onrender.com/image",
            "text": text, "model": model_name, "style": style,
            "filename": _cached_filename, "date": datetime.now().strftime("%d.%m.%Y")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/image', methods=['GET'])
def serve_image():
    global _cached_image, _cached_filename, _cached_mimetype
    if not _cached_image:
        return "No image cached yet. Call /daily first.", 404
    return send_file(io.BytesIO(_cached_image), mimetype=_cached_mimetype,
                     download_name=_cached_filename or "kioti_daily.gif")

@app.route('/daily-image', methods=['GET'])
def daily_image():
    try:
        photo_bytes, filename = get_random_github_photo()
        if not photo_bytes: return "No photo", 500
        model_name, series_label = detect_model(filename)
        text = get_claude_text(random.choice(PROMPTS))
        style = random.choice(ANIMATION_STYLES)
        buf = generate_animated_gif(photo_bytes, text, model_name, series_label, style)
        return send_file(buf, mimetype='image/gif', download_name='kioti_daily.gif')
    except Exception as e:
        return str(e), 500

@app.route('/generate', methods=['POST'])
def generate():
    try:
        if 'photo' not in request.files:
            return jsonify({"error":"No photo"}), 400
        photo_bytes = request.files['photo'].read()
        text = request.form.get('text','').strip() or get_claude_text(random.choice(PROMPTS))
        model_name = request.form.get('model','KIOTI')
        series_label = request.form.get('series','KIOTI TRAKTOREN')
        style = request.form.get('style', random.choice(ANIMATION_STYLES))
        buf = generate_animated_gif(photo_bytes, text, model_name, series_label, style)
        return send_file(buf, mimetype='image/gif',
                        download_name=f'kioti_{datetime.now().strftime("%Y%m%d")}.gif')
    except Exception as e:
        return jsonify({"error":str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port, debug=False)
