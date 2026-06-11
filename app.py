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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
W, H = 1080, 1920
KIOTI_RED = (210, 35, 15)

GITHUB_USER = "LorenzStephan"
GITHUB_REPO = "kioti-image-api"
GITHUB_BRANCH = "main"

PROMPTS = [
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Max. 2 kurze Sätze. Direkt, stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: 7 Jahre Garantie. Max. 2 Sätze. Provokant, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Fairer Preis. Max. 2 Sätze. Direkt, kein Weichspüler, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Sofort verfügbar, keine Wartezeit. Max. 2 Sätze. Dringlichkeit, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Zuverlässigkeit für Lohnunternehmer. Max. 2 Sätze. Stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Weinbau und Obstbau. Max. 2 Sätze. Präzise, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
    "Schreibe einen WhatsApp-Post für Kioti Traktoren. Thema: Kommunale Fahrzeuge. Max. 2 Sätze. Sachlich, stark, ein Emoji. Ende mit: Meld dich jetzt! Nur den Post.",
]

def fnt(size, bold=True):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def get_github_photos():
    try:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/"
        res = requests.get(url, timeout=15)
        files = res.json()
        images = [f for f in files
                  if f.get("type") == "file" and
                  any(f.get("name","").lower().endswith(ext)
                      for ext in [".jpg",".jpeg",".png",".webp"])]
        return images
    except Exception as e:
        print(f"GitHub list error: {e}")
        return []

def get_random_github_photo():
    try:
        images = get_github_photos()
        if not images:
            return None, None
        safe_images = [f for f in images
                       if " " not in f["name"] and "(" not in f["name"]]
        if not safe_images:
            safe_images = images
        chosen = random.choice(safe_images)
        raw_url = chosen["download_url"]
        res = requests.get(raw_url, timeout=30)
        if res.status_code == 200:
            return res.content, chosen["name"]
        return None, None
    except Exception as e:
        print(f"GitHub photo error: {e}")
        return None, None

def get_claude_text(prompt):
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
    except:
        return "🚜 Kioti – robust, zuverlässig, fair. Meld dich jetzt!"

def wrap_text(text, font, max_width, draw):
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

def detect_model(filename):
    fn = filename.upper()
    if "HX1403" in fn or "HX140" in fn: return "HX1403", "HX SERIE  •  140 PS"
    if "HX1402" in fn: return "HX1402", "HX SERIE  •  140 PS"
    if "HX1201" in fn or "HX120" in fn: return "HX1201", "HX SERIE  •  120 PS"
    if "CS2
