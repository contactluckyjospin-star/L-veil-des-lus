import os
import re
import json
import time
import base64
import requests
import feedparser
import google.generativeai as genai
from datetime import datetime
from io import BytesIO

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
COMPETITOR_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id=UC6Xu0MRuSzXMF3CVB3HxMNg"
EBOOK_URL  = "https://cbqjfbfj.mychariow.shop"

GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
DRIVE_FOLDER_ID    = "1VOgqhCLPqMdGsc7XptSo7rYCmiYpfdBG"

MANUAL_URL_FILE = "manual_url.txt"
STATE_FILE = "state.json"

# ─────────────────────────────────────────
#  SERVICE ACCOUNT GOOGLE DRIVE
# ─────────────────────────────────────────
def save_output(folder, filename, content, binary=False):
    """Sauvegarde un fichier dans le dossier output/ du repo."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    mode = "wb" if binary else "w"
    encoding = None if binary else "utf-8"
    with open(path, mode, encoding=encoding) as f:
        f.write(content)
    print(f"   📁 {path}")
    return path

# ─────────────────────────────────────────
#  ÉTAT
# ─────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_video_id": None, "avatar_index": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ─────────────────────────────────────────
#  URL MANUELLE
# ─────────────────────────────────────────
def read_manual_url():
    if os.path.exists(MANUAL_URL_FILE):
        with open(MANUAL_URL_FILE) as f:
            content = f.read().strip()
        if content and ("youtube.com" in content or "youtu.be" in content):
            return content
    return ""

def clear_manual_url():
    with open(MANUAL_URL_FILE, "w") as f:
        f.write("")

COMPETITOR_URL_INPUT = read_manual_url()

# ─────────────────────────────────────────
#  RÉCUPÉRER LE TITRE D'UNE URL YOUTUBE
# ─────────────────────────────────────────
def get_video_id_from_url(url):
    patterns = [r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_video_title_from_url(url):
    video_id = get_video_id_from_url(url)
    if not video_id:
        raise Exception(f"Impossible d'extraire le video_id depuis : {url}")
    print(f"🔗 Video ID extrait : {video_id}")
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    resp = requests.get(oembed_url, timeout=10)
    if resp.status_code == 200:
        title = resp.json().get("title", "")
        if title:
            print(f"🎯 Titre récupéré : {title}")
            return video_id, title
    raise Exception(f"Impossible de récupérer le titre pour {video_id}")

# ─────────────────────────────────────────
#  SURVEILLANCE AUTO DU CONCURRENT
# ─────────────────────────────────────────
def check_new_video(state):
    print("🔍 Vérification du flux RSS concurrent...")
    feed = feedparser.parse(COMPETITOR_RSS)
    if not feed.entries:
        print("⚠️ Flux RSS vide ou inaccessible.")
        return None
    latest = feed.entries[0]
    video_id = latest.yt_videoid
    if video_id == state.get("last_video_id"):
        print("✅ Pas de nouvelle vidéo.")
        return None
    print(f"🎯 Nouvelle vidéo détectée : {latest.title}")
    return {"id": video_id, "title": latest.title}

# ─────────────────────────────────────────
#  GEMINI — TITRE (traduction directe)
# ─────────────────────────────────────────
def translate_title(competitor_title):
    print("🔤 Traduction du titre concurrent...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.5-flash")
    prompt = f"""Traduis ce titre YouTube en français.
Garde le même sens, la même énergie et la même puissance.
Réponds UNIQUEMENT avec le titre traduit, rien d'autre.
Titre à traduire : "{competitor_title}" """
    response = model.generate_content(prompt)
    title = response.text.strip().strip('"')
    print(f"🎬 Titre traduit : {title}")
    return title

# ─────────────────────────────────────────
#  GEMINI — SCRIPT (5 parties × 500 mots)
# ─────────────────────────────────────────
def generate_script(competitor_title, fr_title):
    print("✍️  Génération du script en 5 parties...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.5-flash")

    style = """STYLE EXACT de la chaîne "Vibrations Célestes" :
- Tutoiement intime ("tu"), tu parles directement à l'âme de l'élu
- Phrases courtes percutantes alternées avec des phrases longues et profondes
- Ton psychologique, thérapeutique, révélateur
- Open loops : "Si tu pars maintenant, tu risques de manquer..."
- Questions rhétoriques : "Est-ce que tu réalises à quel point..."
- Expressions : "Ne détourne pas le regard", "Je vais te dire la vérité crue", "mon ami"
- AUCUNE indication visuelle, AUCUN horodatage, AUCUN titre de section
- Uniquement les paroles à dire à voix haute, texte fluide et continu"""

    contexte = f'Thème : "{fr_title}"\nThème original : "{competitor_title}"'

    parties_prompts = [
        f"""{style}\n{contexte}\n\nÉcris la PARTIE 1 (HOOK) du script.
