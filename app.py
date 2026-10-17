import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
import json
import os
import base64
import re
import hashlib
import io
import urllib.parse

# Configuration de la page
st.set_page_config(
    page_title="Ronde Farfadets - SGDF",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_FILE = "ronde_data.json"

# =============================================================
# SÉCURITÉ : HACHAGE & VÉRIFICATION DES MOTS DE PASSE
# =============================================================
def hash_password(pwd: str) -> str:
    if not pwd:
        return ""
    # Si la chaîne est déjà un hash SHA-256 valide (64 caractères hexadécimaux)
    if len(pwd) == 64 and all(c in "0123456789abcdefABCDEF" for c in pwd):
        return pwd
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def verify_password(input_pwd: str, stored_hash: str) -> bool:
    if not stored_hash or not input_pwd:
        return False
    # Rétrocompatibilité transparente si le mot de passe est encore en clair dans le JSON
    if stored_hash == input_pwd:
        return True
    return hash_password(input_pwd) == stored_hash

# =============================================================
# FONCTIONS UTILITAIRES DE DATE ET FICHIERS
# =============================================================
def format_date_fr(d_str):
    if not d_str:
        return ""
    d_clean = str(d_str).strip()
    if "/" in d_clean:
        return d_clean
    try:
        dt = datetime.strptime(d_clean, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return d_clean

def parse_date_to_iso(d_input):
    if isinstance(d_input, (date, datetime)):
        return d_input.strftime("%Y-%m-%d")
    d_clean = str(d_input).strip()
    if "/" in d_clean:
        try:
            parts = d_clean.split("/")
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        except Exception:
            return d_clean
    return d_clean

def parse_date_obj(d_input):
    if isinstance(d_input, date):
        return d_input
    d_clean = str(d_input).strip()
    if "/" in d_clean:
        try:
            return datetime.strptime(d_clean, "%d/%m/%Y").date()
        except Exception:
            pass
    try:
        return datetime.strptime(d_clean, "%Y-%m-%d").date()
    except Exception:
        return date.today()

def file_to_base64(uploaded_file):
    if uploaded_file is not None:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        return f"data:{uploaded_file.type};base64,{b64}"
def safe_float(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    try:
        s = str(val).strip().replace(",", ".")
        return float(s)
    except Exception:
        return default

def safe_int(val, default=0):
    if val is None or pd.isna(val):
        return default
    try:
        s = str(val).strip().replace(",", ".")
        return int(float(s))
    except Exception:
        return default

def normalize_rencontre_data(r):
    r.setdefault("description", "")
    r.setdefault("imaginaire_rencontre", "")
    r.setdefault("objectifs", "")
    r.setdefault("photo", "")
    r.setdefault("lieu_adresse", r.get("lieu", "Local Scout - Sartrouville"))
    r["lat"] = safe_float(r.get("lat"), 48.9417)
    r["lon"] = safe_float(r.get("lon"), 2.1645)
    r.setdefault("materiels", [])
    r.setdefault("colonnes_deroule", [])
    
    clean_deroule = []
    for step in r.get("deroule", []):
        d_item = {
            "date": format_date_fr(step.get("date", r.get("date", ""))),
            "heure_debut": step.get("heure_debut", step.get("heure", "14:00")),
            "heure_fin": step.get("heure_fin", "14:30"),
            "activite": step.get("activite", ""),
            "animateur": step.get("animateur", step.get("responsable", r.get("animateur", ""))),
            "commentaire": step.get("commentaire", ""),
            "materiels": step.get("materiels", [step.get("materiel")] if step.get("materiel") else [])
        }
        for k, v in step.items():
            if k not in d_item:
                d_item[k] = v
        clean_deroule.append(d_item)
    r["deroule"] = clean_deroule
    return r

# =============================================================
# CHARGEMENT ET SAUVEGARDE DE LA BASE DE DONNÉES
# =============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"active_ronde_id": 1, "rondes": [], "utilisateurs": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            raw.setdefault("active_ronde_id", 1)
            raw.setdefault("rondes", [])
            raw.setdefault("utilisateurs", [])
            for ro in raw.get("rondes", []):
                ro.setdefault("imaginaire_photos", [])
                ro.setdefault("imaginaire_titre", "L'Aventure des Farfadets")
                ro["rencontres"] = [normalize_rencontre_data(r) for r in ro.get("rencontres", [])]
            return raw
    except Exception:
        return {"active_ronde_id": 1, "rondes": [], "utilisateurs": []}

def build_excel_export_bytes(database_obj, save_path=None):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 1. Rondes
        rows_r = [{
            "id": r.get("id"), "nom": r.get("nom", ""), "saison": r.get("saison", ""),
            "groupe": r.get("groupe", ""), "peuplade": r.get("peuplade", ""), "lieu_habituel": r.get("lieu_habituel", "")
        } for r in database_obj.get("rondes", [])]
        pd.DataFrame(rows_r).to_excel(writer, sheet_name="Rondes", index=False)
        
        # 2. Membres
        rows_m = []
        for r in database_obj.get("rondes", []):
            for m in r.get("membres", []):
                rows_m.append({
                    "id": m.get("id"), "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""),
                    "prenom": m.get("prenom", ""), "nom": m.get("nom", ""),
                    "role": m.get("role", "Enfant"), "contact": m.get("contact", ""), "photo": m.get("photo", "")
                })
        pd.DataFrame(rows_m).to_excel(writer, sheet_name="Membres", index=False)

        # 3. Rencontres (paramétrage complet du site)
        rows_rc = []
        for r in database_obj.get("rondes", []):
            for rc in r.get("rencontres", []):
                rows_rc.append({
                    "id": rc.get("id"), "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""), "titre": rc.get("titre", ""),
                    "type": rc.get("type", "Rencontre ronde"), "date": rc.get("date", ""), "horaire": rc.get("horaire", "14:00 - 17:00"),
                    "lieu": rc.get("lieu", ""), "lieu_adresse": rc.get("lieu_adresse", rc.get("lieu", "")),
                    "lat": rc.get("lat", 48.9417), "lon": rc.get("lon", 2.1645),
                    "animateur": rc.get("animateur", ""), "statut": rc.get("statut", "À venir"),
                    "description": rc.get("description", ""), "imaginaire_rencontre": rc.get("imaginaire_rencontre", ""),
                    "objectifs": rc.get("objectifs", ""), "photo": rc.get("photo", ""),
                    "colonnes_deroule_json": json.dumps(rc.get("colonnes_deroule", []), ensure_ascii=False),
                    "deroule_json": json.dumps(rc.get("deroule", []), ensure_ascii=False),
                    "materiels_json": json.dumps(rc.get("materiels", []), ensure_ascii=False)
                })
        pd.DataFrame(rows_rc).to_excel(writer, sheet_name="Rencontres", index=False)

        # 4. Deroules (tableau détaillé étape par étape)
        rows_d = []
        for r in database_obj.get("rondes", []):
            for rc in r.get("rencontres", []):
                custom_cols = rc.get("colonnes_deroule", [])
                for idx, s in enumerate(rc.get("deroule", [])):
                    row_d = {
                        "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""), "rencontre_id": rc.get("id"), "titre_rencontre": rc.get("titre", ""),
                        "etape": idx + 1, "date": s.get("date", ""), "heure_debut": s.get("heure_debut", ""),
                        "heure_fin": s.get("heure_fin", ""), "activite": s.get("activite", ""),
                        "animateur": s.get("animateur", ""),
                        "materiels": ", ".join(s.get("materiels", [])) if isinstance(s.get("materiels"), list) else str(s.get("materiels", "")),
                        "commentaire": s.get("commentaire", "")
                    }
                    for cc in custom_cols:
                        row_d[cc] = s.get(cc, "")
                    rows_d.append(row_d)
        pd.DataFrame(rows_d).to_excel(writer, sheet_name="Deroules", index=False)

        # 5. Materiels (inventaire détaillé)
        rows_mat = []
        for r in database_obj.get("rondes", []):
            for rc in r.get("rencontres", []):
                for m in rc.get("materiels", []):
                    rows_mat.append({
                        "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""), "rencontre_id": rc.get("id"), "titre_rencontre": rc.get("titre", ""),
                        "materiel_id": m.get("id", ""), "nom": m.get("nom", ""), "qui_amene": m.get("qui_amene", ""),
                        "quantite_remarque": m.get("remarque", m.get("quantite", "")), "photo": m.get("photo", "")
                    })
        pd.DataFrame(rows_mat).to_excel(writer, sheet_name="Materiels", index=False)

        # 6. Imaginaire
        rows_im = [{
            "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""),
            "titre": r.get("imaginaire_titre", "L'Aventure des Farfadets"),
            "texte": r.get("imaginaire", ""),
            "photos_json": json.dumps(r.get("imaginaire_photos", []), ensure_ascii=False)
        } for r in database_obj.get("rondes", [])]
        pd.DataFrame(rows_im).to_excel(writer, sheet_name="Imaginaire", index=False)

        # 7. Supports
        rows_sp = []
        for r in database_obj.get("rondes", []):
            for sp in r.get("supports", []):
                rows_sp.append({
                    "id": sp.get("id"), "ronde_id": r.get("id"), "ronde_nom": r.get("nom", ""), "titre": sp.get("titre", ""),
                    "url": sp.get("url", ""), "categorie": sp.get("categorie", "Pédagogie"), "desc": sp.get("desc", "")
                })
        pd.DataFrame(rows_sp).to_excel(writer, sheet_name="Supports", index=False)

        # 8. Utilisateurs
        rows_u = []
        for u in database_obj.get("utilisateurs", []):
            r_auth = u.get("rondes_autorisees", [])
            rows_u.append({
                "id": u.get("id"), "prenom": u.get("prenom", ""), "nom": u.get("nom", ""),
                "email": u.get("email", ""), "role": u.get("role", "parent"), "membre_id": u.get("membre_id", ""),
                "rondes_autorisees": ", ".join(map(str, r_auth)) if isinstance(r_auth, list) else str(r_auth)
            })
        pd.DataFrame(rows_u).to_excel(writer, sheet_name="Utilisateurs", index=False)

        # 9. Configuration
        rows_cfg = [
            {"cle": "active_ronde_id", "valeur": str(database_obj.get("active_ronde_id", 1))},
            {"cle": "google_sheet_url", "valeur": str(database_obj.get("google_sheet_url", ""))},
            {"cle": "date_export", "valeur": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
        ]
        pd.DataFrame(rows_cfg).to_excel(writer, sheet_name="Configuration", index=False)

    data = buf.getvalue()
    if save_path:
        try:
            with open(save_path, "wb") as f_out:
                f_out.write(data)
        except Exception:
            pass
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Met à jour le modèle Excel local sur disque en arrière-plan
    try:
        excel_mirror_path = os.path.join(os.path.dirname(__file__), "Modele_Google_Sheets_Ronde_Farfadets.xlsx")
        build_excel_export_bytes(data, save_path=excel_mirror_path)
    except Exception:
        pass

db = load_data()

# Gestion de la ronde active
def get_current_ronde():
    rondes = db.get("rondes", [])
    if not rondes:
        ro_default = {
            "id": 1,
            "nom": "Ronde 3 Farfadets - Sartrouville",
            "saison": "2026 - 2027",
            "groupe": "Groupe Saint Martin Sartrouville",
            "peuplade": "Branche scoute des 6 - 8 ans et leurs parents",
            "lieu_habituel": "Local Scout - Notre Dame du Val",
            "membres": [],
            "rencontres": [],
            "imaginaire": "Bienvenue au village des Farfadets !",
            "imaginaire_titre": "L'Aventure des Farfadets",
            "imaginaire_photos": [],
            "supports": []
        }
        db["rondes"] = [ro_default]
        db["active_ronde_id"] = 1
        save_data(db)
        return ro_default
    
    # Priorité à l'état de session si défini
    cur_id = st.session_state.get("active_ronde_id", db.get("active_ronde_id", rondes[0]["id"]))
    for r in rondes:
        if r.get("id") == cur_id:
            return r
    st.session_state["active_ronde_id"] = rondes[0]["id"]
    db["active_ronde_id"] = rondes[0]["id"]
    save_data(db)
    return rondes[0]

def switch_ronde(new_id):
    st.session_state["active_ronde_id"] = new_id
    db["active_ronde_id"] = new_id
    save_data(db)
    st.session_state["flash_success"] = f"✅ Vous êtes maintenant connecté à la ronde : {get_current_ronde().get('nom')}"
    st.rerun()

current_ronde = get_current_ronde()

# Variables d'état générales
if "cal_year" not in st.session_state:
    st.session_state["cal_year"] = 2026
if "cal_month" not in st.session_state:
    st.session_state["cal_month"] = 10
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "🏠 Accueil"

# =============================================================
# CSS HAUTE FIDÉLITÉ (Barre supérieure, Tiroir Burger, Map, Cartes)
# =============================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    color-scheme: light only !important;
    supported-color-schemes: light !important;
}

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color-scheme: light only !important;
    background-color: #F8FAFC !important;
    color: #0F172A !important;
}

/* Masquer les barres de contrôle Streamlit pour un rendu application natif */
[data-testid="stToolbar"], .stDeployButton, #MainMenu, footer, [data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
    visibility: hidden !important;
}

header[data-testid="stHeader"] {
    display: none !important;
    height: 0px !important;
}

/* ==========================================================================
   MODALES, DIALOGUES ET POPUPS STREAMLIT (st.dialog, stModal, BaseWeb)
   Résout définitivement le problème de dialogue sombre sur mobile
   ========================================================================== */
div[data-testid="stDialog"],
div[data-testid="stDialog"] > div,
div[data-testid="stDialog"] [role="dialog"],
div[data-testid="stDialog"] [role="dialog"] > div,
div[data-testid="stDialog"] [role="dialog"] section,
div[data-testid="stDialog"] [data-testid="stVerticalBlock"],
div[data-testid="stDialog"] [data-testid="stForm"],
div[data-baseweb="modal"],
div[data-baseweb="modal"] > div,
div[data-baseweb="modal-body"],
div[role="dialog"],
div[role="dialog"] > div,
div[role="dialog"] section,
div[role="dialog"] [data-testid="stVerticalBlock"],
div[role="dialog"] [data-testid="stForm"],
.stModal,
.stModal > div {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border-color: #CBD5E1 !important;
}

/* Titres de modales */
div[data-testid="stDialog"] h1,
div[data-testid="stDialog"] h2,
div[data-testid="stDialog"] h3,
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] h2,
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p,
div[role="dialog"] h1,
div[role="dialog"] h2,
div[role="dialog"] h3,
div[role="dialog"] [data-testid="stMarkdownContainer"] p {
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
    font-weight: 700 !important;
}

/* Bouton fermer (croix X) de la modale */
div[data-testid="stDialog"] button[aria-label="Close"],
div[data-testid="stDialog"] button[aria-label="Fermer"],
div[role="dialog"] button[aria-label="Close"],
div[role="dialog"] button[aria-label="Fermer"],
div[role="dialog"] button svg,
div[data-testid="stDialog"] button svg {
    color: #1E293B !important;
    fill: #1E293B !important;
    stroke: #1E293B !important;
}

/* ==========================================================================
   TEXTES, TITRES ET LABELS DE FORMULAIRES
   Contraste sombre garanti sur fond clair
   ========================================================================== */
h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, [data-testid="stMarkdownContainer"] p {
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
}

[data-testid="stWidgetLabel"] label, 
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {
    color: #1E293B !important;
    -webkit-text-fill-color: #1E293B !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

.stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: #64748B !important;
    -webkit-text-fill-color: #64748B !important;
}

/* ==========================================================================
   CHAMPS DE SAISIE (INPUTS, TEXTAREAS, NUMBER INPUTS)
   ========================================================================== */
input, textarea, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="input"] input {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
}

input:focus, textarea:focus, [data-baseweb="input"]:focus-within {
    border-color: #1D4ED8 !important;
    box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.2) !important;
}

input::placeholder, textarea::placeholder {
    color: #94A3B8 !important;
    -webkit-text-fill-color: #94A3B8 !important;
}

/* ==========================================================================
   MENUS DÉROULANTS (SELECTBOX, MULTISELECT, BASEWEB)
   ========================================================================== */
[data-baseweb="select"],
[data-baseweb="select"] > div,
[data-baseweb="select"] div {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
}

[data-baseweb="select"] > div {
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
}

