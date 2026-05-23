from PIL import Image, ImageDraw, ImageFont
import requests
import os
import textwrap

THUMBNAIL_SIZE = (1280, 720)
MARGIN = 60  # marge gauche/droite

def download_font():
    font_path = "/tmp/Anton-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
        r = requests.get(url)
        with open(font_path, "wb") as f:
            f.write(r.content)
    return font_path

def draw_text_with_outline(draw, text, position, font, fill="white", outline="black", outline_width=7):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=outline, anchor="mm")
    draw.text((x, y), text, font=font, fill=fill, anchor="mm")

def fit_font_size(draw, text, font_path, max_width, start_size, min_size=40):
    """Trouve la plus grande taille de police qui fait tenir le texte dans max_width."""
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font, size
        size -= 4
    return ImageFont.truetype(font_path, min_size), min_size

def wrap_text(text, max_chars):
    """Découpe le texte en lignes de max_chars caractères, sans couper les mots."""
    return textwrap.wrap(text, width=max_chars)

def generate_thumbnail(main_title, subtitle="(S'IL VOUS PLAÎT, REGARDEZ CECI)", output_path="thumbnail.jpg"):
    """
    Génère une miniature style Vibrations Célestes.
    main_title : le titre principal (sera découpé en lignes automatiquement)
    subtitle   : le sous-titre fixe en jaune (toujours présent)
    """
    bg = Image.open("background.png").convert("RGB")
    bg = bg.resize(THUMBNAIL_SIZE, Image.LANCZOS)

    # Assombrir un peu pour que le texte blanc ressorte
    overlay = Image.new("RGB", THUMBNAIL_SIZE, (0, 0, 0))
    bg = Image.blend(bg, overlay, alpha=0.25)

    draw = ImageDraw.Draw(bg)
    font_path = download_font()
    cx = THUMBNAIL_SIZE[0] // 2
    max_text_width = THUMBNAIL_SIZE[0] - 2 * MARGIN

    main_title = main_title.upper().strip()
    subtitle = subtitle.upper().strip()

    # Découper le titre principal en lignes (max ~18 caractères par ligne)
    lines = wrap_text(main_title, 18)
    if len(lines) > 3:
        # Trop de lignes : regrouper
        lines = wrap_text(main_title, 24)[:3]

    # Calculer la taille de police pour le titre (la plus grande qui tient)
    longest_line = max(lines, key=len)
    title_font, title_size = fit_font_size(draw, longest_line, font_path, max_text_width, start_size=120)

    # Hauteur de ligne
    line_height = int(title_size * 1.15)
    subtitle_font, _ = fit_font_size(draw, subtitle, font_path, max_text_width, start_size=70, min_size=35)
    sub_height = int(subtitle_font.size * 1.2)

    # Hauteur totale du bloc de texte
    total_height = len(lines) * line_height + sub_height + 30
    start_y = (THUMBNAIL_SIZE[1] - total_height) // 2 + line_height // 2

    # Dessiner chaque ligne du titre (blanc)
    y = start_y
    for line in lines:
        draw_text_with_outline(draw, line, (cx, y), title_font, fill="white")
        y += line_height

    # Dessiner le sous-titre (jaune)
    y += 20
    draw_text_with_outline(draw, subtitle, (cx, y), subtitle_font, fill="#FFD700", outline_width=5)

    bg.save(output_path, "JPEG", quality=95)
    print(f"✅ Miniature générée : {output_path}")
    return output_path

def clean_title_for_thumbnail(yt_title):
    """Nettoie le titre YouTube pour la miniature : retire emojis et sous-titre entre parenthèses."""
    import re
    # Retirer le contenu entre parenthèses (on a notre propre sous-titre)
    title = re.sub(r'\([^)]*\)', '', yt_title)
    # Retirer les emojis et caractères spéciaux
    title = re.sub(r'[^\w\s\'!?-]', '', title, flags=re.UNICODE)
    # Retirer "L'ÉLU :" ou préfixes pour garder le punch
    title = title.strip(' :')
    return title.strip()