- Commence par "Écoute-moi attentivement, car..."
- Urgence immédiate, open loop puissant
- Écris EXACTEMENT environ 500 mots pour cette partie (ni moins, ni beaucoup plus)
- Termine par : "Et parce que je sais à quel point ce chemin est complexe et parsemé d'embûches émotionnelles, j'ai condensé toute la méthode dans mon ebook spécial. Si tu sens que tu as besoin d'un guide pas à pas, cet ouvrage est fait pour toi. Le lien est dans la description, prêt à t'accompagner vers ta nouvelle vie."
Écris UNIQUEMENT le texte, rien d'autre.""",

        f"""{style}\n{contexte}\n\nScript déjà écrit :\n---\n{{precedent}}\n---\n\nÉcris la PARTIE 2 (DÉVELOPPEMENT PROFOND) qui continue naturellement.
- Métaphores puissantes, exemples concrets
- Écris EXACTEMENT environ 500 mots pour cette partie (ni moins, ni beaucoup plus)
- PAS de promo ebook
Écris UNIQUEMENT le texte, rien d'autre.""",

        f"""{style}\n{contexte}\n\nScript déjà écrit :\n---\n{{precedent}}\n---\n\nÉcris la PARTIE 3 (RÉVÉLATION / TOURNANT) qui continue naturellement.
- Vérité que personne n'ose dire
- Écris EXACTEMENT environ 500 mots pour cette partie (ni moins, ni beaucoup plus)
- Termine par : "Et parce que je veux que cette transformation soit concrète dans ta vie, j'ai créé quelque chose pour toi. Mon ebook t'accompagne pas à pas. Le lien est dans la description."
Écris UNIQUEMENT le texte, rien d'autre.""",

        f"""{style}\n{contexte}\n\nScript déjà écrit :\n---\n{{precedent}}\n---\n\nÉcris la PARTIE 4 (RESPONSABILITÉ) qui continue naturellement.
- Responsabilité de l'élu, pièges à éviter
- Écris EXACTEMENT environ 500 mots pour cette partie (ni moins, ni beaucoup plus)
- PAS de promo ebook
Écris UNIQUEMENT le texte, rien d'autre.""",

        f"""{style}\n{contexte}\n\nScript déjà écrit :\n---\n{{precedent}}\n---\n\nÉcris la PARTIE 5 (CONCLUSION PUISSANTE) qui termine le script.
- "C'est maintenant que tout se décide. Non pas demain..."
- Écris EXACTEMENT environ 500 mots pour cette partie (ni moins, ni beaucoup plus)
- Termine par : "Abonne-toi à cette chaîne et active la cloche. Et si tu veux aller encore plus loin, mon ebook t'attend dans la description. Chaque page est une main tendue vers la version de toi qui n'attendait que ta permission pour exister pleinement. Ton moment est maintenant. Et cette fois, rien ne peut plus l'arrêter."
Écris UNIQUEMENT le texte, rien d'autre."""
    ]

    parties = []
    script_complet = ""
    for i, prompt_template in enumerate(parties_prompts, 1):
        prompt = prompt_template.replace("{precedent}", script_complet[-2000:])
        response = model.generate_content(prompt)
        partie = response.text.strip()
        parties.append(partie)
        script_complet += partie + "\n\n"
        print(f"   ✓ Partie {i}/5 générée ({len(partie)} car. / {len(partie.split())} mots)")

    script = script_complet.strip()
    print(f"📝 Script complet : {len(script)} caractères ({len(script.split())} mots)")
    return script

