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
from scipy.signal import butter, lfilter

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="KEY ULTIMATE HARMONIC 2 PRO", page_icon="🎧", layout="wide")

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
    .stFileUploader { border: 2px dashed #6366F1; padding: 20px; border-radius: 15px; background: #FFFFFF; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CONSTANTES ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "VOTRE_TOKEN_DE_SECOURS")
CHAT_ID = st.secrets.get("CHAT_ID", "VOTRE_CHAT_ID")

BASE_CAMELOT_MINOR = {'Ab':'1A','G#':'1A','Eb':'2A','D#':'2A','Bb':'3A','A#':'3A','F':'4A','C':'5A','G':'6A','D':'7A','A':'8A','E':'9A','B':'10A','F#':'11A','Gb':'11A','Db':'12A','C#':'12A'}
BASE_CAMELOT_MAJOR = {'B':'1B','F#':'2B','Gb':'2B','Db':'3B','C#':'3B','Ab':'4B','G#':'4B','Eb':'5B','D#':'5B','Bb':'6B','A#':'6B','F':'7B','C':'8B','G':'9B','D':'10B','A':'11B','E':'12B'}
PROFILES = {
    "major": np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]), 
    "minor": np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
}
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# --- FONCTIONS UTILITAIRES ---
def get_camelot_pro(key_mode_str):
    try:
        parts = key_mode_str.split(" ")
        key, mode = parts[0], parts[1].lower()
        if mode in ['minor', 'dorian']: return BASE_CAMELOT_MINOR.get(key, "??")
        else: return BASE_CAMELOT_MAJOR.get(key, "??")
    except: return "??"

def upload_to_telegram(file_buffer, filename, caption):
    try:
        file_buffer.seek(0)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        files = {'document': (filename, file_buffer.read())}
        data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
        response = requests.post(url, files=files, data=data, timeout=30).json()
        return response.get("ok", False)
    except: return False

def get_sine_witness(note_mode_str, key_suffix=""):
    if note_mode_str == "N/A": return ""
    parts = note_mode_str.split(' ')
    note, mode = parts[0], parts[1].lower() if len(parts) > 1 else "major"
    unique_id = f"playBtn_{note}_{mode}_{key_suffix}".replace("#", "sharp").replace(".", "_")
    return components.html(f"""
    <div style="display: flex; align-items: center; justify-content: center; gap: 10px; font-family: sans-serif;">
        <button id="{unique_id}" style="background: #6366F1; color: white; border: none; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 12px;">▶</button>
        <span style="font-size: 9px; font-weight: bold; color: #666;">{note} {mode[:3].upper()}</span>
    </div>
    <script>
    const notesFreq = {{'C':261.63,'C#':277.18,'D':293.66,'D#':311.13,'E':329.63,'F':349.23,'F#':369.99,'G':392.00,'G#':415.30,'A':440.00,'A#':466.16,'B':493.88}};
    let audioCtx = null; let oscillators = []; let gainNode = null;
    document.getElementById('{unique_id}').onclick = function() {{
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (this.innerText === '▶') {{
            this.innerText = '◼'; this.style.background = '#E74C3C';
            gainNode = audioCtx.createGain();
            gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.1, audioCtx.currentTime + 0.1);
            gainNode.connect(audioCtx.destination);
            const isMinor = '{mode}' === 'minor' || '{mode}' === 'dorian';
            const intervals = isMinor ? [0, 3, 7] : [0, 4, 7];
            intervals.forEach(interval => {{
                let osc = audioCtx.createOscillator();
                osc.type = 'triangle';
                let freq = notesFreq['{note}'] * Math.pow(2, interval / 12);
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                osc.connect(gainNode);
                osc.start();
                oscillators.push(osc);
            }});
        }} else {{
            if(gainNode) {{
                gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.1);
                setTimeout(() => {{ oscillators.forEach(o => o.stop()); oscillators = []; }}, 100);
            }}
            this.innerText = '▶'; this.style.background = '#6366F1';
        }}
    }};
    </script>
    """, height=40)

