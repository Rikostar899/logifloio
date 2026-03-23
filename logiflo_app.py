import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import datetime
import re
import tempfile
import os
import difflib
import unicodedata
import math
import time
import requests
import concurrent.futures
from fpdf import FPDF
from openai import OpenAI
import json

st.set_page_config(page_title="LOGIFLO.IO | Control Tower", layout="wide", page_icon="🏢")

# =========================================
# 0. INIT IA
# =========================================
client = OpenAI(api_key="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")

# =========================================
# 0.1 AUTH
# =========================================
USERS_DB = {
    "eric":         "logiflo2026",
    "admin":        "admin123",
    "demo_client1": "audit2026",
    "demo_client2": "test2026",
    "jury":         "pitch2026",
    "partenaire":   "partner2026",
    "test":         "test123",
}

# =========================================
# 0.2 ORS
# =========================================
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImIwNzAxZDE3YjQxNzRjYmJiZGFhMjhmZGU0MWNjYmY0IiwiaCI6Im11cm11cjY0In0="

# =========================================
# 0.3 PROMPTS IA
# =========================================
PROMPT_STOCK = """
PRE-PHASE: CONTEXTUAL INTELLIGENCE
Avant toute analyse, détecte automatiquement le contexte client via les données fournies.

Identity:
Tu es l'Auditeur Financier et Directeur Supply Chain Senior pour Logiflo.io.
Langue: RÉPONDS IMPÉRATIVEMENT ET INTÉGRALEMENT EN FRANÇAIS.

Structure obligatoire — utilise EXACTEMENT ces titres :

### DIAGNOSTIC OPERATIONNEL
Bilan critique du taux de service et de la rotation. Nomme explicitement les 3 références en rupture ou à risque imminent.

### DIAGNOSTIC FINANCIER & STOCKS DORMANTS
Analyse du capital immobilisé. Nomme les 3 références qui vampirisent la trésorerie.

### PLAN D'ACTION IMMÉDIAT (TOP 3)
3 recommandations concrètes. Pour chaque action, ligne suivante :
Impact potentiel : Fort/Moyen/Faible | Difficulté d'exécution : 1 à 5

### SCORING LOGIFLO
- Performance & Rotation stock : /100
- Risque financier (Cash Trap) : /100
- Résilience supply chain : /100

RÈGLES STRICTES :
1. N'INVENTE AUCUN GAIN EN EUROS.
2. N'utilise JAMAIS mes instructions comme texte dans ta réponse.
3. Si une donnée manque, signale-le comme ANGLE MORT STRATÉGIQUE.
4. Fais un vrai saut de ligne entre chaque idée.
"""

PROMPT_TRANSPORT = """
PRE-PHASE: CONTEXTUAL INTELLIGENCE
Détecte automatiquement le mode de transport dominant. Si les données contiennent un poids (kg), calcule le coût au kg et déduis le taux de remplissage estimé selon le type de véhicule probable. Si le poids est absent, signale-le OBLIGATOIREMENT comme ANGLE MORT STRATÉGIQUE : sans cette donnée, le coût au km ne permet pas de juger l'efficacité réelle du chargement.

Identity:
Tu es un Auditeur Senior en Stratégie Transport & Supply Chain.
Langue: RÉPONDS IMPÉRATIVEMENT ET INTÉGRALEMENT EN FRANÇAIS.
Ton ton est clinique, implacable et orienté R.O.I. NE SOIS PAS UN PERROQUET : déduis les problèmes cachés.

Structure obligatoire — utilise EXACTEMENT ces titres :

### AUDIT DE RENTABILITE
Analyse chirurgicale de la marge globale et du Yield. Nomme les 3 trajets/clients qui détruisent la rentabilité. Émets une hypothèse experte sur la cause.

### DIAGNOSTIC RÉSEAU
Juge la cohérence spatiale et l'efficacité d'exploitation. Si le poids est disponible : analyse le coût/kg et le remplissage estimé. Si absent : signale ANGLE MORT STRATÉGIQUE.

### PLAN DE RATIONALISATION (TOP 3)
3 recommandations agressives.
Pour chaque action : Impact Cash : Fort/Moyen/Faible | Difficulté d'exécution : 1 à 5

### SCORING LOGIFLO
- Rentabilité & Yield Transport : /100
- Efficacité Opérationnelle (Remplissage / Vide) : /100
- Maîtrise des OPEX (Coûts d'achat) : /100

RÈGLES STRICTES :
1. N'INVENTE AUCUN GAIN EN EUROS.
2. N'utilise JAMAIS mes instructions comme texte dans ta réponse.
3. Fais un vrai saut de ligne entre chaque idée.
"""