# ─────────────────────────────────────────
#  GEMINI — DESCRIPTION + COMMENTAIRE ÉPINGLÉ
# ─────────────────────────────────────────
def generate_description_and_comment(fr_title):
    print("🏷️  Génération de la description YouTube...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.5-flash")
    prompt = f"""Tu es le créateur de "Vibrations Célestes", chaîne spirituelle française pour les âmes élues.

Basé sur ce titre : "{fr_title}"

Génère en JSON (UNIQUEMENT le JSON, rien d'autre, pas de backticks) :
{{
  "description": "Une description YouTube RICHE et COMPLÈTE en français (350-400 mots) dans le style intime et spirituel de Vibrations Célestes. Structure : (1) Une accroche puissante de 2-3 phrases qui parle directement à l'élu. (2) Un paragraphe qui développe le thème de la vidéo et ce que le spectateur va recevoir. (3) Une invitation chaleureuse à regarder jusqu'au bout. (4) Une promotion de l'ebook avec le lien {EBOOK_URL} (présente l'ebook comme un guide de transformation). (5) Un appel à s'abonner, liker et commenter 'AMEN' pour recevoir les bénédictions. Utilise des sauts de ligne entre les paragraphes. Ton émotionnel et inspirant.",
  "tags": "Liste de 15 tags pertinents séparés par des virgules, en français, sur le thème spirituel (élu, foi, Dieu, miracle, âme, signes divins, éveil spirituel, message de Dieu, etc.)",
  "pinned_comment": "Commentaire épinglé chaleureux en français, 4-5 lignes. Commence par un emoji spirituel. Invite à commenter 'AMEN', fait la promo de l'ebook avec {EBOOK_URL}, et invite à s'abonner."
}}"""
    response = model.generate_content(prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    return data["description"], data["tags"], data["pinned_comment"]

# ─────────────────────────────────────────
#  MINIATURE
# ─────────────────────────────────────────
def generate_thumbnail(fr_title):
    from thumbnail import generate_thumbnail as gen_thumb
    from thumbnail import clean_title_for_thumbnail
    main_title = clean_title_for_thumbnail(fr_title)
    path = gen_thumb(main_title, "(S'IL VOUS PLAÎT, REGARDEZ CECI)", "thumbnail.jpg")
    return path

# ─────────────────────────────────────────
#  PIPELINE PRINCIPAL
# ─────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"  SPIRITUAL AUTOPILOT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    state = load_state()

    # ── MODE MANUEL ou AUTO ──
    if COMPETITOR_URL_INPUT:
        print(f"🎯 MODE MANUEL — URL reçue : {COMPETITOR_URL_INPUT}")
        video_id, competitor_title = get_video_title_from_url(COMPETITOR_URL_INPUT)
        new_video = {"id": f"manual_{video_id}", "title": competitor_title}
    else:
        print("🤖 MODE AUTO — Surveillance RSS")
        new_video = check_new_video(state)
        if not new_video:
            return

    try:
        # 1. Traduire le titre
        fr_title = translate_title(new_video["title"])

        # 2. Générer le script (5 parties × 500 mots)
        script = generate_script(new_video["title"], fr_title)

        # 3. Générer description + commentaire épinglé
        yt_desc, yt_tags, pinned_comment = generate_description_and_comment(fr_title)

        # 4. Générer la miniature
        print("🖼️  Génération de la miniature...")
        thumb_path = generate_thumbnail(fr_title)

        # 5. Préparer le résumé
        date_str = datetime.now().strftime('%Y-%m-%d_%H%M')
        folder_name = f"{date_str}_{fr_title[:50].replace(' ', '_')}"

        print(f"\n📤 Upload vers Google Drive...")

        # 6. Sauvegarder tout dans le dossier output/
        safe_title = re.sub(r'[^\w\s-]', '', fr_title)[:50].strip().replace(' ', '_')
        out_folder = os.path.join("output", f"{date_str}_{safe_title}")

        print(f"\n📁 Sauvegarde dans {out_folder}/")

        save_output(
            out_folder,
            "SCRIPT.txt",
            f"TITRE : {fr_title}\n\n{'='*50}\nSCRIPT COMPLET (à copier dans HeyGen)\n{'='*50}\n\n{script}"
        )

        save_output(
            out_folder,
            "DESCRIPTION.txt",
            f"TITRE YOUTUBE :\n{fr_title}\n\n{'='*50}\nDESCRIPTION :\n{'='*50}\n\n{yt_desc}\n\n{'='*50}\nTAGS (à copier dans le champ Tags YouTube) :\n{'='*50}\n\n{yt_tags}\n\n{'='*50}\nCOMMENTAIRE ÉPINGLÉ :\n{'='*50}\n\n{pinned_comment}"
        )

        with open(thumb_path, "rb") as f:
            thumb_data = f.read()
        save_output(out_folder, "MINIATURE.jpg", thumb_data, binary=True)
        os.remove(thumb_path)

        # 7. Mettre à jour l'état
        if COMPETITOR_URL_INPUT:
            clear_manual_url()
        else:
            state["last_video_id"] = new_video["id"]
        state["avatar_index"] = (state["avatar_index"] + 1) % 2
        save_state(state)

        print(f"\n🎉 SUCCÈS ! Tout est prêt dans le dossier output/ :")
        print(f"   📝 Script : {len(script)} car. ({len(script.split())} mots)")
        print(f"   🎬 Titre : {fr_title}")
        print(f"   📋 Description + commentaire épinglé")
        print(f"   🖼️  Miniature")
        print(f"\n   → Va dans {out_folder}/ sur GitHub, copie le script dans HeyGen, et publie ! 🚀")

    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        raise

if __name__ == "__main__":
    main()