# --- MOTEUR ANALYSE OPTIMISÉ ---
@st.cache_data(show_spinner="Analyse Harmonique Profonde...", ttl=3600)
def get_full_analysis(file_bytes, file_name):
    y, sr = librosa.load(io.BytesIO(file_bytes), sr=22050)
    tuning_offset = librosa.estimate_tuning(y=y, sr=sr)
    y_harm = librosa.effects.hpss(y)[0]
    
    hop_length = 1024
    chroma = librosa.feature.chroma_cens(y=y_harm, sr=sr, hop_length=hop_length, tuning=tuning_offset)
    rms = librosa.feature.rms(y=y_harm, hop_length=hop_length)[0]
    
    duration = librosa.get_duration(y=y, sr=sr)
    step_sec = 10
    step_frames = int(librosa.time_to_frames(step_sec, sr=sr, hop_length=hop_length))
    
    timeline_data, weighted_votes = [], []

    for i in range(0, chroma.shape[1] - step_frames, step_frames):
        window = chroma[:, i:i+step_frames]
        window_rms = np.mean(rms[i:i+step_frames])
        if window_rms < 0.01: continue 
        
        chroma_avg = np.mean(window, axis=1)
        best_score, res_key = -1, ""
        
        for mode, profile in PROFILES.items():
            for n in range(12):
                score = np.corrcoef(chroma_avg, np.roll(profile, n))[0, 1]
                if score > best_score:
                    best_score, res_key = score, f"{NOTES[n]} {mode}"
        
        if res_key:
            weighted_votes.append((res_key, window_rms))
            timeline_data.append({
                "Temps": int(librosa.frames_to_time(i, sr=sr, hop_length=hop_length)),
                "Note": res_key,
                "Confiance": round(float(best_score) * 100, 1)
            })

    if not weighted_votes:
        return {"file_name": file_name, "recommended": {"note": "N/A", "conf": 0, "label": "ERREUR", "bg": "red"}}

    # --- AJOUT RÈGLE : HEURISTIQUE HARMONIQUE (V -> i) ---
    # On compte les occurrences de chaque accord pour détecter les dominantes
    raw_counts = Counter([v[0] for v in weighted_votes])
    
    # Correction : Si on a un accord Majeur qui est la dominante (V) d'un accord mineur présent
    # Exemple : Si Majeur est détecté mais Mi Mineur est aussi présent -> Priorité au Mi Mineur
    final_vote_counts = {}
    for note_mode, weight in weighted_votes:
        note, mode = note_mode.split(' ')
        
        # Logique de redirection : Si "Note Majeur" est la dominante d'une "Note-5 mineur"
        # On transfère une partie du poids à la tonique probable
        idx_current = NOTES.index(note)
        idx_target = (idx_current + 5) % 12 # +5 demi-tons = quinte juste au dessus
        probable_tonic = f"{NOTES[idx_target]} minor"
        
        if mode == "major" and probable_tonic in raw_counts:
            # On booste la tonique mineure car l'accord majeur joue le rôle de dominante
            final_vote_counts[probable_tonic] = final_vote_counts.get(probable_tonic, 0) + (weight * 1.5)
        else:
            final_vote_counts[note_mode] = final_vote_counts.get(note_mode, 0) + weight

    n1 = max(final_vote_counts, key=final_vote_counts.get)
    
    # --- FIN DE RÈGLE ---

    df_tl = pd.DataFrame(timeline_data)
    purity = (len(df_tl[df_tl['Note'] == n1]) / len(df_tl)) * 100
    avg_conf_n1 = df_tl[df_tl['Note'] == n1]['Confiance'].mean()
    
    df_tl['is_stable'] = df_tl['Note'] == df_tl['Note'].shift(1)
    note_solide = df_tl[df_tl['is_stable']]['Note'].mode().iloc[0] if not df_tl[df_tl['is_stable']].empty else n1
    solid_conf = int(df_tl[df_tl['Note'] == note_solide]['Confiance'].mean())

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    musical_score = min(int((purity * 0.4) + (avg_conf_n1 * 0.6)), 100)
    
    if musical_score > 85: label, bg = "NOTE INDISCUTABLE", "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
    elif musical_score > 65: label, bg = "NOTE TRÈS FIABLE", "linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)"
    else: label, bg = "ANALYSE COMPLEXE", "linear-gradient(135deg, #f83600 0%, #f9d423 100%)"

    del y, y_harm, chroma, rms
    gc.collect()

    return {
        "file_name": file_name,
        "recommended": {"note": n1, "conf": musical_score, "label": label, "bg": bg},
        "note_solide": note_solide, "solid_conf": solid_conf,
        "vote": n1, "vote_conf": int(purity),
        "n1": n1, "n2": df_tl['Note'].value_counts().index[1] if len(df_tl['Note'].unique()) > 1 else n1,
        "c1": int(purity), "c2": 0,
        "tempo": int(float(tempo)), "energy": int(np.clip(musical_score/10, 1, 10)),
        "timeline": timeline_data
    }