# =========================================
# 1. SESSION STATE
# =========================================
defaults = {
    "page": "accueil", "module": "", "auth": False,
    "df_stock": None, "df_trans": None,
    "history_stock": [], "stock_view": "MANAGER",
    "seuil_bas": 15, "seuil_rupture": 0, "seuil_km": 0,
    "geo_cache": {}, "route_cache": {},
    "trans_mapping": None, "trans_filename": None,
    "analysis_stock": None, "analysis_trans": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================
# 2. CSS
# =========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

:root {
    --navy:  #0B2545;
    --navy2: #162D52;
    --green: #00C896;
    --green2:#00A87A;
    --slate: #4A6080;
    --light: #F0F4F8;
    --red:   #E8304A;
    --white: #FFFFFF;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    color: var(--navy);
}
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 95% !important;
}

/* KPI CARDS */
.kpi-card {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    border-top: 3px solid var(--green);
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    transition: transform 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
.kpi-card h4 {
    color: var(--slate) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
}
.kpi-card h2 {
    font-family: 'Syne', sans-serif !important;
    font-size: 2.2rem !important;
    font-weight: 800 !important;
    margin-top: 0;
    line-height: 1;
    letter-spacing: -1px;
}
.kpi-card p {
    font-size: 12px;
    color: var(--slate);
    margin-top: 6px;
}

/* BOUTONS */
div.stButton > button {
    border-radius: 8px;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    background-color: var(--navy);
    color: #f8fafc;
    border: none;
    transition: 0.3s;
}
div.stButton > button:hover {
    background-color: var(--navy2);
    transform: translateY(-2px);
}

/* SIDEBAR */
[data-testid="stSidebar"] { background-color: var(--navy) !important; }
[data-testid="stSidebar"] * { color: #ffffff !important; font-size: 1rem !important; }
[data-testid="stSidebar"] hr { border-color: #1e3a5f !important; }
div[role="radiogroup"] > label { padding-bottom: 12px; cursor: pointer; }

/* LOGO SIDEBAR */
.sidebar-logo {
    font-family: 'Syne', sans-serif;
    font-size: 26px;
    font-weight: 800;
    color: white;
    letter-spacing: -0.5px;
}
.sidebar-logo span { color: #00C896; }

/* IMPORT CARD */
.import-card {
    background: var(--white);
    padding: 25px;
    border-radius: 12px;
    border-left: 6px solid var(--green);
    margin-bottom: 20px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}
.import-card h3 {
    margin-top: 0;
    color: var(--navy);
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
}
.import-card p { color: var(--slate); font-size: 14px; margin-bottom: 0; line-height: 1.5; }

/* RAPPORT IA — rendu markdown propre */
.report-text {
    background: var(--light);
    padding: 32px;
    border-radius: 12px;
    border-left: 6px solid var(--navy);
    box-shadow: 0 4px 6px rgba(0,0,0,0.06);
    line-height: 1.8;
}
.report-text h3 {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 800;
    color: var(--navy);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-top: 28px;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--green);
}
.report-text h3:first-child { margin-top: 0; }
.report-text p { color: #2d3748; font-size: 14px; margin-bottom: 8px; }
.report-text strong { color: var(--navy); }
.report-text ul { padding-left: 20px; }
.report-text li { color: #2d3748; font-size: 14px; margin-bottom: 4px; }

/* TERRAIN ALERT */
.terrain-alert {
    background-color: #fef2f2;
    border-left: 5px solid var(--red);
    padding: 16px; border-radius: 6px;
    margin-bottom: 20px;
    font-weight: bold; color: #991b1b;
}

/* BIG EMOJI */
.big-emoji { font-size: 70px; margin-bottom: 10px; display:block; text-align:center; }
</style>
""", unsafe_allow_html=True)

# =========================================
# 3. HELPER — RENDU RAPPORT IA
# =========================================
def render_report(texte: str) -> str:
    """
    Convertit le texte brut de l'IA en HTML propre.
    Transforme ### Titre → <h3>, **gras** → <strong>, sauts de ligne → <p>.
    """
    html_lines = []
    for line in texte.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Titres ### 
        if line.startswith('### '):
            titre = line[4:].strip()
            html_lines.append(f"<h3>{titre}</h3>")
        # Gras **texte**
        else:
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            # Puces - ou *
            if line.startswith('- ') or line.startswith('* '):
                html_lines.append(f"<p>• {line[2:]}</p>")
            else:
                html_lines.append(f"<p>{line}</p>")
    return '\n'.join(html_lines)

# =========================================
# 4. MOTEUR PDF
# =========================================
class PDFReport(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.multi_cell(0, 4, "Document genere par Logiflo.io. Les recommandations sont a titre indicatif.", align="C")

def generate_expert_pdf(title, content, figs=None):
    pdf = PDFReport()
    # Page de garde
    pdf.add_page()
    pdf.set_fill_color(11, 37, 69)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_y(100)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 32)
    pdf.cell(0, 15, "LOGIFLO.IO", ln=True, align='C')
    pdf.set_font("Arial", "", 14)
    pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 10, "AUDIT STRATEGIQUE", ln=True, align='C')
    pdf.ln(30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 20)
    clean_title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    pdf.cell(0, 10, clean_title, ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Date d'edition : {datetime.date.today().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.cell(0, 10, "Statut : CONFIDENTIEL", ln=True, align='C')
    # Page contenu
    pdf.add_page()
    pdf.set_fill_color(240, 244, 248)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_y(10)
    pdf.set_text_color(11, 37, 69)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "RAPPORT D'ANALYSE", ln=True, align='L')
    pdf.line(10, 25, 200, 25)
    pdf.ln(15)
    if figs:
        for fig in figs:
            try:
                img_bytes = fig.to_image(format="png", width=800, height=350)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name
                pdf.image(tmp_path, x=15, y=pdf.get_y() + 2, w=180)
                pdf.ln(95)
            except:
                pass
    if pdf.get_y() > 220:
        pdf.add_page()
    content = (content
        .replace("\u2019", "'").replace("\u2018", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u20ac", "EUR").replace("\u2022", "-"))
    for line in content.split('\n'):
        line = line.strip().replace("<br>", "")
        if not line:
            pdf.ln(4); continue
        if line.startswith('### '):
            t = unicodedata.normalize('NFKD', line[4:]).encode('ASCII', 'ignore').decode('utf-8')
            pdf.ln(6)
            pdf.set_font("Arial", "BU", 12)
            pdf.set_text_color(11, 37, 69)
            pdf.cell(0, 8, t.upper(), ln=True)
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(40, 40, 40)
        else:
            body = unicodedata.normalize('NFKD',
                line.replace("<b>","").replace("</b>","").replace("**","")
            ).encode('ASCII', 'ignore').decode('utf-8')
            pdf.multi_cell(0, 6, body)
    return pdf.output(dest='S').encode('latin-1')

# =========================================
# 5. SMART INGESTER STOCK
# =========================================
def nettoyer_texte(t):
    t = str(t).lower()
    t = unicodedata.normalize('NFD', t).encode('ascii', 'ignore').decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', t)

def smart_ingester_stock_ultime(df):
    propres = {col: nettoyer_texte(col) for col in df.columns}
    cibles = {
        "reference":     ["reference","ref","article","code","sku","ean","produit","designation","nom","item"],
        "quantite":      ["quantite","qte","qty","stock","stk","volume","pieces","units","restant"],
        "prix_unitaire": ["prix","price","cout","cost","valeur","pmp","tarif","montant","pu","achat"]
    }
    trouvees = {}
    for std, syns in cibles.items():
        for orig, propre in propres.items():
            if orig in trouvees: continue
            if any(s == propre or (len(s) >= 3 and s in propre) for s in syns):
                trouvees[orig] = std; break
            if difflib.get_close_matches(propre, syns, n=1, cutoff=0.8):
                trouvees[orig] = std
    df = df.rename(columns=trouvees)
    manq = [c for c in ["reference","quantite","prix_unitaire"] if c not in df.columns]
    if manq:
        return None, f"Colonnes introuvables : {', '.join(manq)}."
    for col in ["quantite","prix_unitaire"]:
        df[col] = df[col].astype(str).str.replace(r'[^\d.,-]','',regex=True).str.replace(',','.')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna(subset=["quantite","prix_unitaire"]).copy(), "Succès"

# =========================================
# 6. AUTO MAP TRANSPORT (IA)
# =========================================
def auto_map_columns_with_ai(df):
    titres = list(df.columns)
    profil = {col: {"exemples": list(df[col].dropna().astype(str).unique()[:5])} for col in titres}
    prompt = f"""Tu es un Data Architect expert.
Titres disponibles : {titres}
Données : {json.dumps(profil, ensure_ascii=False)}
Associe chaque concept à un titre EXACT. Si absent, mets null.
Concepts : "client", "ca", "co", "dep", "arr", "dist", "poids".
JSON uniquement : {{"client":"...","ca":"...","co":"...","dep":"...","arr":"...","dist":"...","poids":"..."}}"""
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":prompt}],
            temperature=0.0
        )
        raw = r.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        mapping = json.loads(raw)
        return {k: v for k, v in mapping.items() if v in titres}
    except:
        return {"client": titres[0], "ca": titres[1] if len(titres)>1 else None, "co": None}

# =========================================
# 7. GÉNÉRATION IA
# =========================================
def generate_ai_analysis(data_summary):
    prompt = PROMPT_STOCK if st.session_state.module == "stock" else PROMPT_TRANSPORT
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":prompt},
                {"role":"user","content":f"Métriques : {data_summary}. Rédige l'audit selon la structure imposée."}
            ],
            temperature=0.2
        )
        texte = r.choices[0].message.content
        try:
            return texte.encode('latin-1').decode('utf-8')
        except:
            return texte
    except Exception as e:
        return f"Erreur IA : {str(e)}"

# =========================================
# 8. ROUTING ORS
# =========================================
def calculate_haversine(lon1, lat1, lon2, lat2):
    R = 6371.0
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def fetch_geo(city, _token=None):
    if not city or str(city).strip() in ("","nan","None"):
        return city, None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": str(city).strip(), "format":"json","limit":1},
            headers={"User-Agent":"Logiflo.io/2.0 (contact@logiflo.io)"},
            timeout=5
        )
        if r.status_code == 200:
            d = r.json()
            if d:
                return city, [float(d[0]["lon"]), float(d[0]["lat"])]
    except:
        pass
    return city, None

def geocode_cities_mapbox(cities):
    villes = [c for c in set(str(v) for v in cities)
              if c not in st.session_state.geo_cache and c not in ("","nan","None")]
    if villes:
        bar = st.progress(0, text="📍 Géocodage des villes...")
        for i, city in enumerate(villes):
            _, coord = fetch_geo(city)
            if coord:
                st.session_state.geo_cache[city] = coord
            time.sleep(1.1)
            bar.progress((i+1)/len(villes), text=f"📍 Géocodage... ({i+1}/{len(villes)})")
        bar.empty()
    return {c: st.session_state.geo_cache[c]
            for c in set(str(v) for v in cities)
            if c in st.session_state.geo_cache}

@st.cache_data(show_spinner=False)
def _ors_distance(lon1, lat1, lon2, lat2):
    for profile in ["driving-hgv","driving-car"]:
        try:
            r = requests.post(
                f"https://api.openrouteservice.org/v2/directions/{profile}",
                json={"coordinates":[[lon1,lat1],[lon2,lat2]],"instructions":False},
                headers={"Accept":"application/json","Content-Type":"application/json","Authorization":ORS_API_KEY},
                timeout=6
            )
            if r.status_code == 200:
                return r.json()["routes"][0]["summary"]["distance"] / 1000.0
        except:
            continue
    return None

def fetch_route(dep, arr, mode, coords, _token=None):
    c1, c2 = coords.get(str(dep)), coords.get(str(arr))
    if not c1 or not c2:
        return (dep, arr, mode), 0.0
    lon1,lat1 = c1; lon2,lat2 = c2
    dist_vol = calculate_haversine(lon1,lat1,lon2,lat2)
    m = str(mode).lower()
    if any(k in m for k in ["mer","sea","maritime","bateau","conteneur","port","ferry"]):
        return (dep,arr,mode), dist_vol*1.25
    elif any(k in m for k in ["air","avion","aérien","aerien","flight"]):
        return (dep,arr,mode), dist_vol*1.05
    elif any(k in m for k in ["fer","rail","train","sncf","ferroviaire"]):
        return (dep,arr,mode), dist_vol*1.15
    else:
        d = _ors_distance(lon1,lat1,lon2,lat2)
        return (dep,arr,mode), (d if d and d>0 else dist_vol*1.30)

def smart_multimodal_router(df, dep_col, arr_col, mode_col=None):
    coords = geocode_cities_mapbox(pd.concat([df[dep_col],df[arr_col]]).dropna().unique())
    uniq = []
    for _,row in df.iterrows():
        dep = row[dep_col]; arr = row[arr_col]
        mode = str(row[mode_col]).lower() if mode_col and pd.notna(row.get(mode_col)) else "route"
        k = (dep,arr,mode)
        if k not in st.session_state.route_cache and k not in uniq:
            uniq.append(k)
    if uniq:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for key, dist in [f.result() for f in concurrent.futures.as_completed(
                [ex.submit(fetch_route,r[0],r[1],r[2],coords) for r in uniq])]:
                st.session_state.route_cache[key] = dist
    df["_DIST_CALCULEE"] = [
        st.session_state.route_cache.get(
            (row[dep_col], row[arr_col],
             str(row[mode_col]).lower() if mode_col and pd.notna(row.get(mode_col)) else "route"), 0.0)
        for _,row in df.iterrows()
    ]
    return df

def super_clean(val):
    if pd.isna(val): return 0.0
    try:
        return float(str(val).replace('€','').replace('$','').replace('EUR','')
                     .replace(' ','').replace('\xa0','').replace(',','.'))
    except:
        return 0.0

# =========================================
# 9. PAGES
# =========================================

# — ACCUEIL —
if st.session_state.page == "accueil":
    st.markdown("<h1 style='text-align:center;color:#0B2545;font-family:Syne,sans-serif;font-weight:800;letter-spacing:-1px;'>LOGIFLO.IO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;font-size:1.1em;color:#4A6080;'>Plateforme d'Intelligence Logistique et d'Optimisation Financière</p><br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<span class='big-emoji'>📦</span>", unsafe_allow_html=True)
        if st.button("AUDIT STOCKS", use_container_width=True):
            st.session_state.module="stock"; st.session_state.page="choix_profil_stock"; st.rerun()
    with c2:
        st.markdown("<span class='big-emoji'>🌍</span>", unsafe_allow_html=True)
        if st.button("AUDIT TRANSPORT", use_container_width=True):
            st.session_state.module="transport"; st.session_state.page="login"; st.rerun()
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, cm, _ = st.columns([1,1,1])
    if cm.button("DEMANDER UN ACCÈS PRIVÉ", use_container_width=True):
        st.session_state.page="contact"; st.rerun()

# — CONTACT —
elif st.session_state.page == "contact":
    st.markdown("<h2 style='text-align:center;color:#0B2545;font-family:Syne,sans-serif;'>Demande d'Accès Réservé</h2>", unsafe_allow_html=True)
    _, cc, _ = st.columns([1,1.5,1])
    with cc:
        with st.form("vip"):
            st.text_input("Nom & Prénom"); st.text_input("Email Professionnel"); st.text_input("Entreprise")
            st.selectbox("Volume géré :",["Moins de 10M EUR","De 10M à 50M EUR","Plus de 50M EUR"])
            st.selectbox("Enjeu prioritaire :",["Optimisation BFR (Stocks)","Réduction coûts Transport","Global Supply Chain"])
            if st.form_submit_button("Transmettre", use_container_width=True):
                st.success("Demande transmise. Notre équipe vous contactera sous 24h.")
        if st.button("← Retour", use_container_width=True):
            st.session_state.page="accueil"; st.rerun()

# — CHOIX PROFIL STOCK —
elif st.session_state.page == "choix_profil_stock":
    st.markdown("<h2 style='text-align:center;color:#0B2545;font-family:Syne,sans-serif;'>Sélectionnez votre Espace de Travail</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#4A6080;'>L'interface s'adaptera à vos habilitations.</p><br><br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<span class='big-emoji'>📊</span>", unsafe_allow_html=True)
        if st.button("PROFIL MANAGER (Stratégie & Finance)", use_container_width=True):
            st.session_state.stock_view="MANAGER"; st.session_state.page="login"; st.rerun()
    with c2:
        st.markdown("<span class='big-emoji'>👷</span>", unsafe_allow_html=True)
        if st.button("PROFIL TERRAIN (Action Opérationnelle)", use_container_width=True):
            st.session_state.stock_view="TERRAIN"; st.session_state.page="login"; st.rerun()

# — LOGIN —
elif st.session_state.page == "login":
    st.markdown(f"<h2 style='text-align:center;color:#0B2545;font-family:Syne,sans-serif;'>Accès Sécurisé — Module {st.session_state.module.upper()}</h2><br>", unsafe_allow_html=True)
    _, cl, _ = st.columns([1,1.2,1])
    with cl:
        with st.form("login_form"):
            u = st.text_input("Identifiant")
            p = st.text_input("Mot de passe", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Connexion", use_container_width=True):
                if u in USERS_DB and USERS_DB[u] == p:
                    st.session_state.auth=True; st.session_state.page="app"; st.rerun()
                else:
                    st.error("Identifiants incorrects.")
        if st.button("← Retour", use_container_width=True):
            st.session_state.page="accueil"; st.rerun()

# — APP —
elif st.session_state.auth and st.session_state.page == "app":

    with st.sidebar:
        st.markdown("""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
                <div class="sidebar-logo">LOGI<span>FLO</span>.IO</div>
                <div style="font-size:20px;line-height:1.2;">📦<br>📦📦</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        nav = st.radio("NAVIGATION", ["Espace de Travail","Paramètres","Archives","Mentions Légales & CGV"])
        st.markdown("---")
        if st.button("Déconnexion", use_container_width=True):
            st.session_state.clear(); st.rerun()
        st.markdown("<div style='margin-top:40px;border-top:1px solid #1e3a5f;padding-top:14px;font-size:11px;color:#4A6080;'>© 2026 Logiflo B2B Enterprise</div>", unsafe_allow_html=True)

    # MENTIONS LÉGALES
    if nav == "Mentions Légales & CGV":
        st.title("⚖️ Mentions Légales & CGUV")
        st.markdown("Dernière mise à jour : Mars 2026\n\n---")
        st.markdown("""
### 1. OBJET
Les présentes CGUV régissent l'accès à **Logiflo.io**. Accès réservé aux professionnels B2B accrédités.

### 2. ZERO DATA RETENTION
Fichiers traités en mémoire vive uniquement. Non stockés, non revendus, non utilisés pour entraîner des modèles IA. Purgés automatiquement à la fin de session.

### 3. PROPRIÉTÉ INTELLECTUELLE
Algorithmes, Smart Ingester™, cerveaux IA et design sont la propriété exclusive de Logiflo. Toute reproduction sans autorisation est passible de poursuites.

### 4. LIMITATION DE RESPONSABILITÉ
Audits fournis à titre de support à la décision. Logiflo ne saurait être tenu responsable des décisions prises sur cette base.

### 5. LOI APPLICABLE
Droit français. Tribunaux de Commerce du siège social de Logiflo compétents.
        """)

    # ARCHIVES
    elif nav == "Archives":
        st.title("🗄️ Archives & Historique")
        st.info("Module de synchronisation en cours d'initialisation.")

    # PARAMÈTRES
    elif nav == "Paramètres":
        st.title("⚙️ Configuration des Seuils")
        if st.session_state.module == "stock":
            st.session_state.seuil_bas      = st.slider("Seuil d'Alerte", 0, 100, st.session_state.seuil_bas)
            st.session_state.seuil_rupture  = st.slider("Seuil de Rupture Critique", 0, 10, st.session_state.seuil_rupture)
        else:
            st.session_state.seuil_km = st.slider("Seuil Rentabilité (EUR/KM)", 0, 1000, st.session_state.seuil_km)

    # ESPACE DE TRAVAIL
    elif nav == "Espace de Travail":

        # ==========================================
        # MODULE STOCK
        # ==========================================
        if st.session_state.module == "stock":
            st.title("📦 Audit Financier des Stocks")
            ci, cb = st.columns([4,1])
            ci.markdown(f"**Profil Actif : {st.session_state.stock_view}**")
            if cb.button("Changer de profil"):
                st.session_state.page="choix_profil_stock"; st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <div class='import-card'>
                    <h3>📥 Importation Sécurisée</h3>
                    <p>Déposez votre extraction brute. Le <b>Smart Ingester™</b> détecte et nettoie automatiquement vos colonnes.</p>
                </div>
            """, unsafe_allow_html=True)

            up = st.file_uploader("", type=["csv","xlsx"], key="stock_upload")
            st.markdown("---")

            if up:
                df_brut = pd.read_excel(up) if up.name.endswith("xlsx") else pd.read_csv(up)
                with st.spinner("⏳ Analyse en cours..."):
                    df_propre, statut = smart_ingester_stock_ultime(df_brut)
                if df_propre is None:
                    st.error(statut)
                else:
                    st.session_state.df_stock = df_propre

            if st.session_state.df_stock is not None:
                df = st.session_state.df_stock

                col_sorties = next((c for c in df.columns if any(k in str(c).lower() for k in ["vente","sortie","sold","conso"])), None)
                if col_sorties:
                    df["_SORTIES"] = df[col_sorties].fillna(0)
                    df["Couverture"] = np.where(df["_SORTIES"]>0, df["quantite"]/df["_SORTIES"], 9999)
                    df["Statut"] = np.select(
                        [(df["quantite"]<=st.session_state.seuil_rupture),
                         (df["quantite"]>0)&(df["_SORTIES"]==0),
                         (df["quantite"]>0)&(df["Couverture"]>6)],
                        ["🚨 RUPTURE","🔴 Dormant (Mort)","🟠 Rotation Lente (> 6 mois)"],
                        default="✅ Sain"
                    )
                else:
                    df["Statut"] = np.where(df["quantite"]<=st.session_state.seuil_rupture, "🚨 RUPTURE","✅ EN STOCK")

                df["valeur_totale"] = df["quantite"] * df["prix_unitaire"]
                val_totale = df["valeur_totale"].sum()
                ruptures   = df[df["Statut"]=="🚨 RUPTURE"]
                tx_serv    = (1 - len(ruptures)/len(df))*100 if len(df)>0 else 100

                if not st.session_state.history_stock or st.session_state.history_stock[-1]["valeur"] != val_totale:
                    st.session_state.history_stock.append({"date":datetime.datetime.now().strftime("%H:%M:%S"),"valeur":val_totale})

                # ── VUE MANAGER ──
                if st.session_state.stock_view == "MANAGER":
                    c1,c2,c3 = st.columns(3)
                    c1.markdown(f"<div class='kpi-card'><h4>Capital Immobilisé</h4><h2 style='color:#0B2545;'>{val_totale:,.0f} €</h2></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='kpi-card'><h4>Taux de Service</h4><h2 style='color:#00C896;'>{tx_serv:.1f} %</h2></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='kpi-card'><h4>Articles en Rupture</h4><h2 style='color:#E8304A;'>{len(ruptures)}</h2></div>", unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    cp, cl2 = st.columns(2)
                    color_map = {
                        "🚨 RUPTURE":"#E8304A","✅ EN STOCK":"#00C896","✅ Sain":"#00C896",
                        "🔴 Dormant (Mort)":"#c0392b","🟠 Rotation Lente (> 6 mois)":"#f39c12"
                    }
                    with cp:
                        fig_pie = px.pie(df, names="Statut", hole=0.4, color="Statut", color_discrete_map=color_map)
                        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with cl2:
                        fig_line = px.line(pd.DataFrame(st.session_state.history_stock), x="date", y="valeur")
                        fig_line.update_traces(line_color="#00C896")
                        fig_line.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_line, use_container_width=True)

                    if st.button("GÉNÉRER L'AUDIT FINANCIER (IA)", use_container_width=True):
                        with st.spinner("Analyse approfondie en cours..."):
                            df_tox = df[df["Statut"].isin(["🔴 Dormant (Mort)","🟠 Rotation Lente (> 6 mois)"])]
                            pires  = df_tox.nlargest(3,"valeur_totale") if not df_tox.empty else df.nlargest(3,"valeur_totale")
                            top_str = ", ".join([f"{r['reference']} ({r['valeur_totale']:,.0f} EUR)" for _,r in pires.iterrows()])
                            rupt_l  = ruptures.nlargest(3,"prix_unitaire")["reference"].astype(str).tolist() if not ruptures.empty else "Aucune"
                            st.session_state.analysis_stock = generate_ai_analysis(
                                f"Capital immobilisé: {val_totale:.0f} EUR. Taux service: {tx_serv:.1f}%. "
                                f"Ruptures: {len(ruptures)}. Top dormants: {top_str}. Top ruptures: {rupt_l}."
                            )

                    if st.session_state.analysis_stock:
                        rendu = render_report(st.session_state.analysis_stock)
                        st.markdown(f'<div class="report-text">{rendu}</div><br>', unsafe_allow_html=True)
                        pdf_data = generate_expert_pdf("AUDIT STRATEGIQUE DES STOCKS", st.session_state.analysis_stock, [fig_pie, fig_line])
                        st.download_button("📥 Télécharger le Rapport Officiel (PDF)", pdf_data, "Audit_Stock_Logiflo.pdf", use_container_width=True)

                # ── VUE TERRAIN (sans jauge) ──
                elif st.session_state.stock_view == "TERRAIN":
                    c1, c2 = st.columns(2)
                    c1.markdown(f"<div class='kpi-card'><h4>Articles à Réapprovisionner</h4><h2 style='color:#E8304A;'>{len(ruptures)}</h2></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='kpi-card'><h4>Taux de Disponibilité</h4><h2 style='color:#00C896;'>{tx_serv:.1f} %</h2></div>", unsafe_allow_html=True)

                    st.markdown("### 🚨 Plan d'Action Terrain")
                    if len(ruptures) > 0:
                        st.dataframe(ruptures[["reference","quantite","prix_unitaire","Statut"]], use_container_width=True)
                    else:
                        st.success("✅ Aucun article en rupture.")

                    st.markdown("### 📊 Inventaire Complet")
                    st.dataframe(df[["reference","quantite","Statut"]], use_container_width=True, height=400)

        # ==========================================
        # MODULE TRANSPORT
        # ==========================================
        elif st.session_state.module == "transport":
            st.title("🚚 Audit de Rentabilité Transport")
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <div class='import-card'>
                    <h3>🌍 Importation des Flux de Transport</h3>
                    <p>Déposez votre fichier TMS ou Excel. Le moteur <b>ORS</b> calcule les distances routières réelles en Europe.<br>
                    <b>Conseil :</b> incluez une colonne <b>poids (kg)</b> pour activer l'analyse de remplissage.<br>
                    <span style='color:#00A87A;font-weight:600;'>✓ Zero Data Retention</span> | Formats : .CSV, .XLSX</p>
                </div>
            """, unsafe_allow_html=True)

            up_t = st.file_uploader("", type=["csv","xlsx"], key="trans_upload")
            st.markdown("---")

            if up_t:
                if st.session_state.trans_filename != up_t.name:
                    try:
                        df_t = pd.read_excel(up_t) if up_t.name.endswith("xlsx") else pd.read_csv(up_t, encoding='utf-8')
                    except UnicodeDecodeError:
                        up_t.seek(0)
                        df_t = pd.read_csv(up_t, encoding='latin-1')
                    with st.spinner("⏳ Détection des colonnes..."):
                        mapping = auto_map_columns_with_ai(df_t)
                    st.session_state.trans_mapping  = mapping
                    st.session_state.df_trans       = df_t
                    st.session_state.trans_filename = up_t.name

            if st.session_state.df_trans is not None:
                df_t    = st.session_state.df_trans
                mapping = st.session_state.trans_mapping

                def col(k): return mapping.get(k) if mapping.get(k) in df_t.columns else None

                tour_c = col("client") or df_t.columns[0]
                dep_c  = col("dep");  arr_c  = col("arr")
                dist_c = col("dist"); mode_c = col("mode")
                ca_c   = col("ca");   co_c   = col("co")
                poids_c = col("poids")

                if not co_c:
                    for c in df_t.columns:
                        if any(k in str(c).lower() for k in ["coût","cout","cost","achat"]):
                            co_c=c; break
                if not ca_c:
                    for c in df_t.columns:
                        if any(k in str(c).lower() for k in ["ca","revenue","revenu","facture"]):
                            ca_c=c; break

                if not co_c:
                    st.error("🚨 Colonne 'Coût' introuvable dans votre fichier.")
                    st.stop()

                df_t["_CO"] = df_t[co_c].apply(super_clean)
                if ca_c:
                    df_t["_CA"] = df_t[ca_c].apply(super_clean)
                else:
                    df_t["_CA"] = df_t["_CO"] / 0.85
                    st.warning("💡 CA manquant — estimé à marge 15%.")

                df_t["Marge_Nette"] = df_t["_CA"] - df_t["_CO"]

                if dep_c and arr_c and "_DIST_CALCULEE" not in df_t.columns:
                    with st.spinner("⏳ Calcul des distances ORS..."):
                        df_t = smart_multimodal_router(df_t, dep_c, arr_c, mode_c)
                        st.session_state.df_trans = df_t

                df_t["_DIST_FINALE"] = (
                    df_t["_DIST_CALCULEE"] if "_DIST_CALCULEE" in df_t.columns and df_t["_DIST_CALCULEE"].sum()>0
                    else (df_t[dist_c].apply(super_clean) if dist_c else 0)
                )
                df_t["Rentabilité_%"] = np.where(df_t["_CA"]>0, df_t["Marge_Nette"]/df_t["_CA"]*100, 0)
                df_t["_DS"]           = df_t["_DIST_FINALE"].replace(0,1)
                df_t["Cout_KM"]       = np.where(df_t["_DIST_FINALE"]>0, df_t["_CO"]/df_t["_DS"], 0)

                # Poids si disponible
                poids_info = ""
                if poids_c:
                    df_t["_POIDS"] = df_t[poids_c].apply(super_clean)
                    df_t["_DS_P"]  = df_t["_POIDS"].replace(0,1)
                    df_t["Cout_kg"] = np.where(df_t["_POIDS"]>0, df_t["_CO"]/df_t["_DS_P"], 0)
                    poids_total  = df_t["_POIDS"].sum()
                    cout_kg_moy  = df_t["Cout_kg"].mean()
                    poids_info   = f" Poids total transporté: {poids_total:,.0f} kg. Coût moyen/kg: {cout_kg_moy:.3f} EUR."

                marge_tot  = df_t["Marge_Nette"].sum()
                ca_tot     = df_t["_CA"].sum()
                taux       = (marge_tot/ca_tot*100) if ca_tot>0 else 0
                traj_def   = len(df_t[df_t["Marge_Nette"]<0])
                cout_km    = df_t["Cout_KM"].mean()
                toxiques   = df_t[df_t["Marge_Nette"]<(df_t["_CA"]*0.05)]
                fuite      = toxiques["_CO"].sum()-toxiques["_CA"].sum()
                nb_tox     = len(toxiques)

                c1,c2,c3 = st.columns(3)
                c1.markdown(f"<div class='kpi-card'><h4>Marge Nette Globale</h4><h2 style='color:#0B2545;'>{marge_tot:,.0f} €</h2></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='kpi-card'><h4>Taux de Rentabilité</h4><h2 style='color:#00C896;'>{taux:.1f} %</h2></div>", unsafe_allow_html=True)
                if fuite > 0:
                    c3.markdown(f"<div class='kpi-card'><h4>🚨 Fuite de Marge</h4><h2 style='color:#E8304A;'>-{fuite:,.0f} €</h2><p>{nb_tox} trajets toxiques</p></div>", unsafe_allow_html=True)
                else:
                    c3.markdown(f"<div class='kpi-card'><h4>✅ Réseau</h4><h2 style='color:#00C896;'>Sain</h2></div>", unsafe_allow_html=True)

                if poids_c:
                    st.info(f"⚖️ Données poids détectées — Coût moyen : **{df_t['Cout_kg'].mean():.3f} €/kg** | Poids total : **{df_t['_POIDS'].sum():,.0f} kg**")

                st.markdown("<br>", unsafe_allow_html=True)
                df_plot = df_t.sort_values("Marge_Nette")
                df_plot["Statut"] = np.where(df_plot["Rentabilité_%"]<10.0, "Alerte (< 10%)","Sain (> 10%)")
                fig_trans = px.bar(df_plot, x=tour_c, y="Marge_Nette", color="Statut",
                    color_discrete_map={"Alerte (< 10%)":"#E8304A","Sain (> 10%)":"#00C896"},
                    title="Analyse de Rentabilité par Trajet")
                fig_trans.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_trans, use_container_width=True)

                if st.button("GÉNÉRER L'AUDIT DE RENTABILITÉ (IA)", use_container_width=True):
                    with st.spinner("Analyse approfondie en cours..."):
                        top3     = df_t.nsmallest(3,"Marge_Nette")
                        pires_s  = ", ".join([f"{r[tour_c]} ({r['Marge_Nette']:.0f} EUR)" for _,r in top3.iterrows()]) if not top3.empty else "Aucun"
                        st.session_state.analysis_trans = generate_ai_analysis(
                            f"Trajets: {len(df_t)}. Marge globale: {marge_tot:.0f} EUR. Taux: {taux:.1f}%. "
                            f"Déficitaires: {traj_def}. Top 3 pires: {pires_s}. Coût moyen/km: {cout_km:.2f} EUR.{poids_info}"
                        )

                if st.session_state.analysis_trans:
                    rendu = render_report(st.session_state.analysis_trans)
                    st.markdown(f'<div class="report-text">{rendu}</div><br>', unsafe_allow_html=True)
                    pdf_t = generate_expert_pdf("AUDIT FINANCIER TRANSPORT", st.session_state.analysis_trans, [fig_trans])
                    st.download_button("📥 Télécharger le Rapport Officiel (PDF)", pdf_t, "Transport_Logiflo.pdf", use_container_width=True)