[data-baseweb="select"] svg {
    fill: #1E293B !important;
    color: #1E293B !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] > div,
[role="listbox"],
[role="listbox"] > div,
[role="option"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
}

[role="option"]:hover,
[aria-selected="true"] {
    background-color: #EFF6FF !important;
    color: #1D4ED8 !important;
    -webkit-text-fill-color: #1D4ED8 !important;
}

/* Multi-select tags */
[data-baseweb="tag"] {
    background-color: #EFF6FF !important;
    color: #1D4ED8 !important;
    -webkit-text-fill-color: #1D4ED8 !important;
    border: 1px solid #BFDBFE !important;
}

/* ==========================================================================
   BOUTONS PRIMAIRES & SECONDAIRES
   Empêche le bouton rouge par défaut de Streamlit
   ========================================================================== */
button[kind="primary"],
button[data-testid="baseButton-primary"],
.stFormSubmitButton > button,
button[type="submit"] {
    background-color: #1D4ED8 !important;
    border: 1px solid #1D4ED8 !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover,
.stFormSubmitButton > button:hover {
    background-color: #1E40AF !important;
    border-color: #1E40AF !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

button[kind="secondary"],
button[data-testid="baseButton-secondary"] {
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    color: #1E293B !important;
    -webkit-text-fill-color: #1E293B !important;
    border-radius: 8px !important;
}

button[kind="secondary"]:hover,
button[data-testid="baseButton-secondary"]:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

/* Onglets Streamlit */
button[data-baseweb="tab"] {
    color: #64748B !important;
    -webkit-text-fill-color: #64748B !important;
    font-weight: 600 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #1D4ED8 !important;
    -webkit-text-fill-color: #1D4ED8 !important;
    border-bottom-color: #1D4ED8 !important;
}

.main .block-container {
    padding-top: 1rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1350px;
}

/* TOP NAVBAR CONTENANT LE BURGER, LE LOGO ET LE PROFIL (Image 1) */
.custom-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #FFFFFF;
    padding: 8px 18px;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 18px;
    border: 1px solid #E2E8F0;
}

.brand-title-box {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-badge-tag {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    color: #1D4ED8;
    font-weight: 800;
    font-size: 15px;
    padding: 6px 12px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.help-circle-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background-color: #1D4ED8;
    color: white;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 16px;
    box-shadow: 0 2px 6px rgba(29, 78, 216, 0.25);
}

.user-badge-btn {
    background-color: #1E3A8A;
    color: #FFFFFF !important;
    font-size: 13px;
    font-weight: 600;
    padding: 7px 16px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.role-tag-pill {
    background: #3B82F6;
    color: white;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 10px;
    text-transform: uppercase;
}

/* HERO BANNER EN-TÊTE */
.hero-header-card {
    background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
    border-radius: 16px;
    padding: 26px 22px 22px 22px;
    text-align: center;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    margin-bottom: 20px;
}

.hero-main-title {
    font-size: 28px;
    font-weight: 800;
    color: #0F172A;
    margin: 0;
}

.hero-sub-title {
    font-size: 18px;
    font-weight: 700;
    color: #1E293B;
    margin-top: 4px;
}

.hero-badge-tag {
    display: inline-block;
    margin-top: 6px;
    background: #DBEAFE;
    color: #1E40AF;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 20px;
}

/* CARTES DASHBOARD */
.dashboard-card {
    background: #FFFFFF;
    border-radius: 14px;
    border: 1px solid #E2E8F0;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    min-height: 105px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.card-icon-bubble {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: #1D4ED8;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.card-title {
    font-size: 15.5px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
}

.card-subtitle {
    font-size: 12.5px;
    color: #64748B;
    margin-top: 3px;
    margin-bottom: 0;
}

.card-action-btn {
    background: #1D4ED8;
    color: #FFFFFF !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 8px;
    display: inline-block;
}

/* CARTE MAPS */
.map-card-box {
    background: #FFFFFF;
    border-radius: 14px;
    border: 1px solid #E2E8F0;
    padding: 16px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 16px;
}

.map-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.map-title {
    font-size: 16px;
    font-weight: 800;
    color: #0F172A;
    margin: 0;
}

.map-address {
    font-size: 12.5px;
    color: #64748B;
    margin-top: 2px;
}

.map-frame-wrapper {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #CBD5E1;
    height: 220px;
    position: relative;
}

/* CALENDRIER EXACT */
.cal-nav-title {
    font-size: 13.5px;
    font-weight: 800;
    color: #111827;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    text-align: center;
}

.cal-scroll-area {
    max-height: 380px;
    overflow-y: auto;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    margin-bottom: 14px;
}

.cal-grid-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin: 0 !important;
}

.cal-grid-table th {
    font-size: 12.5px;
    font-weight: 600;
    color: #111827;
    text-align: center;
    padding: 8px 2px;
    border-bottom: 1px solid #E5E7EB;
    border-right: 1px solid #E5E7EB;
    background: #FAFAFA;
}
.cal-grid-table th:last-child {
    border-right: none;
}

.cal-grid-table td {
    vertical-align: top;
    height: 58px;
    padding: 4px 5px;
    border-bottom: 1px solid #E5E7EB;
    border-right: 1px solid #E5E7EB;
    background: #FFFFFF;
}
.cal-grid-table td:last-child {
    border-right: none;
}

.cal-grid-table td.today-cell {
    background-color: #FEFCE8 !important;
}

.cal-day-header {
    text-align: right;
    font-size: 12px;
    font-weight: 600;
    color: #111827;
    line-height: 1;
    margin-bottom: 2px;
}

.cal-day-header.muted {
    color: #9CA3AF;
    font-weight: 400;
}

.cal-slot-badge {
    background: #5B4FC4;
    color: #FFFFFF;
    font-size: 9.5px;
    font-weight: 600;
    padding: 2px 4px;
    border-radius: 4px;
    display: block;
    text-align: center;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.25;
}

/* ANIMATEURS */
.speaker-profile-box {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.speaker-avatar-circle {
    width: 72px;
    height: 72px;
    border-radius: 14px;
    background: linear-gradient(135deg, #3B82F6, #1D4ED8);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: 700;
    box-shadow: 0 3px 8px rgba(29, 78, 216, 0.2);
    margin-bottom: 8px;
    border: 3px solid #EFF6FF;
}

/* STYLE DU TIROIR BURGER GAUCHE (OFF-CANVAS DRAWER EXACT COMME IMAGE 2) */
div[data-testid="stDialog"]:has(#burger-drawer-marker) > div:first-child {
    justify-content: flex-start !important;
    align-items: stretch !important;
    padding: 0 !important;
}

div[data-testid="stDialog"]:has(#burger-drawer-marker) div[role="dialog"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    bottom: 0 !important;
    height: 100vh !important;
    max-height: 100vh !important;
    width: 320px !important;
    max-width: 85vw !important;
    margin: 0 !important;
    border-radius: 0 16px 16px 0 !important;
    background: #FFFFFF !important;
    box-shadow: 6px 0 28px rgba(0, 0, 0, 0.25) !important;
    animation: drawerSlide 0.22s ease-out !important;
    overflow-y: auto !important;
    border: none !important;
    padding: 20px 18px !important;
}

@keyframes drawerSlide {
    from { transform: translateX(-100%); }
    to { transform: translateX(0); }
}

.drawer-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid #E2E8F0;
}

.drawer-nav-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    border-radius: 8px;
    color: #1E293B;
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 4px;
    cursor: pointer;
    transition: background 0.15s ease;
}

.drawer-nav-item:hover {
    background: #F1F5F9;
    color: #1D4ED8;
}

.drawer-nav-item.active {
    background: #EFF6FF;
    color: #1D4ED8;
    border-left: 4px solid #1D4ED8;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Message flash de validation persistant
if "flash_success" in st.session_state and st.session_state["flash_success"]:
    st.success(st.session_state["flash_success"])
    st.toast(st.session_state["flash_success"])
    del st.session_state["flash_success"]


# =============================================================
# GESTION DES UTILISATEURS & AUTHENTIFICATION
# =============================================================
def get_user_role():
    user = st.session_state.get("logged_user")
    if not user:
        return None
    return user.get("role", "parent").lower()

def is_admin():
    return get_user_role() == "admin"

def is_responsable_or_admin():
    return get_user_role() in ["admin", "responsable"]

# ----------------- VUE DE CONNEXION OBLIGATOIRE -----------------
if "logged_user" not in st.session_state or st.session_state["logged_user"] is None:
    st.markdown("""
        <div style="max-width: 480px; margin: 40px auto 20px auto; text-align: center;">
            <div style="font-size: 46px; margin-bottom: 8px;">🏕️</div>
            <h1 style="font-size: 26px; font-weight: 800; color: #0F172A; margin: 0;">Espace Ronde Farfadets</h1>
            <div style="font-size: 14px; color: #64748B; margin-top: 4px;">Scouts et Guides de France • Connexion sécurisée</div>
        </div>
    """, unsafe_allow_html=True)

    c_box_left, c_box_main, c_box_right = st.columns([1, 1.8, 1])
    with c_box_main:
        with st.container():
            st.markdown("""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 24px 28px; box-shadow: 0 4px 14px rgba(0,0,0,0.06); margin-bottom: 14px;">
                    <h3 style="margin-top:0; font-size:18px; color:#1E293B;">Connexion à votre espace</h3>
                    <p style="font-size:13px; color:#64748B; margin-bottom:18px;">Renseignez vos identifiants pour accéder aux données de votre ronde.</p>
                </div>
            """, unsafe_allow_html=True)

            users_list = db.get("utilisateurs", [])

            with st.form("form_auth_login"):
                u_email = st.text_input("Adresse e-mail", placeholder="votre.email@sgdf.fr")
                u_pwd = st.text_input("Mot de passe", type="password", placeholder="••••••••")
                btn_login = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

                if btn_login:
                    if not u_email or not u_pwd:
                        st.error("Veuillez renseigner votre adresse e-mail et votre mot de passe.")
                    else:
                        target_u = next((u for u in users_list if u.get("email", "").strip().lower() == u_email.strip().lower()), None)
                        if target_u and verify_password(u_pwd, target_u.get("mot_de_passe", "")):
                            # Mise à niveau automatique du hashage si le mot de passe était encore stocké en clair
                            if target_u.get("mot_de_passe") == u_pwd:
                                target_u["mot_de_passe"] = hash_password(u_pwd)
                                save_data(db)
                            st.session_state["logged_user"] = target_u
                            st.session_state["flash_success"] = f"Connexion réussie : Bienvenue {target_u.get('prenom')} {target_u.get('nom')} !"
                            st.rerun()
                        else:
                            st.error("Adresse e-mail ou mot de passe incorrect.")

            st.write("")
            with st.expander("🔑 Mot de passe oublié ? Réinitialiser votre mot de passe"):
                st.caption("Saisissez votre adresse e-mail pour définir un nouveau mot de passe sécurisé :")
                with st.form("form_auth_reset_pwd"):
                    r_email = st.text_input("Adresse e-mail de votre compte", placeholder="votre.email@sgdf.fr")
                    r_pwd1 = st.text_input("Nouveau mot de passe", type="password", placeholder="••••••••")
                    r_pwd2 = st.text_input("Confirmez le nouveau mot de passe", type="password", placeholder="••••••••")
                    btn_reset = st.form_submit_button("Enregistrer le nouveau mot de passe", type="primary", use_container_width=True)

                    if btn_reset:
                        if not r_email:
                            st.error("L'adresse e-mail est obligatoire.")
                        elif not r_pwd1 or len(r_pwd1) < 4:
                            st.error("Le mot de passe doit comporter au moins 4 caractères.")
                        elif r_pwd1 != r_pwd2:
                            st.error("Les deux mots de passe saisis ne sont pas identiques.")
                        else:
                            target_reset = next((u for u in users_list if u.get("email", "").strip().lower() == r_email.strip().lower()), None)
                            if not target_reset:
                                st.error("Aucun compte n'a été trouvé avec cette adresse e-mail.")
                            else:
                                target_reset["mot_de_passe"] = hash_password(r_pwd1)
                                save_data(db)
                                st.success("✅ Votre mot de passe a été réinitialisé ! Vous pouvez maintenant vous connecter ci-dessus.")

    st.stop()


logged_user = st.session_state.get("logged_user")
if not logged_user:
    st.stop()
    logged_user = {}


# DIALOG TIROIR BURGER GAUCHE CONFORME À L'IMAGE 2
@st.dialog("Menu de navigation", width="small")
def dialog_burger_menu():
    st.markdown('<div id="burger-drawer-marker"></div>', unsafe_allow_html=True)
    
    # En-tête du tiroir avec logo
    st.markdown(f"""
        <div class="drawer-header">
            <div style="font-size:28px;">🏕️</div>
            <div>
                <div style="font-weight:800; font-size:15px; color:#1E293B;">RONDE FARFADETS</div>
                <div style="font-size:12px; color:#64748B;">{current_ronde.get('groupe', 'Groupe SGDF')}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Menus de navigation
    nav_items = [
        ("🏠 Accueil", "🏠 Accueil"),
        ("📅 Planning des rencontres", "📅 Planning des rencontres"),
        ("👥 Farfadets & Familles", "👥 Farfadets & Familles"),
        ("✨ L'imaginaire de ronde", "✨ L'imaginaire de ronde"),
        ("📂 Documents & Supports", "📂 Documents & Supports"),
    ]
    # Seul l'Admin a accès aux paramètres de la ronde
    if is_admin():
        nav_items.append(("⚙️ Paramètres de la Ronde", "⚙️ Paramètres de la Ronde"))

    cur_nav = st.session_state.get("nav_page", "🏠 Accueil")
    for label, target_page in nav_items:
        is_active = (cur_nav == target_page)
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"drawer_btn_{target_page}", type=btn_type, use_container_width=True):
            st.session_state["nav_page"] = target_page
            st.session_state["active_editing_rencontre_id"] = None
            st.rerun()

    st.markdown("---")

    # SÉLECTEUR DE SESSION / RONDE DANS LE TIROIR (Conforme Image)
    st.markdown("""
        <div style="font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; margin-bottom: 6px;">
            Accès à vos sessions / ronde :
        </div>
    """, unsafe_allow_html=True)

    rondes_list = db.get("rondes", [])
    noms_rondes = [r["nom"] for r in rondes_list]
    cur_idx_r = next((i for i, r in enumerate(rondes_list) if r["id"] == current_ronde["id"]), 0)

    choix_ronde_drawer = st.selectbox(
        "Changer de ronde :", 
        noms_rondes, 
        index=cur_idx_r, 
        key="drawer_select_ronde", 
        label_visibility="collapsed"
    )
    selected_r_obj = next((r for r in rondes_list if r["nom"] == choix_ronde_drawer), None)
    if selected_r_obj and selected_r_obj["id"] != current_ronde["id"]:
        switch_ronde(selected_r_obj["id"])

    st.markdown("---")

    # Informations utilisateur & Déconnexion
    role_str = "Administrateur" if logged_user.get("role") == "admin" else ("Responsable Farfadets" if logged_user.get("role") == "responsable" else "Parent")
    st.markdown(f"""
        <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px; margin-bottom:12px;">
            <div style="font-weight:700; font-size:13px; color:#1E293B;">👤 {logged_user.get('prenom')} {logged_user.get('nom')}</div>
            <div style="font-size:11.5px; color:#1D4ED8; font-weight:600;">{role_str}</div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Se déconnecter", key="btn_logout_drawer", use_container_width=True):
        st.session_state["logged_user"] = None
        st.session_state["active_editing_rencontre_id"] = None
        st.session_state["flash_success"] = "Vous avez été déconnecté."
        st.rerun()


# =============================================================
# TOP NAVBAR CONFORME À L'IMAGE 1 (BURGER, TITRE, SÉLECTION, PROFIL)
# =============================================================
top_col1, top_col2, top_col3, top_col4 = st.columns([0.6, 4.5, 2.5, 2.8])

# 1. Bouton Burger qui ouvre le tiroir
with top_col1:
    if st.button("☰", key="top_burger_button", help="Ouvrir le menu de navigation"):
        dialog_burger_menu()

# 2. Logo et Nom de l'application
with top_col2:
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px; padding-top: 3px;">
            <div class="brand-badge-tag">
                <span>⛺</span> RONDE FARFADETS
            </div>
            <div>
                <div style="font-weight: 700; color: #1E293B; font-size: 13.5px; line-height: 1.2;">SCOUTS ET GUIDES DE FRANCE</div>
                <div style="font-size: 11.5px; color: #64748B;">{current_ronde.get('groupe', 'Groupe SGDF')} • {current_ronde.get('peuplade', 'Peuplade 6-8 ans')}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# 3. Sélecteur de Ronde direct dans la barre supérieure
with top_col3:
    rondes_list = db.get("rondes", [])
    noms_rondes = [r["nom"] for r in rondes_list]
    cur_idx_r = next((i for i, r in enumerate(rondes_list) if r["id"] == current_ronde["id"]), 0)
    
    choix_top_ronde = st.selectbox(
        "Ronde active :",
        noms_rondes,
        index=cur_idx_r,
        key="top_select_ronde",
        label_visibility="collapsed"
    )
    selected_r_top = next((r for r in rondes_list if r["nom"] == choix_top_ronde), None)
    if selected_r_top and selected_r_top["id"] != current_ronde["id"]:
        switch_ronde(selected_r_top["id"])

# 4. Badge Utilisateur & Bouton Déconnexion
with top_col4:
    user_role_label = "Admin" if logged_user.get("role") == "admin" else ("Respo" if logged_user.get("role") == "responsable" else "Parent")
    u_c1, u_c2 = st.columns([3, 1.2])
    with u_c1:
        st.markdown(f"""
            <div class="user-badge-btn" title="Connecté en tant que {logged_user.get('prenom')} {logged_user.get('nom')}">
                <span>👤</span> {logged_user.get('nom', '').upper()} {logged_user.get('prenom', '')} 
                <span class="role-tag-pill">{user_role_label}</span>
            </div>
        """, unsafe_allow_html=True)
    with u_c2:
        if st.button("Quitter", key="btn_top_logout", help="Se déconnecter"):
            st.session_state["logged_user"] = None
            st.session_state["flash_success"] = "Vous avez été déconnecté."
            st.rerun()


# =============================================================
# MODALES DÉDIÉES (ÉDITIONS & FORMULAIRES DE RENCONTRES)
# =============================================================

@st.dialog("➕ Créer une nouvelle ronde")
def dialog_creer_ronde():
    if not is_admin():
        st.error("Seul un administrateur peut créer une nouvelle ronde.")
        return
    st.write("Renseignez les informations de la nouvelle ronde :")
    with st.form("form_create_ronde", clear_on_submit=True):
        nom = st.text_input("Nom de la ronde", placeholder="Ex : Ronde 2 Farfadets - Sartrouville")
        saison = st.text_input("Saison / Année", value="2026 - 2027")
        groupe = st.text_input("Nom du groupe SGDF", placeholder="Ex : Groupe Saint Martin Sartrouville")
        lieu = st.text_input("Lieu habituel", placeholder="Ex : Local Scout - Notre Dame du Val")
        submitted = st.form_submit_button("Créer et activer la ronde", type="primary", use_container_width=True)
        if submitted:
            if not nom:
                st.error("Le nom de la ronde est obligatoire.")
            else:
                new_id = max([r["id"] for r in db["rondes"]], default=0) + 1
                new_ronde = {
                    "id": new_id,
                    "nom": nom,
                    "saison": saison,
                    "groupe": groupe or "Groupe SGDF",
                    "peuplade": "Branche scoute des 6 - 8 ans et leurs parents",
                    "lieu_habituel": lieu or "Local scout",
                    "membres": [],
                    "rencontres": [],
                    "imaginaire": "Bienvenue au village des Farfadets !",
                    "imaginaire_titre": "L'Aventure des Farfadets",
                    "imaginaire_photos": [],
                    "supports": []
                }
                db["rondes"].append(new_ronde)
                db["active_ronde_id"] = new_id
                st.session_state["active_ronde_id"] = new_id
                save_data(db)
                st.session_state["flash_success"] = f"✅ La ronde '{nom}' a été créée et activée !"
                st.rerun()

@st.dialog("⚙️ Paramètres de la ronde actuelle")
def dialog_parametres_ronde():
    if not is_admin():
        st.error("Réservé aux administrateurs.")
        return
    r = get_current_ronde()
    st.write(f"Modification des informations de : **{r['nom']}**")
    with st.form("form_update_ronde_modal", clear_on_submit=False):
        nom = st.text_input("Nom de la ronde", value=r.get("nom", ""))
        saison = st.text_input("Saison / Année", value=r.get("saison", ""))
        groupe = st.text_input("Groupe SGDF", value=r.get("groupe", ""))
        lieu = st.text_input("Lieu habituel", value=r.get("lieu_habituel", ""))
        submitted = st.form_submit_button("Enregistrer les modifications", type="primary", use_container_width=True)
        if submitted:
            r["nom"] = nom
            r["saison"] = saison
            r["groupe"] = groupe
            r["lieu_habituel"] = lieu
            save_data(db)
            st.session_state["flash_success"] = "✅ Paramètres de la ronde modifiés avec succès !"
            st.rerun()

    if len(db["rondes"]) > 1:
        st.markdown("---")
        if st.button("🗑️ Supprimer cette ronde", type="secondary", use_container_width=True):
            db["rondes"] = [x for x in db["rondes"] if x["id"] != r["id"]]
            db["active_ronde_id"] = db["rondes"][0]["id"]
            st.session_state["active_ronde_id"] = db["rondes"][0]["id"]
            save_data(db)
            st.session_state["flash_success"] = "🗑️ La ronde a été supprimée."
            st.rerun()

# ----------------- MODALE ÉDITION RENCONTRE COMPLÈTE -----------------
def on_dismiss_edit_rencontre():
    st.session_state["active_editing_rencontre_id"] = None

@st.dialog("⚙️ Configuration détaillée de la rencontre", width="large", on_dismiss=on_dismiss_edit_rencontre)
def dialog_modifier_rencontre(rencontre_id):
    r = next((x for x in current_ronde.get("rencontres", []) if x["id"] == rencontre_id), None)
    if not r:
        st.error("Rencontre introuvable.")
        if st.button("Fermer"):
            st.session_state["active_editing_rencontre_id"] = None
            st.rerun()
        return

    st.markdown(f"### 📌 Événement : **{r.get('titre')}**")
    
    MODAL_TABS = [
        "📋 Informations Générales", 
        "⏱️ Déroulé chronologique", 
        "🎒 Liste du Matériel & Photos", 
        "📝 Description & Objectifs"
    ]
    cur_tab_key = f"rencontre_modal_tab_{rencontre_id}"
    
    # Prise en compte d'une redirection forcée d'onglet (ex: après ajout ou modification de matériel)
    if f"_force_tab_{rencontre_id}" in st.session_state:
        st.session_state[cur_tab_key] = st.session_state.pop(f"_force_tab_{rencontre_id}")
        st.session_state[f"seg_nav_{rencontre_id}"] = st.session_state[cur_tab_key]
    elif cur_tab_key not in st.session_state or st.session_state[cur_tab_key] not in MODAL_TABS:
        st.session_state[cur_tab_key] = MODAL_TABS[0]
        st.session_state[f"seg_nav_{rencontre_id}"] = MODAL_TABS[0]

    def _on_subtab_change():
        val = st.session_state.get(f"seg_nav_{rencontre_id}")
        if val in MODAL_TABS:
            st.session_state[cur_tab_key] = val

    selected_subtab = st.segmented_control(
        "Onglet de configuration",
        options=MODAL_TABS,
        selection_mode="single",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key=f"seg_nav_{rencontre_id}",
        on_change=_on_subtab_change
    )
    cur_modal_tab = selected_subtab or st.session_state.get(cur_tab_key, MODAL_TABS[0])

    st.write("")

    # 1. INFORMATIONS GÉNÉRALES
    if cur_modal_tab == "📋 Informations Générales":
        with st.form(f"form_edit_r_gen_{rencontre_id}"):
            c1, c2 = st.columns(2)
            with c1:
                titre = st.text_input("Titre de la rencontre", value=r.get("titre", ""))
                type_opts = ["Rencontre ronde", "Sortie nature", "Réunion parents/animateurs", "Week-end de ronde"]
                type_idx = type_opts.index(r.get("type", "Rencontre ronde")) if r.get("type") in type_opts else 0
                type_r = st.selectbox("Type", type_opts, index=type_idx)
                d_val = parse_date_obj(r.get("date", date.today()))
                d_date = st.date_input("Date de la rencontre (JJ/MM/AAAA)", value=d_val, format="DD/MM/YYYY")
            with c2:
                horaire = st.text_input("Créneau horaire", value=r.get("horaire", "14:00 - 17:00"))
                animateur = st.text_input("Animateur principal", value=r.get("animateur", ""))
                statut_opts = ["À venir", "Terminé", "Annulé"]
                statut_idx = statut_opts.index(r.get("statut", "À venir")) if r.get("statut") in statut_opts else 0
                statut = st.selectbox("Statut", statut_opts, index=statut_idx)

            st.markdown("---")
            st.markdown("#### 📍 Lieu & Coordonnées GPS pour la Carte")
            c_lieu1, c_lieu2 = st.columns(2)
            with c_lieu1:
                lieu = st.text_input("Nom du lieu", value=r.get("lieu", ""))
                lieu_adr = st.text_input("Adresse complète du lieu", value=r.get("lieu_adresse", ""))
            with c_lieu2:
                lat = st.number_input("Latitude GPS", value=safe_float(r.get("lat"), 48.9417), format="%.5f")
                lon = st.number_input("Longitude GPS", value=safe_float(r.get("lon"), 2.1645), format="%.5f")

            if st.form_submit_button("Enregistrer les informations générales", type="primary", use_container_width=True):
                r["titre"] = titre
                r["type"] = type_r
                r["date"] = parse_date_to_iso(d_date)
                r["horaire"] = horaire
                r["animateur"] = animateur
                r["statut"] = statut
                r["lieu"] = lieu
                r["lieu_adresse"] = lieu_adr
                r["lat"] = lat
                r["lon"] = lon
                save_data(db)
                st.session_state[f"_force_tab_{rencontre_id}"] = "📋 Informations Générales"
                st.session_state[cur_tab_key] = "📋 Informations Générales"
                st.session_state["flash_success"] = f"✅ Rencontre mise à jour au {format_date_fr(r['date'])} !"
                st.rerun()

    # 2. DÉROULÉ CHRONOLOGIQUE (TABLEAU INTERACTIF AVEC ÉCRAN MODIFIER ET ÉCRAN AJOUTER)
    elif cur_modal_tab == "⏱️ Déroulé chronologique":
        st.markdown("#### ⏱️ Déroulé chronologique de la rencontre")
        deroule_list = r.get("deroule", [])
        custom_cols = r.setdefault("colonnes_deroule", [])
        mat_noms = [m.get("nom") for m in r.get("materiels", []) if m.get("nom")]

        cur_edit_step_key = f"editing_step_idx_{rencontre_id}"
        cur_add_step_key = f"adding_step_{rencontre_id}"
        editing_idx = st.session_state.get(cur_edit_step_key, None)
        is_adding = st.session_state.get(cur_add_step_key, False)

        # ÉCRAN 1 : MODIFICATION D'UNE LIGNE PRÉCISE DU TABLEAU
        if editing_idx is not None and 0 <= editing_idx < len(deroule_list):
            cur_s = deroule_list[editing_idx]
            
            c_back, c_title = st.columns([1.2, 4])
            with c_back:
                if st.button("← Retour au tableau", key=f"btn_back_step_edit_{rencontre_id}", use_container_width=True):
                    st.session_state[cur_edit_step_key] = None
                    st.rerun()
            with c_title:
                st.markdown(f"##### ✏️ Modifier l'étape {editing_idx + 1} : **{cur_s.get('activite', '')}**")
            
            with st.form(f"form_modify_step_{rencontre_id}_{editing_idx}"):
                col_ms1, col_ms2, col_ms3 = st.columns(3)
                with col_ms1:
                    m_s_date = st.date_input("Date de l'étape", value=parse_date_obj(cur_s.get("date", r.get("date", date.today()))), format="DD/MM/YYYY")
                    m_s_act = st.text_input("Activité *", value=cur_s.get("activite", ""))
                with col_ms2:
                    m_s_deb = st.text_input("Heure début", value=cur_s.get("heure_debut", "14:00"))
                    m_s_fin = st.text_input("Heure fin", value=cur_s.get("heure_fin", "14:30"))
                with col_ms3:
                    m_s_anim = st.text_input("Animateur", value=cur_s.get("animateur", ""))
                    current_step_mats = cur_s.get("materiels", [])
                    avail_mats = list(set(mat_noms + current_step_mats))
                    m_s_mats = st.multiselect("Matériels", options=avail_mats, default=[x for x in current_step_mats if x in avail_mats])

                m_s_com = st.text_input("Commentaire / Consigne", value=cur_s.get("commentaire", ""))

                m_custom_vals = {}
                if custom_cols:
                    st.markdown("###### Colonnes supplémentaires :")
                    cc_cols = st.columns(min(len(custom_cols), 3))
                    for ci, cname in enumerate(custom_cols):
                        with cc_cols[ci % 3]:
                            m_custom_vals[cname] = st.text_input(cname, value=str(cur_s.get(cname, "")), key=f"f_edit_c_{cname}_{editing_idx}")

                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    sub_edit = st.form_submit_button("💾 Enregistrer les modifications de la ligne", type="primary", use_container_width=True)
                with col_b2:
                    sub_cancel = st.form_submit_button("Annuler", use_container_width=True)

                if sub_cancel:
                    st.session_state[cur_edit_step_key] = None
                    st.rerun()

                if sub_edit:
                    if not m_s_act:
                        st.error("Le nom de l'activité est obligatoire.")
                    else:
                        cur_s["date"] = format_date_fr(m_s_date)
                        cur_s["activite"] = m_s_act
                        cur_s["heure_debut"] = m_s_deb
                        cur_s["heure_fin"] = m_s_fin
                        cur_s["animateur"] = m_s_anim
                        cur_s["materiels"] = m_s_mats
                        cur_s["commentaire"] = m_s_com
                        for cname, cval in m_custom_vals.items():
                            cur_s[cname] = cval
                        save_data(db)
                        st.session_state[cur_edit_step_key] = None
                        st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                        st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                        st.session_state["flash_success"] = f"✅ Étape '{m_s_act}' mise à jour dans le tableau !"
                        st.rerun()

            if st.button("🗑️ Supprimer cette étape du déroulé", key=f"btn_del_editing_step_{rencontre_id}", type="secondary"):
                deroule_list.pop(editing_idx)
                r["deroule"] = deroule_list
                save_data(db)
                st.session_state[cur_edit_step_key] = None
                st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                st.session_state["flash_success"] = "✅ Étape retirée du déroulé."
                st.rerun()

        # ÉCRAN 2 : SAISIE POUR AJOUTER UNE NOUVELLE LIGNE AU TABLEAU
        elif is_adding:
            c_back, c_title = st.columns([1.2, 4])
            with c_back:
                if st.button("← Retour au tableau", key=f"btn_back_step_add_{rencontre_id}", use_container_width=True):
                    st.session_state[cur_add_step_key] = False
                    st.rerun()
            with c_title:
                st.markdown(f"##### ➕ Ajouter une nouvelle étape à la suite du tableau")

            with st.form(f"form_add_step_{rencontre_id}", clear_on_submit=True):
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    step_date = st.date_input("Date de l'étape", value=parse_date_obj(r.get("date", date.today())), format="DD/MM/YYYY")
                    step_act = st.text_input("Nom de l'activité *", placeholder="Ex : Grand jeu de piste")
                with col_s2:
                    step_h_deb = st.text_input("Heure début *", value="14:00")
                    step_h_fin = st.text_input("Heure fin *", value="14:30")
                with col_s3:
                    step_anim = st.text_input("Animateur en charge", value=r.get("animateur", ""))
                    step_mats = st.multiselect("Matériels nécessaires", options=mat_noms if mat_noms else ["Foulards", "Goûter", "Boussoles"])
                
                step_com = st.text_input("Commentaire / Consigne d'animation", placeholder="Ex : Diviser la ronde en deux équipes")

                new_custom_vals = {}
                if custom_cols:
                    st.markdown("###### Colonnes supplémentaires :")
                    cc_cols_add = st.columns(min(len(custom_cols), 3))
                    for ci, cname in enumerate(custom_cols):
                        with cc_cols_add[ci % 3]:
                            new_custom_vals[cname] = st.text_input(cname, placeholder=f"Valeur pour {cname}", key=f"f_add_c_{cname}")

                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    sub_add = st.form_submit_button("➕ Valider et ajouter la ligne au tableau", type="primary", use_container_width=True)
                with col_b2:
                    sub_canc_add = st.form_submit_button("Annuler", use_container_width=True)

                if sub_canc_add:
                    st.session_state[cur_add_step_key] = False
                    st.rerun()

                if sub_add:
                    if not step_act:
                        st.error("Le nom de l'activité est obligatoire.")
                    else:
                        new_step = {
                            "date": format_date_fr(step_date),
                            "heure_debut": step_h_deb,
                            "heure_fin": step_h_fin,
                            "activite": step_act,
                            "animateur": step_anim,
                            "materiels": step_mats,
                            "commentaire": step_com
                        }
                        for cname, cval in new_custom_vals.items():
                            new_step[cname] = cval
                        r.setdefault("deroule", []).append(new_step)
                        save_data(db)
                        st.session_state[cur_add_step_key] = False
                        st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                        st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                        st.session_state["flash_success"] = f"✅ Étape '{step_act}' ajoutée au déroulé !"
                        st.rerun()

        # ÉCRAN 3 : AFFICHAGE DU TABLEAU AVEC ACTIONS SUR CHAQUE LIGNE ET BOUTON D'AJOUT À LA SUITE
        else:
            with st.expander("⚙️ Personnaliser les colonnes du tableau (Ajouter / Supprimer des colonnes)"):
                st.caption("Vous pouvez ajouter des colonnes supplémentaires pour stocker toute information nécessaire (ex: Lieu précis, Consigne sécurité, Météo...).")
                if custom_cols:
                    st.write("**Colonnes personnalisées actives :**")
                    for c_idx, col_name in enumerate(custom_cols):
                        cc1, cc2 = st.columns([4, 1])
                        cc1.write(f"• **{col_name}**")
                        if cc2.button("Supprimer", key=f"del_col_{rencontre_id}_{c_idx}"):
                            custom_cols.pop(c_idx)
                            r["colonnes_deroule"] = custom_cols
                            save_data(db)
                            st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                            st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                            st.rerun()
                
                with st.form(f"form_add_col_{rencontre_id}", clear_on_submit=True):
                    nc_name = st.text_input("Nom de la nouvelle colonne", placeholder="Ex : Lieu précis")
                    if st.form_submit_button("➕ Ajouter cette colonne au tableau", type="primary"):
                        if nc_name and nc_name.strip():
                            clean_nc = nc_name.strip()
                            if clean_nc not in custom_cols and clean_nc not in ["Date", "Début", "Fin", "Activité", "Animateur", "Matériels", "Commentaire"]:
                                custom_cols.append(clean_nc)
                                r["colonnes_deroule"] = custom_cols
                                save_data(db)
                                st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                                st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                                st.session_state["flash_success"] = f"✅ Colonne '{clean_nc}' ajoutée !"
                                st.rerun()
                            else:
                                st.warning("Cette colonne existe déjà ou est un champ par défaut.")

            if deroule_list:
                st.markdown("""
                    <div style="background:#F1F5F9; border:1px solid #CBD5E1; border-radius:8px 8px 0 0; padding:10px 12px; font-weight:700; font-size:13px; color:#1E293B; margin-bottom:4px;">
                        <div style="display:flex; align-items:center;">
                            <div style="width:6%;">#</div>
                            <div style="width:16%;">Horaires</div>
                            <div style="width:26%;">Activité & Détails</div>
                            <div style="width:16%;">Animateur</div>
                            <div style="width:18%;">Matériels</div>
                            <div style="width:18%; text-align:right;">Actions</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                for idx, s in enumerate(deroule_list):
                    c_row = st.container()
                    with c_row:
                        c_num, c_hor, c_act, c_anim, c_mat, c_btn = st.columns([0.6, 1.5, 2.4, 1.4, 1.6, 1.7])
                        with c_num:
                            st.markdown(f"**#{idx + 1}**")
                        with c_hor:
                            st.markdown(f"**{s.get('heure_debut', '')} - {s.get('heure_fin', '')}**")
                            st.caption(s.get("date", format_date_fr(r.get("date"))))
                        with c_act:
                            st.markdown(f"**{s.get('activite', '')}**")
                            if s.get("commentaire"):
                                st.caption(f"💬 {s.get('commentaire')}")
                            for cc in custom_cols:
                                if s.get(cc):
                                    st.caption(f"🔹 *{cc}* : {s.get(cc)}")
                        with c_anim:
                            anim_name = s.get("animateur") or "-"
                            st.markdown(f"🏕️ {anim_name}")
                        with c_mat:
                            mats_step = s.get("materiels", [])
                            if mats_step:
                                mats_txt = ", ".join(mats_step)
                                st.markdown(f'<span style="background:#EFF6FF; color:#1D4ED8; font-size:11px; padding:2px 6px; border-radius:4px; font-weight:600;">🎒 {mats_txt}</span>', unsafe_allow_html=True)
                            else:
                                st.caption("Aucun")
                        with c_btn:
                            cb1, cb2 = st.columns([2, 1])
                            with cb1:
                                if st.button("✏️ Modifier", key=f"btn_edit_step_line_{rencontre_id}_{idx}", use_container_width=True):
                                    st.session_state[cur_edit_step_key] = idx
                                    st.session_state[cur_add_step_key] = False
                                    st.rerun()
                            with cb2:
                                if st.button("🗑️", key=f"btn_del_step_line_{rencontre_id}_{idx}", use_container_width=True, help="Supprimer cette étape"):
                                    deroule_list.pop(idx)
                                    r["deroule"] = deroule_list
                                    save_data(db)
                                    st.session_state[f"_force_tab_{rencontre_id}"] = "⏱️ Déroulé chronologique"
                                    st.session_state[cur_tab_key] = "⏱️ Déroulé chronologique"
                                    st.session_state["flash_success"] = "🗑️ Étape supprimée."
                                    st.rerun()
                        st.markdown('<hr style="margin:4px 0 8px 0; border:0; border-top:1px solid #E2E8F0;">', unsafe_allow_html=True)
            else:
                st.info("Aucune étape dans le déroulé de cette rencontre.")

            # BOUTON AJOUTER À LA SUITE DU TABLEAU
            st.write("")
            if st.button("➕ Ajouter une étape à la suite du tableau", type="primary", use_container_width=True, key=f"btn_trigger_add_step_{rencontre_id}"):
                st.session_state[cur_add_step_key] = True
                st.session_state[cur_edit_step_key] = None
                st.rerun()

    # 3. LISTE DU MATÉRIEL (TABLEAU INTERACTIF AVEC ÉCRAN MODIFIER ET ÉCRAN AJOUTER)
    elif cur_modal_tab == "🎒 Liste du Matériel & Photos":
        st.markdown("#### 🎒 Matériels de la rencontre")
        mats_list = r.get("materiels", [])
        membres_noms = [f"{mb['prenom']} {mb['nom']}" for mb in current_ronde.get("membres", [])]
        qui_options = ["Parents", "Animateurs", "Tous"] + membres_noms

        cur_edit_mat_key = f"editing_mat_idx_{rencontre_id}"
        cur_add_mat_key = f"adding_mat_{rencontre_id}"
        editing_m_idx = st.session_state.get(cur_edit_mat_key, None)
        is_adding_mat = st.session_state.get(cur_add_mat_key, False)

        # ÉCRAN 1 : MODIFIER UN MATÉRIEL EXISTANT
        if editing_m_idx is not None and 0 <= editing_m_idx < len(mats_list):
            m = mats_list[editing_m_idx]
            c_back, c_title = st.columns([1.2, 4])
            with c_back:
                if st.button("← Retour au tableau", key=f"btn_back_mat_edit_{rencontre_id}", use_container_width=True):
                    st.session_state[cur_edit_mat_key] = None
                    st.rerun()
            with c_title:
                st.markdown(f"##### ✏️ Modifier le matériel : **{m.get('nom', '')}**")

            with st.form(f"form_edit_mat_{rencontre_id}_{editing_m_idx}"):
                em1, em2 = st.columns(2)
                with em1:
                    edit_m_nom = st.text_input("Nom du matériel *", value=m.get("nom", ""))
                    q_idx = qui_options.index(m.get("qui_amene")) if m.get("qui_amene") in qui_options else 0
                    edit_m_qui = st.selectbox("Qui l'amène ?", options=qui_options, index=q_idx)
                with em2:
                    edit_m_rem = st.text_input("Quantité / Précision", value=m.get("remarque", m.get("quantite", "")))
                    edit_m_file = st.file_uploader("Photo du matériel", type=["png", "jpg", "jpeg"], key=f"f_mat_up_{rencontre_id}_{editing_m_idx}")
                    edit_m_url = st.text_input("Ou lien / URL de l'image", value=m.get("photo", "") if not m.get("photo", "").startswith("data:") else "", key=f"f_mat_url_{rencontre_id}_{editing_m_idx}")
                
                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    sub_m_edit = st.form_submit_button("💾 Enregistrer les modifications du matériel", type="primary", use_container_width=True)
                with col_b2:
                    sub_m_canc = st.form_submit_button("Annuler", use_container_width=True)

                if sub_m_canc:
                    st.session_state[cur_edit_mat_key] = None
                    st.rerun()

                if sub_m_edit:
                    if not edit_m_nom:
                        st.error("Le nom du matériel est requis.")
                    else:
                        m["nom"] = edit_m_nom
                        m["qui_amene"] = edit_m_qui
                        m["remarque"] = edit_m_rem
                        m["quantite"] = edit_m_rem
                        if edit_m_file is not None:
                            m["photo"] = file_to_base64(edit_m_file)
                        elif edit_m_url:
                            m["photo"] = edit_m_url
                        save_data(db)
                        st.session_state[cur_edit_mat_key] = None
                        st.session_state[f"_force_tab_{rencontre_id}"] = "🎒 Liste du Matériel & Photos"
                        st.session_state[cur_tab_key] = "🎒 Liste du Matériel & Photos"
                        st.session_state["flash_success"] = f"✅ Matériel '{edit_m_nom}' mis à jour !"
                        st.rerun()

            if st.button("🗑️ Supprimer ce matériel", key=f"del_mat_editing_{rencontre_id}", type="secondary"):
                mats_list.pop(editing_m_idx)
                r["materiels"] = mats_list
                save_data(db)
                st.session_state[cur_edit_mat_key] = None
                st.session_state[f"_force_tab_{rencontre_id}"] = "🎒 Liste du Matériel & Photos"
                st.session_state[cur_tab_key] = "🎒 Liste du Matériel & Photos"
                st.session_state["flash_success"] = "✅ Matériel supprimé."
                st.rerun()

        # ÉCRAN 2 : AJOUTER UN NOUVEAU MATÉRIEL
        elif is_adding_mat:
            c_back, c_title = st.columns([1.2, 4])
            with c_back:
                if st.button("← Retour au tableau", key=f"btn_back_mat_add_{rencontre_id}", use_container_width=True):
                    st.session_state[cur_add_mat_key] = False
                    st.rerun()
            with c_title:
                st.markdown("##### ➕ Ajouter un nouveau matériel au tableau")

            with st.form(f"form_add_mat_{rencontre_id}", clear_on_submit=True):
                col_add_m1, col_add_m2 = st.columns(2)
                with col_add_m1:
                    m_nom = st.text_input("Nom du matériel *", placeholder="Ex : 10 boussoles et 5 balises")
                    m_qui = st.selectbox("Qui l'amène ?", options=qui_options)
                with col_add_m2:
                    m_rem = st.text_input("Quantité / Remarque", placeholder="Ex : 1 par sizaine")
                    m_file = st.file_uploader("Photo du matériel (optionnel)", type=["png", "jpg", "jpeg"])
                    m_url = st.text_input("Ou lien de l'image / photo", placeholder="https://...")

                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    sub_m_add = st.form_submit_button("➕ Valider et ajouter le matériel au tableau", type="primary", use_container_width=True)
                with col_b2:
                    sub_m_add_canc = st.form_submit_button("Annuler", use_container_width=True)

                if sub_m_add_canc:
                    st.session_state[cur_add_mat_key] = False
                    st.rerun()

                if sub_m_add:
                    if not m_nom:
                        st.error("Le nom du matériel est requis.")
                    else:
                        photo_val = file_to_base64(m_file) or m_url or ""
                        r.setdefault("materiels", []).append({
                            "id": len(mats_list) + 1,
                            "nom": m_nom,
                            "qui_amene": m_qui,
                            "remarque": m_rem,
                            "quantite": m_rem,
                            "photo": photo_val
                        })
                        save_data(db)
                        st.session_state[cur_add_mat_key] = False
                        st.session_state[f"_force_tab_{rencontre_id}"] = "🎒 Liste du Matériel & Photos"
                        st.session_state[cur_tab_key] = "🎒 Liste du Matériel & Photos"
                        st.session_state["flash_success"] = f"✅ Matériel '{m_nom}' ajouté à la rencontre !"
                        st.rerun()

        # ÉCRAN 3 : AFFICHAGE DU TABLEAU DU MATÉRIEL AVEC ACTIONS SUR CHAQUE LIGNE ET BOUTON D'AJOUT À LA SUITE
        else:
            if mats_list:
                st.markdown("""
                    <div style="background:#F1F5F9; border:1px solid #CBD5E1; border-radius:8px 8px 0 0; padding:10px 12px; font-weight:700; font-size:13px; color:#1E293B; margin-bottom:4px;">
                        <div style="display:flex; align-items:center;">
                            <div style="width:10%;">Photo</div>
                            <div style="width:32%;">Nom du matériel</div>
                            <div style="width:22%;">Qui l'amène ?</div>
                            <div style="width:20%;">Quantité / Remarque</div>
                            <div style="width:16%; text-align:right;">Actions</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                for m_idx, m in enumerate(mats_list):
                    c_row = st.container()
                    with c_row:
                        c_ph, c_name, c_qui, c_rem, c_act = st.columns([1, 3.2, 2.2, 2, 1.6])
                        with c_ph:
                            if m.get("photo"):
                                st.markdown(f'<img src="{m["photo"]}" style="width:40px; height:40px; object-fit:cover; border-radius:6px; border:1px solid #CBD5E1;">', unsafe_allow_html=True)
                            else:
                                st.markdown('<div style="width:40px; height:40px; background:#EFF6FF; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size:20px;">📦</div>', unsafe_allow_html=True)
                        with c_name:
                            st.markdown(f"**{m.get('nom', '')}**")
                        with c_qui:
                            st.markdown(f'<span style="background:#DBEAFE; color:#1E40AF; font-size:11.5px; font-weight:600; padding:2px 8px; border-radius:12px;">👤 {m.get("qui_amene", "Non assigné")}</span>', unsafe_allow_html=True)
                        with c_rem:
                            rem_text = m.get("remarque") or m.get("quantite") or "-"
                            st.caption(rem_text)
                        with c_act:
                            cb1, cb2 = st.columns([2, 1])
                            with cb1:
                                if st.button("✏️ Modifier", key=f"btn_edit_mat_row_{rencontre_id}_{m_idx}", use_container_width=True):
                                    st.session_state[cur_edit_mat_key] = m_idx
                                    st.session_state[cur_add_mat_key] = False
                                    st.rerun()
                            with cb2:
                                if st.button("🗑️", key=f"btn_del_mat_row_{rencontre_id}_{m_idx}", use_container_width=True, help="Supprimer ce matériel"):
                                    mats_list.pop(m_idx)
                                    r["materiels"] = mats_list
                                    save_data(db)
                                    st.session_state[f"_force_tab_{rencontre_id}"] = "🎒 Liste du Matériel & Photos"
                                    st.session_state[cur_tab_key] = "🎒 Liste du Matériel & Photos"
                                    st.session_state["flash_success"] = "🗑️ Matériel supprimé."
                                    st.rerun()
                        st.markdown('<hr style="margin:4px 0 8px 0; border:0; border-top:1px solid #E2E8F0;">', unsafe_allow_html=True)
            else:
                st.info("Aucun matériel enregistré pour cette rencontre.")

            st.write("")
            if st.button("➕ Ajouter un matériel à la suite du tableau", type="primary", use_container_width=True, key=f"btn_trigger_add_mat_{rencontre_id}"):
                st.session_state[cur_add_mat_key] = True
                st.session_state[cur_edit_mat_key] = None
                st.rerun()

    # 4. DESCRIPTION & OBJECTIFS
    elif cur_modal_tab == "📝 Description & Objectifs":
        st.markdown("#### 📝 Description & Thématique de la séance")
        with st.form(f"form_pedago_{rencontre_id}"):
            desc_val = st.text_area("Description détaillée de la rencontre", value=r.get("description", ""), height=100)
            im_val = st.text_area("Cadre imaginaire de cette séance", value=r.get("imaginaire_rencontre", ""), height=100)
            obj_val = st.text_area("Objectifs pédagogiques", value=r.get("objectifs", ""), height=90)
            
            c_p_img1, c_p_img2 = st.columns(2)
            with c_p_img1:
                p_file = st.file_uploader("Photo / Illustration de la rencontre", type=["png", "jpg", "jpeg"])
            with c_p_img2:
                p_url = st.text_input("Ou URL de la photo d'illustration", value=r.get("photo", "") if not r.get("photo", "").startswith("data:") else "")

            if st.form_submit_button("Enregistrer la description et les objectifs", type="primary", use_container_width=True):
                r["description"] = desc_val
                r["imaginaire_rencontre"] = im_val
                r["objectifs"] = obj_val
                if p_file is not None:
                    r["photo"] = file_to_base64(p_file)
                elif p_url:
                    r["photo"] = p_url
                save_data(db)
                st.session_state[f"_force_tab_{rencontre_id}"] = "📝 Description & Objectifs"
                st.session_state[cur_tab_key] = "📝 Description & Objectifs"
                st.session_state["flash_success"] = "✅ Pédagogie et photos de la rencontre mises à jour !"
                st.rerun()

    st.write("")
    st.markdown("---")
    c_close1, c_close2 = st.columns([3, 1])
    with c_close2:
        if st.button("✖️ Fermer la fenêtre", key=f"btn_close_dialog_{rencontre_id}", use_container_width=True):
            st.session_state["active_editing_rencontre_id"] = None
            st.rerun()

@st.dialog("🗑️ Supprimer la rencontre")
def dialog_supprimer_rencontre(rencontre_id):
    r = next((x for x in current_ronde["rencontres"] if x["id"] == rencontre_id), None)
    if not r:
        st.error("Rencontre introuvable.")
        return
    st.warning(f"Êtes-vous sûr de vouloir supprimer définitivement la rencontre : **{r.get('titre')}** du {format_date_fr(r.get('date'))} ?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmer la suppression", type="primary", use_container_width=True):
            current_ronde["rencontres"] = [x for x in current_ronde["rencontres"] if x["id"] != rencontre_id]
            save_data(db)
            st.session_state["flash_success"] = "🗑️ Rencontre supprimée."
            st.rerun()
    with c2:
        if st.button("Annuler", use_container_width=True):
            st.rerun()

# ----------------- MODALES MEMBRES -----------------
@st.dialog("✏️ Modifier le membre")
def dialog_modifier_membre(membre_id):
    m = next((x for x in current_ronde["membres"] if x["id"] == membre_id), None)
    if not m:
        st.error("Membre introuvable.")
        return
    with st.form(f"form_edit_m_{membre_id}"):
        prenom = st.text_input("Prénom", value=m.get("prenom", ""))
        nom = st.text_input("Nom", value=m.get("nom", ""))
        roles = ["Enfant", "Parent", "Responsable", "Invité"]
        idx_r = roles.index(m.get("role", "Enfant")) if m.get("role") in roles else 0
        role = st.selectbox("Rôle", roles, index=idx_r)
        contact = st.text_input("Contact", value=m.get("contact", ""))
        initiales = st.text_input("Initiales avatar (2 lettres)", value=m.get("photo", f"{prenom[:1]}{nom[:1]}".upper()), max_chars=3)
        if st.form_submit_button("Sauvegarder", type="primary", use_container_width=True):
            m["prenom"] = prenom
            m["nom"] = nom
            m["role"] = role
            m["contact"] = contact
            m["photo"] = initiales
            save_data(db)
            st.session_state["flash_success"] = f"✅ Membre {prenom} {nom} mis à jour !"
            st.rerun()

@st.dialog("🗑️ Supprimer le membre")
def dialog_supprimer_membre(membre_id):
    m = next((x for x in current_ronde["membres"] if x["id"] == membre_id), None)
    if not m:
        st.error("Membre introuvable.")
        return
    st.warning(f"Supprimer le membre **{m.get('prenom')} {m.get('nom')}** ({m.get('role')}) ?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmer", type="primary", use_container_width=True):
            current_ronde["membres"] = [x for x in current_ronde["membres"] if x["id"] != membre_id]
            save_data(db)
            st.session_state["flash_success"] = "🗑️ Membre supprimé."
            st.rerun()
    with c2:
        if st.button("Annuler", use_container_width=True):
            st.rerun()

@st.dialog("➕ Inscrire un membre")
def dialog_inscrire_membre():
    with st.form("form_dialog_add_member", clear_on_submit=True):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            p_prenom = st.text_input("Prénom *")
            p_nom = st.text_input("Nom *")
        with col_p2:
            p_role = st.selectbox("Rôle", ["Enfant", "Parent", "Responsable", "Invité"])
            p_contact = st.text_input("Contact (tél ou email)")

        if st.form_submit_button("Ajouter à la ronde", type="primary", use_container_width=True):
            if p_prenom and p_nom:
                new_m_id = max([x["id"] for x in current_ronde.get("membres", [])], default=0) + 1
                current_ronde.setdefault("membres", []).append({
                    "id": new_m_id,
                    "prenom": p_prenom,
                    "nom": p_nom,
                    "role": p_role,
                    "contact": p_contact,
                    "photo": f"{p_prenom[:1]}{p_nom[:1]}".upper()
                })
                save_data(db)
                st.session_state["flash_success"] = f"✅ Membre {p_prenom} {p_nom} ajouté avec succès !"
                st.rerun()
            else:
                st.error("Le prénom et le nom sont obligatoires.")

# ----------------- MODALES DOCUMENTS -----------------
@st.dialog("✏️ Modifier le document / support")
def dialog_modifier_support(support_id):
    s = next((x for x in current_ronde["supports"] if x.get("id") == support_id), None)
    if not s:
        st.error("Support introuvable.")
        return
    with st.form(f"form_edit_sup_{support_id}"):
        titre = st.text_input("Titre", value=s.get("titre", ""))
        url = st.text_input("Lien / URL", value=s.get("url", ""))
        desc = st.text_input("Description", value=s.get("desc", ""))
        cats = ["Pédagogie", "Animation", "Chants", "Cadre légal", "Autre"]
        idx_c = cats.index(s.get("categorie", "Pédagogie")) if s.get("categorie") in cats else 0
        cat = st.selectbox("Catégorie", cats, index=idx_c)
        
        up_img = st.file_uploader("Téléverser une image d'icône (PNG, JPG)", type=["png", "jpg", "jpeg"])
        url_img = st.text_input("Ou URL de l'icône/image", value=s.get("icone_image", "") if not s.get("icone_image", "").startswith("data:") else "")

        if st.form_submit_button("Sauvegarder", type="primary", use_container_width=True):
            s["titre"] = titre
            s["url"] = url
            s["desc"] = desc
            s["categorie"] = cat
            if up_img is not None:
                s["icone_image"] = file_to_base64(up_img)
            elif url_img:
                s["icone_image"] = url_img
            save_data(db)
            st.session_state["flash_success"] = f"✅ Document '{titre}' mis à jour !"
            st.rerun()

@st.dialog("🗑️ Supprimer le document")
def dialog_supprimer_support(support_id):
    s = next((x for x in current_ronde["supports"] if x.get("id") == support_id), None)
    if not s:
        st.error("Support introuvable.")
        return
    st.warning(f"Supprimer la ressource **{s.get('titre')}** ?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmer", type="primary", use_container_width=True):
            current_ronde["supports"] = [x for x in current_ronde["supports"] if x.get("id") != support_id]
            save_data(db)
            st.session_state["flash_success"] = "🗑️ Document supprimé."
            st.rerun()
    with c2:
        if st.button("Annuler", use_container_width=True):
            st.rerun()


# =============================================================
# FONCTIONS DE RENDU DU CALENDRIER ET CARTE MAPS
# =============================================================
def get_month_name(m):
    mois = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", 
            "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]
    return mois[m - 1]

def build_calendar_html_table(year, month, rencontres_list):
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)
    today_str = date.today().isoformat()
    
    evts_by_date = {}
    for r in rencontres_list:
        d_iso = parse_date_to_iso(r.get("date"))
        if d_iso:
            evts_by_date.setdefault(d_iso, []).append(r)
            
    rows = []
    for week in weeks:
        cells = []
        for day in week:
            is_cur = (day.month == month)
            day_str = day.strftime("%Y-%m-%d")
            cls_num = "cal-day-header" if is_cur else "cal-day-header muted"
            cls_td = "today-cell" if day_str == today_str else ""
            
            badges = []
            if day_str in evts_by_date:
                for ev in evts_by_date[day_str]:
                    h = ev.get("horaire", "14:00 - 17:00")
                    t = ev.get("titre", "Rencontre")
                    badges.append(f'<span class="cal-slot-badge" title="{t}">{h}</span>')
            
            badges_html = "".join(badges)
            cells.append(f'<td class="{cls_td}"><div class="{cls_num}">{day.day}</div>{badges_html}</td>')
            
        rows.append(f'<tr>{"".join(cells)}</tr>')
        
    table_body = "".join(rows)
    table_html = (
        '<div class="cal-scroll-area">'
        '<table class="cal-grid-table">'
        '<thead><tr>'
        '<th>lun.</th><th>mar.</th><th>mer.</th><th>jeu.</th><th>ven.</th><th>sam.</th><th>dim.</th>'
        '</tr></thead>'
        f'<tbody>{table_body}</tbody>'
        '</table>'
        '</div>'
    )
    return table_html

def render_map_card_html(nom_lieu, adresse, lat, lon):
    return f"""
    <div class="map-card-box">
        <div class="map-header">
            <div class="card-icon-bubble" style="background:#1D4ED8;">📍</div>
            <div>
                <div class="map-title">{nom_lieu}</div>
                <div class="map-address">{adresse}</div>
            </div>
        </div>
        <div class="map-frame-wrapper">
            <iframe 
                width="100%" 
                height="220" 
                frameborder="0" 
                scrolling="no" 
                marginheight="0" 
                marginwidth="0" 
                src="https://www.openstreetmap.org/export/embed.html?bbox={lon-0.014}%2C{lat-0.009}%2C{lon+0.014}%2C{lat+0.009}&amp;layer=mapnik&amp;marker={lat}%2C{lon}" 
                style="border:0;"
            ></iframe>
        </div>
        <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:11.5px; color:#64748B;">GPS : {lat:.4f}, {lon:.4f}</span>
            <a href="https://www.google.com/maps/search/?api=1&query={lat},{lon}" target="_blank" style="font-size:12px; color:#1D4ED8; text-decoration:none; font-weight:700;">Ouvrir sur Google Maps ↗</a>
        </div>
    </div>
    """


# =============================================================
# ROUTAGE DES PAGES (SELON NAVIGATION ET DROITS)
# =============================================================

# Si un non-admin tente d'accéder à la configuration, redirection
if st.session_state["nav_page"] == "⚙️ Paramètres de la Ronde" and not is_admin():
    st.session_state["nav_page"] = "🏠 Accueil"
    st.warning("Accès restreint aux administrateurs.")
    st.rerun()


# =============================================================
# 1. PAGE ACCUEIL
# =============================================================
if st.session_state["nav_page"] == "🏠 Accueil":
    st.markdown(f"""
        <div class="hero-header-card">
            <h1 class="hero-main-title">{current_ronde.get('nom', 'Ronde Farfadets')}</h1>
            <div class="hero-sub-title">Saison {current_ronde.get('saison', '2026 - 2027')}</div>
            <span class="hero-badge-tag">{current_ronde.get('peuplade', 'Branche scoute des 6 - 8 ans et leurs parents')} • {current_ronde.get('lieu_habituel', 'Local')}</span>
        </div>
    """, unsafe_allow_html=True)

    today_str = str(date.today())
    futures = [r for r in current_ronde.get("rencontres", []) if parse_date_to_iso(r.get("date", "")) >= today_str]
    futures = sorted(futures, key=lambda x: parse_date_to_iso(x.get("date", "")))
    prochaine = futures[0] if futures else (current_ronde["rencontres"][0] if current_ronde.get("rencontres") else None)

    col_main_left, col_main_right = st.columns(2, gap="medium")

    with col_main_left:
        # 1. Prochaine rencontre
        if prochaine:
            date_fr = format_date_fr(prochaine.get("date"))
            st.markdown(f"""
                <div class="dashboard-card">
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div class="card-icon-bubble">⭐</div>
                        <div>
                            <div class="card-title">Prochaine rencontre : {date_fr}</div>
                            <div class="card-subtitle">{prochaine.get('titre')} ({prochaine.get('horaire', '14:00 - 17:00')})</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div class="dashboard-card">
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div class="card-icon-bubble">⭐</div>
                        <div>
                            <div class="card-title">Aucune rencontre programmée</div>
                            <div class="card-subtitle">Planifiez une nouvelle date dans l'onglet Planning</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # 2. Carte & Accès au lieu de rencontre
        if prochaine:
            p_lieu = prochaine.get("lieu") or current_ronde.get("lieu_habituel") or "Local Scout"
            p_adresse = prochaine.get("lieu_adresse") or p_lieu
            p_lat = safe_float(prochaine.get("lat"), 48.9417)
            p_lon = safe_float(prochaine.get("lon"), 2.1645)
            st.markdown(render_map_card_html(p_lieu, p_adresse, p_lat, p_lon), unsafe_allow_html=True)
        else:
            p_lieu = current_ronde.get("lieu_habituel", "Local Scout")
            st.markdown(render_map_card_html(p_lieu, "Notre Dame du Val, Sartrouville", 48.9417, 2.1645), unsafe_allow_html=True)

        # 3. Vos Animateurs (responsables de ronde)
        st.markdown("""
            <div class="speakers-header" style="margin-top:2px;">
                <div class="card-icon-bubble" style="background:#1D4ED8;">👤</div>
                <div>
                    <div class="card-title" style="font-size:16px;">Vos animateurs</div>
                    <div class="card-subtitle">Responsables de ronde & animateurs référents</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        respos = [m for m in current_ronde.get("membres", []) if m.get("role") == "Responsable"]
        if respos:
            cols_respos = st.columns(min(len(respos), 3))
            for i, r_resp in enumerate(respos):
                with cols_respos[i % 3]:
                    st.markdown(f"""
                        <div class="speaker-profile-box">
                            <div class="speaker-avatar-circle">{r_resp.get('photo', 'AN')}</div>
                            <div class="speaker-name">{r_resp.get('nom', '')}<br>{r_resp.get('prenom', '')}</div>
                            <div class="speaker-role">Animateur Farfadet</div>
                            <div style="font-size:11px; color:#1D4ED8; margin-top:3px;">{r_resp.get('contact', '')}</div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Aucun responsable enregistré.")

    with col_main_right:
        # 1. Documents & Supports (hauteur alignée sur la Prochaine Rencontre)
        nb_docs = len(current_ronde.get("supports", []))
        st.markdown(f"""
            <div class="dashboard-card">
                <div style="display:flex; align-items:center; gap:16px;">
                    <div class="card-icon-bubble">📁</div>
                    <div>
                        <div class="card-title">Documents & Supports</div>
                        <div class="card-subtitle">{nb_docs} ressources pédagogiques disponibles</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # 2. Calendrier mensuel des rencontres
        st.markdown("""
            <div class="cal-header-top">
                <div class="card-icon-bubble" style="background:#1D4ED8;">📅</div>
                <div>
                    <div class="card-title" style="font-size:16px;">Calendrier de la Ronde</div>
                    <div class="card-subtitle">Vos créneaux de rencontres</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        nav_c1, nav_c2, nav_c3 = st.columns([1, 5, 1])
        with nav_c1:
            if st.button("◀", key="nav_cal_left", use_container_width=True):
                if st.session_state["cal_month"] == 1:
                    st.session_state["cal_month"] = 12
                    st.session_state["cal_year"] -= 1
                else:
                    st.session_state["cal_month"] -= 1
                st.rerun()
        with nav_c2:
            st.markdown(f'<div class="cal-nav-title">{get_month_name(st.session_state["cal_month"])} {st.session_state["cal_year"]}</div>', unsafe_allow_html=True)
        with nav_c3:
            if st.button("▶", key="nav_cal_right", use_container_width=True):
                if st.session_state["cal_month"] == 12:
                    st.session_state["cal_month"] = 1
                    st.session_state["cal_year"] += 1
                else:
                    st.session_state["cal_month"] += 1
                st.rerun()

        table_html = build_calendar_html_table(st.session_state["cal_year"], st.session_state["cal_month"], current_ronde.get("rencontres", []))
        st.markdown(table_html, unsafe_allow_html=True)

        if st.button("📅 Consulter le planning complet & déroulés ↗", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "📅 Planning des rencontres"
            st.session_state["planning_view"] = "📋 Liste des rencontres & Déroulés"
            st.rerun()

        st.write("")

        # 3. Effectifs de la ronde et Charte SGDF (parfaitement alignés sous le calendrier)
        enfants_count = len([m for m in current_ronde.get("membres", []) if m.get("role") == "Enfant"])
        parents_count = len([m for m in current_ronde.get("membres", []) if m.get("role") == "Parent"])
        st.markdown(f"""
            <div class="dashboard-card" style="margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:16px;">
                    <div class="card-icon-bubble">✍️</div>
                    <div>
                        <div class="card-title">Effectifs de la Ronde</div>
                        <div class="card-subtitle">{enfants_count} Farfadets inscrits • {parents_count} Parents engagés</div>
                    </div>
                </div>
            </div>
            <div class="dashboard-card" style="margin-bottom:0;">
                <div style="display:flex; align-items:center; gap:16px;">
                    <div class="card-icon-bubble">📥</div>
                    <div>
                        <div class="card-title">Règlement & Charte SGDF</div>
                        <div class="card-subtitle">Sécurité et cadre officiel</div>
                    </div>
                </div>
                <a href="https://www.sgdf.fr" target="_blank" class="card-action-btn">Consulter</a>
            </div>
        """, unsafe_allow_html=True)


# =============================================================
# 2. PAGE PLANNING DES RENCONTRES
# =============================================================
elif st.session_state["nav_page"] == "📅 Planning des rencontres":
    st.markdown("""
        <div class="hero-header-card" style="padding:22px 20px;">
            <h1 class="hero-main-title" style="font-size:26px;">Planning & Calendrier des Rencontres</h1>
            <div class="hero-sub-title" style="font-size:16px; color:#475569;">Consultez les dates, le déroulé visuel et les listes de matériel</div>
        </div>
    """, unsafe_allow_html=True)

    # Modale active de configuration détaillée si active
    if st.session_state.get("active_editing_rencontre_id"):
        dialog_modifier_rencontre(st.session_state["active_editing_rencontre_id"])

    PLANNING_VIEWS = [
        "📅 Vue Calendrier mensuel", 
        "📋 Liste des rencontres & Déroulés", 
        "➕ Programmer une rencontre"
    ]
    if "planning_view" not in st.session_state or st.session_state["planning_view"] not in PLANNING_VIEWS:
        st.session_state["planning_view"] = PLANNING_VIEWS[0]

    plan_view_choice = st.segmented_control(
        "Navigation Planning",
        options=PLANNING_VIEWS,
        default=st.session_state["planning_view"],
        selection_mode="single",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key="planning_seg_control"
    )
    if plan_view_choice:
        st.session_state["planning_view"] = plan_view_choice
    cur_plan_view = st.session_state.get("planning_view", PLANNING_VIEWS[0])

    if cur_plan_view == "📅 Vue Calendrier mensuel":
        col_cal_box, col_cal_side = st.columns([1.4, 1])

        with col_cal_box:
            p_nav1, p_nav2, p_nav3 = st.columns([1, 4, 1])
            with p_nav1:
                if st.button("◀", key="plan_month_prev", use_container_width=True):
                    if st.session_state["cal_month"] == 1:
                        st.session_state["cal_month"] = 12
                        st.session_state["cal_year"] -= 1
                    else:
                        st.session_state["cal_month"] -= 1
                    st.rerun()
            with p_nav2:
                st.markdown(f'<div class="cal-nav-title" style="font-size:16px; color:#1D4ED8;">{get_month_name(st.session_state["cal_month"])} {st.session_state["cal_year"]}</div>', unsafe_allow_html=True)
            with p_nav3:
                if st.button("▶", key="plan_month_next", use_container_width=True):
                    if st.session_state["cal_month"] == 12:
                        st.session_state["cal_month"] = 1
                        st.session_state["cal_year"] += 1
                    else:
                        st.session_state["cal_month"] += 1
                    st.rerun()

            cal_full_html = build_calendar_html_table(st.session_state["cal_year"], st.session_state["cal_month"], current_ronde.get("rencontres", []))
            st.markdown(cal_full_html, unsafe_allow_html=True)

        with col_cal_side:
            st.markdown("""
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px; margin-bottom:14px;">
                    <div style="font-weight:700; font-size:16px; color:#1E293B;">🔎 Rencontres du mois</div>
                    <div style="font-size:12px; color:#64748B;">Consultez, modifiez ou configurez le déroulé</div>
                </div>
            """, unsafe_allow_html=True)

            cur_prefix = f"{st.session_state['cal_year']}-{st.session_state['cal_month']:02d}"
            mois_rencontres = [r for r in current_ronde.get("rencontres", []) if parse_date_to_iso(r.get("date", "")).startswith(cur_prefix)]
            mois_rencontres = sorted(mois_rencontres, key=lambda x: parse_date_to_iso(x.get("date", "")))

            if mois_rencontres:
                for r in mois_rencontres:
                    with st.expander(f"📍 {format_date_fr(r['date'])} • {r['titre']}", expanded=True):
                        st.markdown(f"**Horaire :** `{r.get('horaire', '14:00 - 17:00')}`")
                        st.markdown(f"**Lieu :** {r.get('lieu', 'Local Scout')}")
                        st.markdown(f"**Animateur :** {r.get('animateur', 'Non défini')}")
                        
                        if is_responsable_or_admin():
                            btn_m1, btn_m2 = st.columns(2)
                            with btn_m1:
                                if st.button("⚙️ Configurer", key=f"btn_edit_cal_{r['id']}", use_container_width=True):
                                    st.session_state["active_editing_rencontre_id"] = r["id"]
                                    st.session_state["planning_view"] = "📅 Vue Calendrier mensuel"
                                    st.rerun()
                            with btn_m2:
                                if st.button("🗑️ Supprimer", key=f"btn_del_cal_{r['id']}", use_container_width=True):
                                    dialog_supprimer_rencontre(r["id"])
            else:
                st.info(f"Aucune rencontre en {get_month_name(st.session_state['cal_month'])} {st.session_state['cal_year']}.")

    elif cur_plan_view == "📋 Liste des rencontres & Déroulés":
        rencontres_all = sorted(current_ronde.get("rencontres", []), key=lambda x: parse_date_to_iso(x.get("date", "")))
        if rencontres_all:
            for r in rencontres_all:
                statut_badge = "🟢 À venir" if r.get("statut") == "À venir" else "⚪ Terminé"
                with st.container():
                    st.markdown(f"""
                        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px 20px; margin-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div style="font-weight:700; font-size:16.5px; color:#0F172A;">{r['titre']}</div>
                                <span style="background:#EFF6FF; color:#1D4ED8; font-weight:600; padding:4px 10px; border-radius:6px; font-size:12px;">{statut_badge}</span>
                            </div>
                            <div style="color:#64748B; font-size:13px; margin-top:4px;">
                                📅 <b>{format_date_fr(r['date'])}</b> &nbsp;|&nbsp; ⏰ <b>{r.get('horaire', '14:00 - 17:00')}</b> &nbsp;|&nbsp; 📍 {r.get('lieu', 'Lieu habituel')} &nbsp;|&nbsp; 👤 {r.get('animateur', 'Équipe')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    if is_responsable_or_admin():
                        c_act1, c_act2, c_act3 = st.columns([1.5, 1, 3])
                        with c_act1:
                            if st.button("⚙️ Configurer la rencontre", key=f"btn_edit_list_{r['id']}", use_container_width=True):
                                st.session_state["active_editing_rencontre_id"] = r["id"]
                                st.session_state["planning_view"] = "📋 Liste des rencontres & Déroulés"
                                st.rerun()
                        with c_act2:
                            if st.button("🗑️ Supprimer", key=f"btn_del_list_{r['id']}", use_container_width=True):
                                dialog_supprimer_rencontre(r["id"])
                    
                    with st.expander(f"Voir le déroulé et matériels de la séance ({len(r.get('deroule', []))} étapes)"):
                        if r.get("photo"):
                            st.markdown(f'<img src="{r["photo"]}" style="max-height:180px; border-radius:10px; margin-bottom:12px;">', unsafe_allow_html=True)
                        if r.get("description"):
                            st.markdown(f"**Description :** {r['description']}")
                        if r.get("imaginaire_rencontre"):
                            st.markdown(f"**Imaginaire de séance :** {r['imaginaire_rencontre']}")
                        if r.get("objectifs"):
                            st.markdown(f"**Objectifs :** {r['objectifs']}")

                        st.markdown("##### ⏱️ Tableau du Déroulé :")
                        if r.get("deroule"):
                            df_steps = []
                            custom_c_list = r.get("colonnes_deroule", [])
                            for idx, s in enumerate(r["deroule"]):
                                row_data = {
                                    "Date": s.get("date", format_date_fr(r.get("date"))),
                                    "Début": s.get("heure_debut", ""),
                                    "Fin": s.get("heure_fin", ""),
                                    "Activité": s.get("activite", ""),
                                    "Animateur": s.get("animateur", ""),
                                    "Matériels requis": ", ".join(s.get("materiels", [])),
                                    "Commentaire": s.get("commentaire", "")
                                }
                                for cc in custom_c_list:
                                    row_data[cc] = s.get(cc, "")
                                df_steps.append(row_data)
                            st.dataframe(pd.DataFrame(df_steps), use_container_width=True, hide_index=True)
                        else:
                            st.caption("Déroulé non renseigné.")

                        if r.get("materiels"):
                            st.markdown("##### 🎒 Matériels assignés :")
                            df_mats = pd.DataFrame([
                                {
                                    "Matériel": m.get("nom", ""),
                                    "Qui amène": m.get("qui_amene", ""),
                                    "Précision / Quantité": m.get("remarque", m.get("quantite", ""))
                                } for m in r["materiels"]
                            ])
                            st.dataframe(df_mats, use_container_width=True, hide_index=True)
                        st.write("")
        else:
            st.info("Aucune rencontre enregistrée.")

    elif cur_plan_view == "➕ Programmer une rencontre":
        if is_responsable_or_admin():
            st.subheader("Programmer une nouvelle rencontre")
            with st.form("form_add_rencontre", clear_on_submit=True):
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    titre_n = st.text_input("Titre de la rencontre *", placeholder="Ex : Grand jeu au parc...")
                    type_n = st.selectbox("Type d'événement", ["Rencontre ronde", "Sortie nature", "Réunion parents/animateurs", "Week-end de ronde"])
                    date_n = st.date_input("Date (JJ/MM/AAAA) *", value=date.today(), format="DD/MM/YYYY")
                with f_col2:
                    horaire_n = st.text_input("Créneau horaire", value="14:00 - 17:00")
                    lieu_n = st.text_input("Lieu", value=current_ronde.get("lieu_habituel", "Local Scout"))
                    animateur_n = st.text_input("Animateur principal", placeholder="Ex : Julien DUBOIS")

                st.markdown("---")
                st.markdown("##### Description & Pédagogie de la séance")
                desc_n = st.text_area("Description courte", placeholder="Ex : Séance en plein air consacrée à la découverte de la nature...")
                obj_n = st.text_input("Objectif pédagogique principal", placeholder="Ex : Apprendre à s'orienter et coopérer en sizaine")

                submitted_n = st.form_submit_button("Enregistrer la rencontre", type="primary", use_container_width=True)
                if submitted_n:
                    if not titre_n:
                        st.error("Le titre de la rencontre est obligatoire.")
                    else:
                        new_r_id = max([x["id"] for x in current_ronde.get("rencontres", [])], default=0) + 1
                        date_iso = parse_date_to_iso(date_n)
                        new_item = {
                            "id": new_r_id,
                            "titre": titre_n,
                            "type": type_n,
                            "date": date_iso,
                            "horaire": horaire_n,
                            "lieu": lieu_n,
                            "lieu_adresse": lieu_n,
                            "lat": 48.9417,
                            "lon": 2.1645,
                            "animateur": animateur_n,
                            "statut": "À venir",
                            "description": desc_n,
                            "imaginaire_rencontre": "",
                            "objectifs": obj_n,
                            "photo": "",
                            "materiels": [
                                {"id": 1, "nom": "Foulards de ronde", "qui_amene": animateur_n, "photo": ""},
                                {"id": 2, "nom": "Goûter et compotes", "qui_amene": "Parents", "photo": ""}
                            ],
                            "deroule": [
                                {"date": format_date_fr(date_iso), "heure_debut": "14:00", "heure_fin": "14:30", "activite": "Accueil et cri de ronde", "animateur": animateur_n, "materiels": ["Foulards de ronde"], "commentaire": "Rassemblement en cercle"},
                                {"date": format_date_fr(date_iso), "heure_debut": "14:30", "heure_fin": "16:15", "activite": "Activité principale", "animateur": animateur_n, "materiels": [], "commentaire": "Jeu par sizaine"},
                                {"date": format_date_fr(date_iso), "heure_debut": "16:15", "heure_fin": "17:00", "activite": "Goûter & Bilan", "animateur": "Parents", "materiels": ["Goûter et compotes"], "commentaire": "Nettoyage et fin"}
                            ]
                        }
                        current_ronde.setdefault("rencontres", []).append(new_item)
                        save_data(db)
                        st.session_state["flash_success"] = f"✅ La rencontre '{titre_n}' du {format_date_fr(date_iso)} a été ajoutée !"
                        st.session_state["planning_view"] = "📋 Liste des rencontres & Déroulés"
                        st.rerun()
        else:
            st.info("La programmation de rencontres est réservée aux animateurs et responsables.")


# =============================================================
# 3. PAGE LE GROUPE (FARFADETS & FAMILLES)
# =============================================================
elif st.session_state["nav_page"] == "👥 Farfadets & Familles":
    st.markdown("""
        <div class="hero-header-card" style="padding:22px 20px;">
            <h1 class="hero-main-title" style="font-size:26px;">Farfadets, Parents & Animateurs</h1>
            <div class="hero-sub-title" style="font-size:16px; color:#475569;">Annuaire, fiches membres et gestion des rôles</div>
        </div>
    """, unsafe_allow_html=True)

    tab_annuaire, tab_add_m = st.tabs(["📋 Annuaire et modification des membres", "➕ Inscrire un membre"])

    with tab_annuaire:
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric("Total Farfadets (6-8 ans)", len([m for m in current_ronde.get("membres", []) if m.get("role") == "Enfant"]))
        with c_m2:
            st.metric("Parents investis", len([m for m in current_ronde.get("membres", []) if m.get("role") == "Parent"]))
        with c_m3:
            st.metric("Responsables / Animateurs", len([m for m in current_ronde.get("membres", []) if m.get("role") == "Responsable"]))

        st.write("")
        membres_list = current_ronde.get("membres", [])
        if membres_list:
            for m in membres_list:
                with st.container():
                    st.markdown(f"""
                        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:12px 18px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <span style="font-weight:700; font-size:15px; color:#1E293B;">{m.get('prenom')} {m.get('nom')}</span>
                                    <span style="background:#DBEAFE; color:#1E40AF; font-size:11px; font-weight:600; padding:2px 8px; border-radius:12px; margin-left:8px;">{m.get('role')}</span>
                                </div>
                                <div style="font-size:12.5px; color:#64748B;">{m.get('contact', '')}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    if is_responsable_or_admin():
                        cm_act1, cm_act2, cm_space = st.columns([1, 1, 4])
                        with cm_act1:
                            if st.button("✏️ Modifier", key=f"edit_m_{m['id']}", use_container_width=True):
                                dialog_modifier_membre(m["id"])
                        with cm_act2:
                            if st.button("🗑️ Supprimer", key=f"del_m_{m['id']}", use_container_width=True):
                                dialog_supprimer_membre(m["id"])
                    st.write("")
        else:
            st.info("Aucun membre inscrit dans cette ronde.")

        if is_responsable_or_admin():
            st.write("")
            if st.button("➕ Inscrire un membre à la suite de la liste", type="primary", use_container_width=True, key="btn_add_member_from_list"):
                dialog_inscrire_membre()

    with tab_add_m:
        if not is_responsable_or_admin():
            st.info("ℹ️ L'inscription d'un nouveau membre est réservée aux animateurs et administrateurs.")
        else:
            st.subheader("Inscrire un nouveau membre")
            with st.form("form_add_m", clear_on_submit=True):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    p_prenom = st.text_input("Prénom *")
                    p_nom = st.text_input("Nom *")
                with col_p2:
                    p_role = st.selectbox("Rôle", ["Enfant", "Parent", "Responsable", "Invité"])
                    p_contact = st.text_input("Contact (tél ou email)")

                if st.form_submit_button("Ajouter à la ronde", type="primary", use_container_width=True):
                    if p_prenom and p_nom:
                        new_m_id = max([x["id"] for x in current_ronde.get("membres", [])], default=0) + 1
                        current_ronde.setdefault("membres", []).append({
                            "id": new_m_id,
                            "prenom": p_prenom,
                            "nom": p_nom,
                            "role": p_role,
                            "contact": p_contact,
                            "photo": f"{p_prenom[:1]}{p_nom[:1]}".upper()
                        })
                        save_data(db)
                        st.session_state["flash_success"] = f"✅ {p_prenom} {p_nom} a été ajouté(e) avec succès !"
                        st.rerun()
                    else:
                        st.error("Le prénom et le nom sont requis.")


# =============================================================
# 4. PAGE L'IMAGINAIRE
# =============================================================
elif st.session_state["nav_page"] == "✨ L'imaginaire de ronde":
    st.markdown("""
        <div class="hero-header-card" style="padding:22px 20px;">
            <h1 class="hero-main-title" style="font-size:26px;">L'Imaginaire des Farfadets</h1>
            <div class="hero-sub-title" style="font-size:16px; color:#475569;">Le cadre narratif, illustrations et aventures de l'année</div>
        </div>
    """, unsafe_allow_html=True)

    tab_im_view, tab_im_edit = st.tabs(["📖 Présentation de l'Imaginaire", "⚙️ Paramétrer le Texte & Photos"])

    with tab_im_view:
        st.markdown(f"### 🌟 {current_ronde.get('imaginaire_titre', 'L’Aventure des Farfadets')}")
        st.markdown(current_ronde.get("imaginaire", ""))

        im_photos = current_ronde.get("imaginaire_photos", [])
        if im_photos:
            st.markdown("---")
            st.markdown("#### 🎨 Galerie et Illustrations de l'Année")
            c_cols = st.columns(min(len(im_photos), 3))
            for p_i, p_obj in enumerate(im_photos):
                with c_cols[p_i % 3]:
                    st.markdown(f'<img src="{p_obj.get("url")}" style="width:100%; height:180px; object-fit:cover; border-radius:12px; border:1px solid #E2E8F0;">', unsafe_allow_html=True)
                    st.caption(f"**{p_obj.get('titre', '')}** — {p_obj.get('desc', '')}")

    with tab_im_edit:
        if is_responsable_or_admin():
            st.subheader("Modifier l'Imaginaire de Ronde")
            with st.form("form_edit_imaginaire_full"):
                titre_im = st.text_input("Titre de l'imaginaire", value=current_ronde.get("imaginaire_titre", "L'Aventure des Farfadets"))
                texte_im = st.text_area("Texte narratif enrichi (Markdown supporté)", value=current_ronde.get("imaginaire", ""), height=220)
                
                if st.form_submit_button("Sauvegarder le texte de l'imaginaire", type="primary", use_container_width=True):
                    current_ronde["imaginaire_titre"] = titre_im
                    current_ronde["imaginaire"] = texte_im
                    save_data(db)
                    st.session_state["flash_success"] = "✅ Imaginaire sauvegardé avec succès !"
                    st.rerun()

            st.markdown("---")
            st.subheader("Ajouter une illustration / photo à l'imaginaire")
            with st.form("form_add_im_photo", clear_on_submit=True):
                f_col_p1, f_col_p2 = st.columns(2)
                with f_col_p1:
                    ph_titre = st.text_input("Titre de l'illustration *", placeholder="Ex : Tom et Lou dans la forêt magique")
                    ph_desc = st.text_input("Légende / Description", placeholder="Ex : Les deux héros découvrent la première pierre")
                with f_col_p2:
                    ph_file = st.file_uploader("Fichier image (JPG, PNG)", type=["png", "jpg", "jpeg"])
                    ph_url = st.text_input("Ou URL directe de l'image", placeholder="https://...")

                if st.form_submit_button("Ajouter cette photo à la galerie", type="primary", use_container_width=True):
                    data_img = file_to_base64(ph_file) or ph_url
                    if not data_img or not ph_titre:
                        st.error("Veuillez renseigner un titre et sélectionner une image.")
                    else:
                        current_ronde.setdefault("imaginaire_photos", []).append({
                            "id": len(current_ronde.get("imaginaire_photos", [])) + 1,
                            "titre": ph_titre,
                            "desc": ph_desc,
                            "url": data_img
                        })
                        save_data(db)
                        st.session_state["flash_success"] = f"✅ Photo '{ph_titre}' ajoutée à l'imaginaire !"
                        st.rerun()

            im_photos_list = current_ronde.get("imaginaire_photos", [])
            if im_photos_list:
                st.markdown("---")
                st.markdown("##### 🗑️ Gérer / Supprimer les illustrations existantes")
                for idx_p, p_item in enumerate(im_photos_list):
                    col_d_p1, col_d_p2 = st.columns([4, 1])
                    with col_d_p1:
                        st.write(f"• **{p_item.get('titre')}** ({p_item.get('desc')})")
                    with col_d_p2:
                        if st.button("Supprimer", key=f"del_im_p_{idx_p}"):
                            im_photos_list.pop(idx_p)
                            current_ronde["imaginaire_photos"] = im_photos_list
                            save_data(db)
                            st.session_state["flash_success"] = "✅ Photo supprimée de l'imaginaire."
                            st.rerun()
        else:
            st.info("Seuls les animateurs et responsables peuvent modifier l'imaginaire.")


# =============================================================
# 5. PAGE DOCUMENTS & SUPPORTS
# =============================================================
elif st.session_state["nav_page"] == "📂 Documents & Supports":
    st.markdown("""
        <div class="hero-header-card" style="padding:22px 20px;">
            <h1 class="hero-main-title" style="font-size:26px;">Documents & Ressources Pédagogiques</h1>
            <div class="hero-sub-title" style="font-size:16px; color:#475569;">Fiches de jeux, livrets et règlements avec icônes personnalisées</div>
        </div>
    """, unsafe_allow_html=True)

    supports_list = current_ronde.get("supports", [])
    if supports_list:
        for s in supports_list:
            s_id = s.get("id", 1)
            icone_img = s.get("icone_image")
            if icone_img:
                icon_html = f'<img src="{icone_img}" style="width:44px; height:44px; object-fit:cover; border-radius:50%; border:1px solid #CBD5E1; flex-shrink:0;">'
            else:
                icon_html = '<div class="card-icon-bubble">📄</div>'

            st.markdown(f"""
                <div class="dashboard-card">
                    <div style="display:flex; align-items:center; gap:16px;">
                        {icon_html}
                        <div>
                            <div class="card-title">{s.get('titre', '')}</div>
                            <div class="card-subtitle">{s.get('desc', s.get('categorie', 'Support'))}</div>
                        </div>
                    </div>
                    <a href="{s.get('url', '#')}" target="_blank" class="card-action-btn">Télécharger</a>
                </div>
            """, unsafe_allow_html=True)

            if is_responsable_or_admin():
                cd_act1, cd_act2, cd_space = st.columns([1, 1, 4])
                with cd_act1:
                    if st.button("✏️ Modifier", key=f"edit_s_{s_id}", use_container_width=True):
                        dialog_modifier_support(s_id)
                with cd_act2:
                    if st.button("🗑️ Supprimer", key=f"del_s_{s_id}", use_container_width=True):
                        dialog_supprimer_support(s_id)
            st.write("")
    else:
        st.info("Aucun document enregistré.")

    if is_responsable_or_admin():
        with st.expander("➕ Ajouter un nouveau document ou lien utile"):
            with st.form("form_add_support_page", clear_on_submit=True):
                col_doc1, col_doc2 = st.columns(2)
                with col_doc1:
                    t_doc = st.text_input("Titre du document *", placeholder="Ex : Guide de camp Farfadet")
                    u_doc = st.text_input("Lien web (URL) *", placeholder="https://...")
                    c_doc = st.selectbox("Catégorie", ["Pédagogie", "Animation", "Chants", "Cadre légal", "Autre"])
                with col_doc2:
                    d_doc = st.text_input("Courte description", placeholder="Ex : Fiche pédagogique 6-8 ans")
                    up_ico = st.file_uploader("Image / Icône personnalisée du document", type=["png", "jpg", "jpeg"])
                    url_ico = st.text_input("Ou URL de l'image de l'icône", placeholder="https://...")

                if st.form_submit_button("Ajouter à la liste", type="primary", use_container_width=True):
                    if t_doc and u_doc:
                        new_s_id = max([x.get("id", 0) for x in current_ronde.get("supports", [])], default=0) + 1
                        ico_val = file_to_base64(up_ico) or url_ico or ""
                        current_ronde.setdefault("supports", []).append({
                            "id": new_s_id,
                            "titre": t_doc,
                            "url": u_doc,
                            "desc": d_doc,
                            "categorie": c_doc,
                            "icone_image": ico_val
                        })
                        save_data(db)
                        st.session_state["flash_success"] = f"✅ Document '{t_doc}' ajouté avec succès !"
                        st.rerun()
                    else:
                        st.error("Le titre et le lien URL sont obligatoires.")


# =============================================================
# 6. PAGE PARAMÈTRES DE LA RONDE (ADMIN SEULEMENT)
# =============================================================
elif st.session_state["nav_page"] == "⚙️ Paramètres de la Ronde":
    if not is_admin():
        st.error("⛔ Accès refusé : Seul l'administrateur peut accéder aux paramètres de la ronde.")
        st.stop()

    st.markdown("""
        <div class="hero-header-card" style="padding:22px 20px;">
            <h1 class="hero-main-title" style="font-size:26px;">Paramètres, Droits & Gestion Multi-Rondes</h1>
            <div class="hero-sub-title" style="font-size:16px; color:#475569;">Espace réservé à l'administrateur</div>
        </div>
    """, unsafe_allow_html=True)

    tab_p_ronde, tab_p_users, tab_p_sync = st.tabs([
        "🏕️ Informations de la Ronde", 
        "👥 Gestion des Utilisateurs & Rôles", 
        "☁️ Synchronisation Google Sheets"
    ])

    with tab_p_ronde:
        st.subheader(f"Ronde active : {current_ronde.get('nom')}")
        with st.form("form_update_ronde_page", clear_on_submit=False):
            nom_r = st.text_input("Nom de la ronde", value=current_ronde.get("nom", ""))
            saison_r = st.text_input("Saison / Année", value=current_ronde.get("saison", ""))
            groupe_r = st.text_input("Nom du groupe SGDF", value=current_ronde.get("groupe", ""))
            lieu_r = st.text_input("Lieu habituel", value=current_ronde.get("lieu_habituel", ""))
            peuplade_r = st.text_input("Nom de la peuplade", value=current_ronde.get("peuplade", "Branche scoute des 6 - 8 ans et leurs parents"))

            if st.form_submit_button("Enregistrer les modifications", type="primary", use_container_width=True):
                current_ronde["nom"] = nom_r
                current_ronde["saison"] = saison_r
                current_ronde["groupe"] = groupe_r
                current_ronde["lieu_habituel"] = lieu_r
                current_ronde["peuplade"] = peuplade_r
                save_data(db)
                st.session_state["flash_success"] = "✅ Informations de la ronde mises à jour !"
                st.rerun()

        st.markdown("---")
        st.subheader("Actions sur les rondes")
        c_ronde_a, c_ronde_b = st.columns(2)
        with c_ronde_a:
            if st.button("➕ Créer une nouvelle ronde", use_container_width=True):
                dialog_creer_ronde()
        with c_ronde_b:
            if len(db["rondes"]) > 1:
                if st.button("🗑️ Supprimer cette ronde", type="secondary", use_container_width=True):
                    db["rondes"] = [x for x in db["rondes"] if x["id"] != current_ronde["id"]]
                    db["active_ronde_id"] = db["rondes"][0]["id"]
                    st.session_state["active_ronde_id"] = db["rondes"][0]["id"]
                    save_data(db)
                    st.session_state["flash_success"] = "🗑️ Ronde supprimée."
                    st.rerun()
            else:
                st.caption("Vous ne pouvez pas supprimer la seule ronde existante.")

    # GESTION DES UTILISATEURS ET DES RÔLES
    with tab_p_users:
        st.subheader("Utilisateurs enregistrés & Rôles d'accès")
        st.caption("Chaque compte est rattaché à une personne du groupe et dispose d'un rôle (Admin, Responsable, Parent).")
        
        users_list = db.get("utilisateurs", [])
        cur_edit_u_id = st.session_state.get("p_user_editing_id", None)
        is_adding_u = st.session_state.get("p_user_adding", False)

        # Mapping membre_id -> Nom complet du membre
        all_membres_map = {}
        membres_choices = []
        for r_item in db.get("rondes", []):
            for mb_item in r_item.get("membres", []):
                mb_label = f"{mb_item.get('id')} - {mb_item.get('prenom')} {mb_item.get('nom')} ({r_item.get('nom')})"
                all_membres_map[mb_item.get("id")] = f"{mb_item.get('prenom')} {mb_item.get('nom')}"
                membres_choices.append({
                    "id": mb_item.get("id"),
                    "label": mb_label
                })

        seen_labels = set()
        unique_mb_choices = []
        for m_ch in membres_choices:
            if m_ch["label"] not in seen_labels:
                seen_labels.add(m_ch["label"])
                unique_mb_choices.append(m_ch)
        mb_labels = [m["label"] for m in unique_mb_choices]

        all_rondes = db.get("rondes", [])
        ronde_id_to_name = {r["id"]: r.get("nom", f"Ronde {r['id']}") for r in all_rondes}

        # ÉCRAN 1 : MODIFICATION D'UN UTILISATEUR DEPUIS SA LIGNE
        if cur_edit_u_id is not None:
            target_user = next((u for u in users_list if u.get("id") == cur_edit_u_id), None)
            if target_user:
                c_back, c_title = st.columns([1.2, 4])
                with c_back:
                    if st.button("← Retour au tableau", key="btn_back_u_edit", use_container_width=True):
                        st.session_state["p_user_editing_id"] = None
                        st.rerun()
                with c_title:
                    st.markdown(f"##### ✏️ Modifier l'utilisateur : **{target_user.get('prenom', '')} {target_user.get('nom', '')}** (ID #{target_user.get('id')})")

                with st.form(f"form_edit_user_{cur_edit_u_id}"):
                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        ed_prenom = st.text_input("Prénom *", value=target_user.get("prenom", ""))
                        ed_nom = st.text_input("Nom *", value=target_user.get("nom", ""))
                        ed_email = st.text_input("Adresse e-mail (identifiant) *", value=target_user.get("email", ""))
                        ed_new_pwd = st.text_input("Nouveau mot de passe (optionnel)", type="password", placeholder="Laisser vide pour conserver l'actuel", help="Saisissez un nouveau mot de passe (min. 4 car.) uniquement si vous souhaitez le réinitialiser.")
                    with col_ed2:
                        roles_opts = ["parent", "responsable", "admin"]
                        current_role = target_user.get("role", "parent").lower()
                        role_index = roles_opts.index(current_role) if current_role in roles_opts else 0
                        ed_role = st.selectbox(
                            "Rôle d'accès *",
                            roles_opts,
                            index=role_index,
                            format_func=lambda x: "👑 Administrateur" if x=="admin" else ("🏕️ Responsable Farfadets" if x=="responsable" else "👨‍👩‍👧 Parent")
                        )

                        mb_idx = 0
                        for idx_m, m_ch in enumerate(unique_mb_choices):
                            if m_ch["id"] == target_user.get("membre_id"):
                                mb_idx = idx_m
                                break
                        sel_mb_label = st.selectbox("Rattacher à un membre du groupe :", mb_labels, index=mb_idx) if mb_labels else None

                        user_curr_rondes = target_user.get("rondes_autorisees", [current_ronde["id"]])
                        if not isinstance(user_curr_rondes, list):
                            user_curr_rondes = [current_ronde["id"]]
                        default_rondes = [rid for rid in user_curr_rondes if rid in ronde_id_to_name]
                        if not default_rondes and all_rondes:
                            default_rondes = [all_rondes[0]["id"]]

                        ed_rondes = st.multiselect(
                            "Rondes autorisées :",
                            options=list(ronde_id_to_name.keys()),
                            default=default_rondes,
                            format_func=lambda rid: ronde_id_to_name.get(rid, f"Ronde {rid}")
                        )

                    col_b1, col_b2 = st.columns([3, 1])
                    with col_b1:
                        sub_edit = st.form_submit_button("💾 Enregistrer les modifications de l'utilisateur", type="primary", use_container_width=True)
                    with col_b2:
                        sub_cancel = st.form_submit_button("Annuler", use_container_width=True)

                    if sub_cancel:
                        st.session_state["p_user_editing_id"] = None
                        st.rerun()

                    if sub_edit:
                        if not ed_prenom.strip() or not ed_nom.strip() or not ed_email.strip():
                            st.error("Le prénom, le nom et l'adresse e-mail sont obligatoires.")
                        elif any(u.get("id") != cur_edit_u_id and u.get("email", "").strip().lower() == ed_email.strip().lower() for u in users_list):
                            st.error("Cette adresse e-mail est déjà attribuée à un autre compte.")
                        elif ed_new_pwd and len(ed_new_pwd) < 4:
                            st.error("Le mot de passe doit comporter au moins 4 caractères.")
                        else:
                            target_user["prenom"] = ed_prenom.strip()
                            target_user["nom"] = ed_nom.strip()
                            target_user["email"] = ed_email.strip()
                            target_user["role"] = ed_role
                            if sel_mb_label:
                                target_user["membre_id"] = int(sel_mb_label.split("-")[0].strip())
                            target_user["rondes_autorisees"] = ed_rondes if ed_rondes else [current_ronde["id"]]
                            if ed_new_pwd:
                                target_user["mot_de_passe"] = hash_password(ed_new_pwd)

                            if logged_user.get("id") == cur_edit_u_id:
                                st.session_state["logged_user"] = target_user

                            save_data(db)
                            st.session_state["p_user_editing_id"] = None
                            st.session_state["flash_success"] = f"✅ Utilisateur {ed_prenom} {ed_nom} mis à jour avec succès !"
                            st.rerun()

                if cur_edit_u_id != logged_user.get("id"):
                    st.write("")
                    if st.button("🗑️ Supprimer définitivement cet utilisateur", key=f"btn_del_editing_u_{cur_edit_u_id}", type="secondary"):
                        db["utilisateurs"] = [x for x in db["utilisateurs"] if x.get("id") != cur_edit_u_id]
                        save_data(db)
                        st.session_state["p_user_editing_id"] = None
                        st.session_state["flash_success"] = "🗑️ Compte utilisateur supprimé avec succès."
                        st.rerun()
            else:
                st.session_state["p_user_editing_id"] = None
                st.rerun()

        # ÉCRAN 2 : SAISIE POUR AJOUTER UN NOUVEL UTILISATEUR À LA SUITE DU TABLEAU
        elif is_adding_u:
            c_back, c_title = st.columns([1.2, 4])
            with c_back:
                if st.button("← Retour au tableau", key="btn_back_u_add", use_container_width=True):
                    st.session_state["p_user_adding"] = False
                    st.rerun()
            with c_title:
                st.markdown("##### ➕ Ajouter un nouvel utilisateur à la suite du tableau")

            with st.form("form_add_new_user_screen", clear_on_submit=True):
                col_nu1, col_nu2 = st.columns(2)
                with col_nu1:
                    u_prenom = st.text_input("Prénom *")
                    u_nom = st.text_input("Nom *")
                    u_email = st.text_input("Adresse e-mail (identifiant) *")
                    u_pwd = st.text_input("Mot de passe initial *", type="password", value="scout123")
                with col_nu2:
                    u_role = st.selectbox(
                        "Rôle d'accès *", 
                        ["parent", "responsable", "admin"], 
                        format_func=lambda x: "👑 Administrateur" if x=="admin" else ("🏕️ Responsable Farfadets" if x=="responsable" else "👨‍👩‍👧 Parent")
                    )
                    sel_mb_link = st.selectbox("Rattacher à un membre du groupe :", mb_labels) if mb_labels else None
                    new_rondes = st.multiselect(
                        "Rondes autorisées :",
                        options=list(ronde_id_to_name.keys()),
                        default=[current_ronde["id"]],
                        format_func=lambda rid: ronde_id_to_name.get(rid, f"Ronde {rid}")
                    )

                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    sub_add_u = st.form_submit_button("➕ Enregistrer cet utilisateur et l'ajouter au tableau", type="primary", use_container_width=True)
                with col_b2:
                    sub_canc_u = st.form_submit_button("Annuler", use_container_width=True)

                if sub_canc_u:
                    st.session_state["p_user_adding"] = False
                    st.rerun()

                if sub_add_u:
                    if not u_prenom.strip() or not u_nom.strip() or not u_email.strip():
                        st.error("Le prénom, le nom et l'adresse e-mail sont obligatoires.")
                    elif any(u.get("email", "").strip().lower() == u_email.strip().lower() for u in users_list):
                        st.error("Cette adresse e-mail est déjà utilisée par un autre compte.")
                    elif len(u_pwd) < 4:
                        st.error("Le mot de passe doit comporter au moins 4 caractères.")
                    else:
                        link_id = int(sel_mb_link.split("-")[0].strip()) if sel_mb_link else 1
                        new_u_id = max([x.get("id", 0) for x in users_list], default=0) + 1
                        db.setdefault("utilisateurs", []).append({
                            "id": new_u_id,
                            "prenom": u_prenom.strip(),
                            "nom": u_nom.strip(),
                            "email": u_email.strip(),
                            "mot_de_passe": hash_password(u_pwd),
                            "role": u_role,
                            "membre_id": link_id,
                            "rondes_autorisees": new_rondes if new_rondes else [current_ronde["id"]]
                        })
                        save_data(db)
                        st.session_state["p_user_adding"] = False
                        st.session_state["flash_success"] = f"✅ Utilisateur {u_prenom} {u_nom} ({u_role}) enregistré !"
                        st.rerun()

        # ÉCRAN 3 : AFFICHAGE DU TABLEAU AVEC ACTIONS SUR CHAQUE LIGNE ET BOUTON D'AJOUT À LA SUITE
        else:
            if users_list:
                st.markdown("""
                    <div style="background:#F1F5F9; border:1px solid #CBD5E1; border-radius:8px 8px 0 0; padding:10px 12px; font-weight:700; font-size:13px; color:#1E293B; margin-bottom:4px;">
                        <div style="display:flex; align-items:center;">
                            <div style="width:7%;"># ID</div>
                            <div style="width:23%;">Identité</div>
                            <div style="width:25%;">E-mail (Identifiant)</div>
                            <div style="width:17%;">Rôle</div>
                            <div style="width:14%;">Membre rattaché</div>
                            <div style="width:14%; text-align:right;">Actions</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                role_badges = {
                    "admin": ('<span style="background:#FEF3C7; color:#92400E; font-size:11px; padding:2px 8px; border-radius:12px; font-weight:600;">👑 Admin</span>'),
                    "responsable": ('<span style="background:#DCFCE7; color:#166534; font-size:11px; padding:2px 8px; border-radius:12px; font-weight:600;">🏕️ Responsable</span>'),
                    "parent": ('<span style="background:#DBEAFE; color:#1E40AF; font-size:11px; padding:2px 8px; border-radius:12px; font-weight:600;">👨‍👩‍👧 Parent</span>')
                }

                for u in users_list:
                    u_id = u.get("id")
                    u_role = u.get("role", "parent").lower()
                    badge_html = role_badges.get(u_role, f'<span style="background:#F3F4F6; color:#374151; font-size:11px; padding:2px 8px; border-radius:12px; font-weight:600;">{u_role.upper()}</span>')
                    is_me = (u_id == logged_user.get("id"))
                    mb_name = all_membres_map.get(u.get("membre_id"), "-")

                    c_id, c_name, c_mail, c_role, c_mb, c_actions = st.columns([0.7, 2.3, 2.5, 1.7, 1.4, 1.4])
                    with c_id:
                        st.markdown(f"**#{u_id}**")
                    with c_name:
                        me_tag = ' <span style="background:#EEF2FF; color:#4338CA; font-size:10px; padding:1px 6px; border-radius:10px; font-weight:700;">(Vous)</span>' if is_me else ''
                        st.markdown(f"**{u.get('prenom', '')} {u.get('nom', '')}**{me_tag}", unsafe_allow_html=True)
                    with c_mail:
                        st.markdown(f"✉️ `{u.get('email', '')}`")
                    with c_role:
                        st.markdown(badge_html, unsafe_allow_html=True)
                    with c_mb:
                        st.caption(f"👤 {mb_name}")
                    with c_actions:
                        cb1, cb2 = st.columns([2, 1])
                        with cb1:
                            if st.button("✏️ Modifier", key=f"btn_edit_u_line_{u_id}", use_container_width=True):
                                st.session_state["p_user_editing_id"] = u_id
                                st.session_state["p_user_adding"] = False
                                st.rerun()
                        with cb2:
                            if not is_me:
                                if st.button("🗑️", key=f"btn_del_u_line_{u_id}", use_container_width=True, help="Supprimer cet utilisateur"):
                                    db["utilisateurs"] = [x for x in db["utilisateurs"] if x.get("id") != u_id]
                                    save_data(db)
                                    st.session_state["flash_success"] = f"🗑️ Utilisateur {u.get('prenom')} {u.get('nom')} supprimé."
                                    st.rerun()
                            else:
                                st.caption("—")
                    st.markdown('<hr style="margin:4px 0 8px 0; border:0; border-top:1px solid #E2E8F0;">', unsafe_allow_html=True)
            else:
                st.info("Aucun utilisateur enregistré.")

            st.write("")
            if st.button("➕ Ajouter un utilisateur à la suite du tableau", type="primary", use_container_width=True, key="btn_trigger_add_user"):
                st.session_state["p_user_adding"] = True
                st.session_state["p_user_editing_id"] = None
                st.rerun()


    # SYNCHRONISATION GOOGLE SHEETS
    with tab_p_sync:
        st.subheader("☁️ Synchronisation Google Sheets & Collaboratif")
        st.caption("Exportez la totalité des données du site sous forme d'un classeur Excel complet (9 onglets synchronisés avec votre base de données JSON) ou synchronisez depuis un Google Sheet partagé.")

        excel_path = os.path.join(os.path.dirname(__file__), "Modele_Google_Sheets_Ronde_Farfadets.xlsx")
        try:
            excel_bytes = build_excel_export_bytes(db, save_path=excel_path)
        except Exception:
            excel_bytes = None

        col_dl1, col_dl2 = st.columns([2, 1])
        with col_dl1:
            if excel_bytes:
                st.download_button(
                    label="📊 Télécharger le classeur Excel complet (9 onglets à jour du JSON)",
                    data=excel_bytes,
                    file_name="Modele_Google_Sheets_Ronde_Farfadets.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("Impossible de générer le flux Excel pour le moment.")
        with col_dl2:
            st.caption("💡 9 onglets inclus : Rondes, Membres, Rencontres, Déroulés, Matériels, Imaginaire, Supports, Utilisateurs, Configuration.")

        st.markdown("---")
        stored_gsheet_url = db.get("google_sheet_url", "")
        gsheet_url_input = st.text_input(
            "Lien de votre Google Sheet :", 
            value=stored_gsheet_url,
            placeholder="https://docs.google.com/spreadsheets/d/1A2B3C4D.../edit"
        )

        col_sync1, col_sync2 = st.columns(2)
        with col_sync1:
            if st.button("📥 Synchroniser depuis Google Sheets", type="primary", use_container_width=True):
                if not gsheet_url_input:
                    st.error("Veuillez renseigner l'URL de votre Google Sheet.")
                else:
                    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", gsheet_url_input)
                    if not match:
                        st.error("URL invalide. Doit contenir '/spreadsheets/d/...'")
                    else:
                        sheet_id = match.group(1)
                        with st.spinner("Synchronisation en cours depuis Google Sheets..."):
                            try:
                                def fetch_sheet(name, required=True):
                                    try:
                                        enc_name = urllib.parse.quote(name)
                                        u = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={enc_name}"
                                        df_res = pd.read_csv(u)
                                        return df_res
                                    except Exception as ex:
                                        if required:
                                            raise ex
                                        return pd.DataFrame()

                                df_r = fetch_sheet("Rondes")
                                df_m = fetch_sheet("Membres")
                                df_rc = fetch_sheet("Rencontres")
                                df_im = fetch_sheet("Imaginaire", required=False)
                                df_sp = fetch_sheet("Supports", required=False)
                                df_d = fetch_sheet("Deroules", required=False)
                                df_mat = fetch_sheet("Materiels", required=False)
                                df_u_sheet = fetch_sheet("Utilisateurs", required=False)

                                new_rondes = []
                                for _, row_r in df_r.iterrows():
                                    rid = safe_int(row_r["id"])
                                    r_membres = []
                                    for _, row_m in df_m[df_m["ronde_id"] == rid].iterrows():
                                        r_membres.append({
                                            "id": safe_int(row_m["id"]),
                                            "prenom": str(row_m.get("prenom", "")),
                                            "nom": str(row_m.get("nom", "")),
                                            "role": str(row_m.get("role", "Enfant")),
                                            "contact": str(row_m.get("contact", "")) if pd.notna(row_m.get("contact")) else "",
                                            "photo": str(row_m.get("photo", "")) if pd.notna(row_m.get("photo")) else ""
                                        })

                                    r_rencontres = []
                                    for _, row_rc in df_rc[df_rc["ronde_id"] == rid].iterrows():
                                        rc_id = safe_int(row_rc["id"])
                                        
                                        # Parsing deroule
                                        deroule_val = row_rc.get("deroule_json", "[]")
                                        try:
                                            deroule_parsed = json.loads(deroule_val) if isinstance(deroule_val, str) and deroule_val.strip() else []
                                        except Exception:
                                            deroule_parsed = []
                                            
                                        # Enrichissement depuis la feuille Deroules si deroule_json est vide
                                        if not deroule_parsed and not df_d.empty and "rencontre_id" in df_d.columns:
                                            sub_d = df_d[(df_d["ronde_id"] == rid) & (df_d["rencontre_id"] == rc_id)]
                                            if not sub_d.empty:
                                                for _, row_d in sub_d.iterrows():
                                                    mats = str(row_d.get("materiels", ""))
                                                    mat_list = [x.strip() for x in mats.split(",") if x.strip()] if mats and mats != "nan" else []
                                                    deroule_parsed.append({
                                                        "date": str(row_d.get("date", "")) if pd.notna(row_d.get("date")) else "",
                                                        "heure_debut": str(row_d.get("heure_debut", "")) if pd.notna(row_d.get("heure_debut")) else "",
                                                        "heure_fin": str(row_d.get("heure_fin", "")) if pd.notna(row_d.get("heure_fin")) else "",
                                                        "activite": str(row_d.get("activite", "")) if pd.notna(row_d.get("activite")) else "",
                                                        "animateur": str(row_d.get("animateur", "")) if pd.notna(row_d.get("animateur")) else "",
                                                        "commentaire": str(row_d.get("commentaire", "")) if pd.notna(row_d.get("commentaire")) else "",
                                                        "materiels": mat_list
                                                    })

                                        # Parsing colonnes personnalisées
                                        col_d_val = row_rc.get("colonnes_deroule_json", "[]")
                                        try:
                                            colonnes_parsed = json.loads(col_d_val) if isinstance(col_d_val, str) and col_d_val.strip() else []
                                        except Exception:
                                            colonnes_parsed = []

                                        # Parsing materiels
                                        mat_val = row_rc.get("materiels_json", "[]")
                                        try:
                                            mat_parsed = json.loads(mat_val) if isinstance(mat_val, str) and mat_val.strip() else []
                                        except Exception:
                                            mat_parsed = []

                                        # Enrichissement depuis la feuille Materiels si materiels_json est vide
                                        if not mat_parsed and not df_mat.empty and "rencontre_id" in df_mat.columns:
                                            sub_mat = df_mat[(df_mat["ronde_id"] == rid) & (df_mat["rencontre_id"] == rc_id)]
                                            if not sub_mat.empty:
                                                for _, row_mat in sub_mat.iterrows():
                                                    mat_parsed.append({
                                                        "id": safe_int(row_mat.get("materiel_id", 1)),
                                                        "nom": str(row_mat.get("nom", "")) if pd.notna(row_mat.get("nom")) else "",
                                                        "qui_amene": str(row_mat.get("qui_amene", "")) if pd.notna(row_mat.get("qui_amene")) else "",
                                                        "photo": str(row_mat.get("photo", "")) if pd.notna(row_mat.get("photo")) else ""
                                                    })

                                        # Coordonnées GPS & adresse (supporte formats avec virgules ou points)
                                        lat_val = safe_float(row_rc.get("lat"), 48.9417)
                                        lon_val = safe_float(row_rc.get("lon"), 2.1645)
                                        lieu_adr = str(row_rc.get("lieu_adresse", row_rc.get("lieu", ""))) if pd.notna(row_rc.get("lieu_adresse")) else str(row_rc.get("lieu", ""))

                                        r_rencontres.append({
                                            "id": rc_id,
                                            "titre": str(row_rc.get("titre", "")),
                                            "type": str(row_rc.get("type", "Rencontre ronde")),
                                            "date": str(row_rc.get("date", "")),
                                            "horaire": str(row_rc.get("horaire", "14:00 - 17:00")),
                                            "lieu": str(row_rc.get("lieu", "")),
                                            "lieu_adresse": lieu_adr,
                                            "lat": lat_val,
                                            "lon": lon_val,
                                            "animateur": str(row_rc.get("animateur", "")) if pd.notna(row_rc.get("animateur")) else "",
                                            "statut": str(row_rc.get("statut", "À venir")),
                                            "description": str(row_rc.get("description", "")) if pd.notna(row_rc.get("description")) else "",
                                            "imaginaire_rencontre": str(row_rc.get("imaginaire_rencontre", "")) if pd.notna(row_rc.get("imaginaire_rencontre")) else "",
                                            "objectifs": str(row_rc.get("objectifs", "")) if pd.notna(row_rc.get("objectifs")) else "",
                                            "photo": str(row_rc.get("photo", "")) if pd.notna(row_rc.get("photo")) else "",
                                            "colonnes_deroule": colonnes_parsed,
                                            "deroule": deroule_parsed,
                                            "materiels": mat_parsed
                                        })

                                    # Imaginaire de ronde
                                    im_text = ""
                                    im_titre = "L'Aventure des Farfadets"
                                    im_photos = []
                                    if not df_im.empty:
                                        im_sub = df_im[df_im["ronde_id"] == rid]
                                        if not im_sub.empty:
                                            im_text = str(im_sub.iloc[0]["texte"]) if pd.notna(im_sub.iloc[0].get("texte")) else ""
                                            if "titre" in im_sub.columns and pd.notna(im_sub.iloc[0].get("titre")):
                                                im_titre = str(im_sub.iloc[0]["titre"])
                                            if "photos_json" in im_sub.columns and pd.notna(im_sub.iloc[0].get("photos_json")):
                                                try:
                                                    im_photos = json.loads(str(im_sub.iloc[0]["photos_json"]))
                                                except Exception:
                                                    im_photos = []

                                    # Supports
                                    r_supports = []
                                    if not df_sp.empty:
                                        for _, row_sp in df_sp[df_sp["ronde_id"] == rid].iterrows():
                                            r_supports.append({
                                                "id": safe_int(row_sp["id"]),
                                                "titre": str(row_sp.get("titre", "")),
                                                "url": str(row_sp.get("url", "")),
                                                "categorie": str(row_sp.get("categorie", "Pédagogie")),
                                                "desc": str(row_sp.get("desc", "")) if pd.notna(row_sp.get("desc")) else ""
                                            })

                                    new_rondes.append({
                                        "id": rid,
                                        "nom": str(row_r.get("nom", "")),
                                        "saison": str(row_r.get("saison", "")),
                                        "groupe": str(row_r.get("groupe", "")),
                                        "peuplade": str(row_r.get("peuplade", "Branche scoute des 6 - 8 ans et leurs parents")),
                                        "lieu_habituel": str(row_r.get("lieu_habituel", "")),
                                        "membres": r_membres,
                                        "rencontres": [normalize_rencontre_data(rc) for rc in r_rencontres],
                                        "imaginaire": im_text,
                                        "imaginaire_titre": im_titre,
                                        "imaginaire_photos": im_photos,
                                        "supports": r_supports
                                    })

                                if new_rondes:
                                    db["rondes"] = new_rondes
                                    db["active_ronde_id"] = new_rondes[0]["id"]
                                    st.session_state["active_ronde_id"] = new_rondes[0]["id"]
                                    db["google_sheet_url"] = gsheet_url_input
                                    
                                    # Utilisateurs (si feuille présente)
                                    if not df_u_sheet.empty and "email" in df_u_sheet.columns:
                                        imported_users = []
                                        for _, row_u in df_u_sheet.iterrows():
                                            u_email = str(row_u.get("email", "")).strip()
                                            if not u_email or u_email == "nan":
                                                continue
                                            existing_u = next((u for u in db.get("utilisateurs", []) if u.get("email", "").strip().lower() == u_email.lower()), None)
                                            pwd_hash = existing_u.get("mot_de_passe") if existing_u else hash_password("scout123")
                                            u_id = safe_int(row_u.get("id")) if pd.notna(row_u.get("id")) else (existing_u.get("id") if existing_u else len(imported_users) + 1)
                                            r_auth_str = str(row_u.get("rondes_autorisees", ""))
                                            try:
                                                r_auth = [int(x.strip()) for x in r_auth_str.split(",") if x.strip().isdigit()]
                                            except Exception:
                                                r_auth = [new_rondes[0]["id"]]
                                            if not r_auth:
                                                r_auth = [new_rondes[0]["id"]]
                                            imported_users.append({
                                                "id": u_id,
                                                "prenom": str(row_u.get("prenom", "")),
                                                "nom": str(row_u.get("nom", "")),
                                                "email": u_email,
                                                "mot_de_passe": pwd_hash,
                                                "role": str(row_u.get("role", "parent")).lower(),
                                                "membre_id": safe_int(row_u.get("membre_id"), 1),
                                                "rondes_autorisees": r_auth
                                            })
                                        if imported_users:
                                            db["utilisateurs"] = imported_users

                                    save_data(db)
                                    st.session_state["flash_success"] = "✅ Synchronisation réussie avec Google Sheets (toutes les tables à jour) !"
                                    st.rerun()
                                else:
                                    st.error("Aucune ronde trouvée dans le Google Sheet.")
                            except Exception as e:
                                st.error(f"Erreur de synchronisation : {e}")

        with col_sync2:
            if st.button("📤 Régénérer le fichier Excel miroir sur le disque", use_container_width=True):
                try:
                    build_excel_export_bytes(db, save_path=excel_path)
                    st.session_state["flash_success"] = "✅ Fichier Excel miroir régénéré avec succès avec toutes les données actuelles du site (9 onglets synchronisés) !"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")