# --- INTERFACE ---
st.markdown("<h1 style='text-align: center;'>🎧 KEY ULTIMATE HARMONIC 2 PRO</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ OPTIONS")
    if st.button("🧹 VIDER LE CACHE"):
        st.session_state.processed_files = {}
        st.session_state.order_list = []
        st.cache_data.clear()
        gc.collect()
        st.rerun()

if 'processed_files' not in st.session_state: st.session_state.processed_files = {}
if 'order_list' not in st.session_state: st.session_state.order_list = []

files = st.file_uploader("📂 DEPOSEZ VOS TRACKS", type=['mp3', 'wav', 'flac'], accept_multiple_files=True)
tabs = st.tabs(["📁 ANALYSEUR", "🕒 HISTORIQUE"])

with tabs[0]:
    if files:
        for f in files:
            fid = f"{f.name}_{f.size}"
            if fid not in st.session_state.processed_files:
                with st.spinner(f"Analyse en cours : {f.name}..."):
                    f_bytes = f.read()
                    res = get_full_analysis(f_bytes, f.name)
                    if res["recommended"]["note"] != "N/A":
                        tg_cap = (
                            f"🎵 *FICHIER* : {res['file_name']}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔥 *KEY* : {res['recommended']['note']} ({get_camelot_pro(res['recommended']['note'])})\n"
                            f"↳ Confiance : {res['recommended']['conf']}%\n"
                            f"🥁 BPM : {res['tempo']}\n"
                            f"━━━━━━━━━━━━━━━━━━━━"
                        )
                        upload_to_telegram(io.BytesIO(f_bytes), f.name, tg_cap)
                        st.session_state.processed_files[fid] = res
                        st.session_state.order_list.insert(0, fid)

        for fid in st.session_state.order_list:
            res = st.session_state.processed_files[fid]
            with st.expander(f"🎵 {res['file_name']}", expanded=True):
                st.markdown(f"""
                    <div class="final-decision-box" style="background: {res['recommended']['bg']};">
                        <div style="font-size: 1em; text-transform: uppercase; letter-spacing: 2px;">{res['recommended']['label']}</div>
                        <div style="font-size: 4.5em; font-weight: 900; line-height:1; margin: 10px 0;">{res['recommended']['note']}</div>
                        <div style="font-size: 1.8em; font-weight: 700;">{get_camelot_pro(res['recommended']['note'])} • {res['recommended']['conf']}%</div>
                    </div>
                """, unsafe_allow_html=True)

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">DOMINANTE</div><div class="value-custom">{res["vote"]}</div><div>{res["vote_conf"]}% présence</div></div>', unsafe_allow_html=True)
                    get_sine_witness(res["vote"], f"dom_{fid}")
                with c2:
                    st.markdown(f'<div class="metric-container" style="border: 2px solid #FFD700;"><div class="label-custom">💎 SOLIDE</div><div class="value-custom" style="color: #D4AF37;">{res["note_solide"]}</div><div>{res["solid_conf"]}%</div></div>', unsafe_allow_html=True)
                    get_sine_witness(res["note_solide"], f"solid_{fid}")
                with c3: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">BPM</div><div class="value-custom">{res["tempo"]}</div></div>', unsafe_allow_html=True)
                with c4: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">STABILITÉ</div><div style="font-size:0.9em;">🥇 {res["n1"]}</div><div style="font-size:0.9em;">🥈 {res["n2"]}</div></div>', unsafe_allow_html=True)
                with c5: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">ÉNERGIE</div><div class="value-custom">{res["energy"]}/10</div></div>', unsafe_allow_html=True)

                st.plotly_chart(px.scatter(pd.DataFrame(res['timeline']), x="Temps", y="Note", color="Confiance", size="Confiance", template="plotly_white"), use_container_width=True)

with tabs[1]:
    if st.session_state.processed_files:
        hist_data = [{"Fichier": r["file_name"], "Note": r['recommended']['note'], "BPM": r["tempo"], "Confiance": f"{r['recommended']['conf']}%"} for r in st.session_state.processed_files.values()]
        st.dataframe(pd.DataFrame(hist_data), use_container_width=True)
