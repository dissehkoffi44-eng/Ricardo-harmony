import streamlit as st
import librosa
import numpy as np
import pandas as pd
import plotly.express as px
from collections import Counter
import io
import streamlit.components.v1 as components
import requests  
import gc                 

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="KEY V7 ULTIMATE HARMONIC", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    .metric-container { background: white; padding: 20px; border-radius: 15px; border: 1px solid #E0E0E0; text-align: center; height: 100%; transition: transform 0.3s; }
    .metric-container:hover { transform: translateY(-5px); border-color: #6366F1; }
    .label-custom { color: #666; font-size: 0.9em; font-weight: bold; margin-bottom: 5px; }
    .value-custom { font-size: 1.6em; font-weight: 800; color: #1A1A1A; }
    .final-decision-box { 
        padding: 25px; border-radius: 15px; text-align: center; margin-bottom: 25px;
        color: white; box-shadow: 0 12px 24px rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTES HARMONIQUES ---
BASE_CAMELOT_MINOR = {'Ab':'1A','G#':'1A','Eb':'2A','D#':'2A','Bb':'3A','A#':'3A','F':'4A','C':'5A','G':'6A','D':'7A','A':'8A','E':'9A','B':'10A','F#':'11A','Gb':'11A','Db':'12A','C#':'12A'}
BASE_CAMELOT_MAJOR = {'B':'1B','F#':'2B','Gb':'2B','Db':'3B','C#':'3B','Ab':'4B','G#':'4B','Eb':'5B','D#':'5B','Bb':'6B','A#':'6B','F':'7B','C':'8B','G':'9B','D':'10B','A':'11B','E':'12B'}

RELATIVES = {
    'C major': 'A minor', 'C# major': 'A# minor', 'D major': 'B minor', 'D# major': 'C minor', 'E major': 'C# minor', 'F major': 'D minor',
    'F# major': 'D# minor', 'G major': 'E minor', 'G# major': 'F minor', 'A major': 'F# minor', 'A# major': 'G minor', 'B major': 'G# minor'
}
RELATIVES.update({v: k for k, v in RELATIVES.items()})

QUINTES = {
    'C': 'G', 'C#': 'G#', 'D': 'A', 'D#': 'A#', 'E': 'B', 'F': 'C', 
    'F#': 'C#', 'G': 'D', 'G#': 'D#', 'A': 'E', 'A#': 'F', 'B': 'F#'
}

def get_camelot_pro(key_mode_str):
    try:
        parts = key_mode_str.split(" ")
        key, mode = parts[0], parts[1].lower()
        if mode in ['minor', 'dorian']: return BASE_CAMELOT_MINOR.get(key, "??")
        else: return BASE_CAMELOT_MAJOR.get(key, "??")
    except: return "??"

# --- FONCTIONS TECHNIQUES ---
def analyze_segment(y, sr, tuning=0.0):
    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    chroma = librosa.feature.chroma_cens(y=y, sr=sr, hop_length=512, n_chroma=12, tuning=tuning)
    chroma_avg = np.mean(chroma, axis=1)
    PROFILES = {
        "major": [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88], 
        "minor": [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    }
    best_score, res_key = -1, ""
    for mode, profile in PROFILES.items():
        for i in range(12):
            score = np.corrcoef(chroma_avg, np.roll(profile, i))[0, 1]
            if score > best_score: best_score, res_key = score, f"{NOTES[i]} {mode}"
    return res_key, best_score

@st.cache_data(show_spinner="Analyse Harmonique Profonde...", max_entries=20)
def get_full_analysis(file_bytes, file_name):
    y, sr = librosa.load(io.BytesIO(file_bytes), sr=None, duration=210)
    tuning_offset = librosa.estimate_tuning(y=y, sr=sr)
    y_harm = librosa.effects.hpss(y)[0]
    duration = librosa.get_duration(y=y, sr=sr)
    timeline_data, votes = [], []
    
    for start_t in range(0, int(duration) - 10, 10):
        y_seg = y_harm[int(start_t*sr):int((start_t+10)*sr)]
        key_seg, score_seg = analyze_segment(y_seg, sr, tuning=tuning_offset)
        votes.append(key_seg)
        timeline_data.append({"Temps": start_t, "Note": key_seg, "Confiance": round(float(score_seg) * 100, 1)})
    
    df_tl = pd.DataFrame(timeline_data)
    counts = Counter(votes)
    top_votes = counts.most_common(2)
    n1 = top_votes[0][0]
    n2 = top_votes[1][0] if len(top_votes) > 1 else n1
    
    # --- CALCUL DU SCORE AVEC RÈGLES DE MUSIQUE (TIERCES, QUINTES, RELATIVES) ---
    purity = (counts[n1] / len(votes)) * 100
    avg_conf_n1 = df_tl[df_tl['Note'] == n1]['Confiance'].mean()
    musical_bonus = 0
    
    # Extraction Camelot pour comparaison
    c1 = get_camelot_pro(n1)
    c2 = get_camelot_pro(n2)
    
    if c1 != "??" and c2 != "??" and n1 != n2:
        val1, mod1 = int(c1[:-1]), c1[-1]
        val2, mod2 = int(c2[:-1]), c2[-1]
        
        # 1. Règle des Quintes (Voisins Camelot : 8A -> 9A)
        if mod1 == mod2 and (abs(val1 - val2) == 1 or abs(val1 - val2) == 11):
            musical_bonus += 15
        # 2. Règle des Relatives (Vertical Camelot : 8A -> 8B)
        elif val1 == val2 and mod1 != mod2:
            musical_bonus += 15
        # 3. RÈGLE DES TIERCES / DIAGONAL (ex: 8A -> 11B ou 10A -> 1B)
        elif (mod1 == 'A' and mod2 == 'B' and (val2 == (val1 + 3) % 12 or val2 == val1 + 3)) or \
             (mod1 == 'B' and mod2 == 'A' and (val2 == (val1 - 3) % 12 or val2 == val1 - 3)):
            musical_bonus += 20

    musical_score = min(int((purity * 0.5) + (avg_conf_n1 * 0.5) + musical_bonus), 100)

    # Détermination du Label
    if musical_score > 88:
        label, bg = "NOTE INDISCUTABLE", "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
    elif musical_score > 68:
        label, bg = "NOTE TRÈS FIABLE", "linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)"
    else:
        label, bg = "ANALYSE COMPLEXE", "linear-gradient(135deg, #f83600 0%, #f9d423 100%)"

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    
    return {
        "file_name": file_name,
        "recommended": {"note": n1, "conf": musical_score, "label": label, "bg": bg},
        "vote": n1, "vote_conf": int(purity),
        "n1": n1, "c1": int(purity), "n2": n2, "c2": int((counts[n2]/len(votes))*100),
        "tempo": int(float(tempo)), "energy": int(np.clip(musical_score/10, 1, 10)),
        "timeline": timeline_data
    }

# --- INTERFACE ---
st.markdown("<h1 style='text-align: center;'>🎧 KEY V7 ULTIMATE HARMONIC</h1>", unsafe_allow_html=True)

if 'processed_files' not in st.session_state: st.session_state.processed_files = {}
if 'order_list' not in st.session_state: st.session_state.order_list = []

files = st.file_uploader("📂 DEPOSEZ VOS TRACKS", type=['mp3', 'wav', 'flac'], accept_multiple_files=True)

if files:
    for f in files:
        fid = f"{f.name}_{f.size}"
        if fid not in st.session_state.processed_files:
            with st.spinner(f"Analyse Harmonique : {f.name}"):
                res = get_full_analysis(f.read(), f.name)
                st.session_state.processed_files[fid] = res
                st.session_state.order_list.insert(0, fid)

    for fid in st.session_state.order_list:
        res = st.session_state.processed_files[fid]
        with st.expander(f"🎵 {res['file_name']}", expanded=True):
            st.markdown(f"""
                <div class="final-decision-box" style="background: {res['recommended']['bg']};">
                    <div style="font-size: 1em; text-transform: uppercase; letter-spacing: 2px;">{res['recommended']['label']}</div>
                    <div style="font-size: 4.5em; font-weight: 900; line-height:1; margin: 10px 0;">{res['recommended']['note']}</div>
                    <div style="font-size: 1.8em; font-weight: 700;">{get_camelot_pro(res['recommended']['note'])} • {res['recommended']['conf']}% PRÉCISION THÉORIQUE</div>
                </div>
            """, unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-container"><div class="label-custom">DOMINANTE</div><div class="value-custom">{res["vote"]}</div><div>{res["vote_conf"]}% présence</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-container"><div class="label-custom">BPM</div><div class="value-custom">{res["tempo"]}</div><div>BPM détecté</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-container"><div class="label-custom">STABILITÉ 1 & 2</div><div style="font-size:0.9em;">🥇 {res["n1"]} ({res["c1"]}%)</div><div style="font-size:0.9em;">🥈 {res["n2"]} ({res["c2"]}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-container"><div class="label-custom">ÉNERGIE</div><div class="value-custom">{res["energy"]}/10</div><div>Harmonique</div></div>', unsafe_allow_html=True)

            st.plotly_chart(px.scatter(pd.DataFrame(res['timeline']), x="Temps", y="Note", color="Confiance", size="Confiance", template="plotly_white", title="Analyse Temporelle & Validation des Lois Harmoniques"), use_container_width=True)
