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
st.set_page_config(page_title="KEY ULTIMATE HARMONIC 2", page_icon="🎧", layout="wide")

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

# --- CONFIGURATION API & CONSTANTES ---
TELEGRAM_TOKEN = "7751365982:AAFLbeRoPsDx5OyIOlsgHcGKpI12hopzCYo"
CHAT_ID = "-1003602454394" 

BASE_CAMELOT_MINOR = {'Ab':'1A','G#':'1A','Eb':'2A','D#':'2A','Bb':'3A','A#':'3A','F':'4A','C':'5A','G':'6A','D':'7A','A':'8A','E':'9A','B':'10A','F#':'11A','Gb':'11A','Db':'12A','C#':'12A'}
BASE_CAMELOT_MAJOR = {'B':'1B','F#':'2B','Gb':'2B','Db':'3B','C#':'3B','Ab':'4B','G#':'4B','Eb':'5B','D#':'5B','Bb':'6B','A#':'6B','F':'7B','C':'8B','G':'9B','D':'10B','A':'11B','E':'12B'}

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
    if note_mode_str == "N/A" or not note_mode_str: return ""
    parts = note_mode_str.split(' ')
    note = parts[0]
    mode = parts[1].lower() if len(parts) > 1 else "major"
    unique_id = f"playBtn_{note}_{mode}_{key_suffix}".replace("#", "sharp").replace(".", "_")
    return components.html(f"""
    <div style="display: flex; align-items: center; justify-content: center; gap: 8px; font-family: sans-serif;">
        <button id="{unique_id}" style="background: #6366F1; color: white; border: none; border-radius: 50%; width: 24px; height: 24px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 10px;">▶</button>
        <span style="font-size: 9px; font-weight: bold; color: #666;">TESTER {note} {mode[:3].upper()}</span>
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
    """, height=35)

# --- MOTEUR ANALYSE ---
def analyze_segment(y, sr, tuning=0.0):
    nyq = 0.5 * sr
    low = 60 / nyq
    high = 1000 / nyq
    b, a = butter(4, [low, high], btype='band')
    y_filtered = lfilter(b, a, y)
    rms = np.sqrt(np.mean(y_filtered**2))
    if rms < 0.01: return None, 0.0

    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    chroma = librosa.feature.chroma_cens(y=y_filtered, sr=sr, hop_length=1024, n_chroma=12, tuning=tuning)
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
    y, sr = librosa.load(io.BytesIO(file_bytes), sr=22050)
    tuning_offset = librosa.estimate_tuning(y=y, sr=sr)
    y_harm = librosa.effects.hpss(y)[0]
    duration = librosa.get_duration(y=y, sr=sr)
    timeline_data, votes = [], []
    
    progress_bar = st.progress(0)
    step = 10
    for i, start_t in enumerate(range(0, int(duration) - step, step)):
        y_seg = y_harm[int(start_t*sr):int((start_t+step)*sr)]
        key_seg, score_seg = analyze_segment(y_seg, sr, tuning=tuning_offset)
        if key_seg:
            votes.append(key_seg)
            timeline_data.append({"Temps": start_t, "Note": key_seg, "Confiance": round(float(score_seg) * 100, 1)})
        progress_bar.progress(min(start_t / duration, 1.0))
    
    progress_bar.empty()
    if not votes: return {"file_name": file_name, "recommended": {"note": "N/A", "conf": 0, "label": "ERREUR", "bg": "red"}}

    df_tl = pd.DataFrame(timeline_data)
    df_tl['is_stable'] = df_tl['Note'] == df_tl['Note'].shift(1)
    last_note = df_tl['Note'].iloc[-1]
    
    stability_scores = {}
    for note in df_tl['Note'].unique():
        note_mask = df_tl['Note'] == note
        count = note_mask.sum()
        avg_conf = df_tl[note_mask]['Confiance'].mean()
        repos_bonus = df_tl[note_mask & df_tl['is_stable']].shape[0] * 3.0
        final_bonus = 30 if note == last_note else 0
        stability_scores[note] = (count * 0.2) + (avg_conf * 0.2) + (repos_bonus * 0.3) + final_bonus

    note_solide = max(stability_scores, key=stability_scores.get)
    counts = Counter(votes)
    n1 = counts.most_common(1)[0][0]
    n2 = counts.most_common(2)[1][0] if len(counts)>1 else n1
    
    rec_note = note_solide if df_tl[df_tl['Note'] == note_solide]['Confiance'].mean() >= 70 else n1
    final_conf = int(df_tl[df_tl['Note'] == rec_note]['Confiance'].mean())

    if final_conf < 70:
        label, bg = "ANALYSE INCERTAINE (<70%)", "linear-gradient(135deg, #232526 0%, #414345 100%)"
    elif final_conf > 88:
        label, bg = "TONIQUE INDISCUTABLE", "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
    else:
        label, bg = "TONIQUE VALIDÉE", "linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)"

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    
    return {
        "file_name": file_name,
        "recommended": {"note": rec_note, "conf": final_conf, "label": label, "bg": bg},
        "note_solide": note_solide, "solid_conf": int(df_tl[df_tl['Note'] == note_solide]['Confiance'].mean()),
        "vote": n1, "vote_conf": int(df_tl[df_tl['Note'] == n1]['Confiance'].mean()),
        "n1": n1, "c1": int(df_tl[df_tl['Note'] == n1]['Confiance'].mean()), 
        "n2": n2, "c2": int(df_tl[df_tl['Note'] == n2]['Confiance'].mean()),
        "tempo": int(float(tempo)), "energy": int(np.clip(final_conf/10, 1, 10)),
        "timeline": timeline_data
    }

# --- INTERFACE ---
st.markdown("<h1 style='text-align: center;'>🎧 KEY ULTIMATE HARMONIC 2</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ MAINTENANCE")
    if st.button("🧹 VIDER TOUT"):
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
                with st.spinner(f"Analyse : {f.name}..."):
                    f_bytes = f.read()
                    res = get_full_analysis(f_bytes, f.name)
                    if res["recommended"]["note"] != "N/A":
                        # Rapport Telegram (Optionnel)
                        tg_cap = f"🎵 *FICHIER* : {res['file_name']}\n🏆 *RECO* : {res['recommended']['note']} ({get_camelot_pro(res['recommended']['note'])})"
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
                
                # Témoin pour la note recommandée principale
                get_sine_witness(res['recommended']['note'], f"main_{fid}")

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">FRÉQUENCE (TOP 1)</div><div class="value-custom">{res["vote"]}</div><div style="font-weight:bold; color:#6366F1;">{get_camelot_pro(res["vote"])} • {res["vote_conf"]}%</div></div>', unsafe_allow_html=True)
                    get_sine_witness(res["vote"], f"dom_{fid}")
                with c2:
                    st.markdown(f'<div class="metric-container" style="border: 2px solid #FFD700;"><div class="label-custom">💎 REPOS (TONIQUE)</div><div class="value-custom" style="color: #D4AF37;">{res["note_solide"]}</div><div style="font-weight:bold; color:#D4AF37;">{get_camelot_pro(res["note_solide"])} • {res["solid_conf"]}%</div></div>', unsafe_allow_html=True)
                    get_sine_witness(res["note_solide"], f"solid_{fid}")
                with c3: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">BPM</div><div class="value-custom">{res["tempo"]}</div><div style="font-size:0.8em; color:#999;">Rythme</div></div>', unsafe_allow_html=True)
                with c4: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">MODALITÉS</div><div style="font-size:0.85em; font-weight:bold;">🥇 {res["n1"]} : {res["c1"]}%</div><div style="font-size:0.85em; font-weight:bold;">🥈 {res["n2"]} : {res["c2"]}%</div></div>', unsafe_allow_html=True)
                    # Double témoin pour les deux modalités
                    col_sub1, col_sub2 = st.columns(2)
                    with col_sub1: get_sine_witness(res["n1"], f"n1_{fid}")
                    with col_sub2: get_sine_witness(res["n2"], f"n2_{fid}")
                with c5: 
                    st.markdown(f'<div class="metric-container"><div class="label-custom">ÉNERGIE</div><div class="value-custom">{res["energy"]}/10</div><div style="font-size:0.8em; color:#999;">Harmonie</div></div>', unsafe_allow_html=True)

                st.plotly_chart(px.scatter(pd.DataFrame(res['timeline']), x="Temps", y="Note", color="Confiance", size="Confiance", template="plotly_white"), use_container_width=True)

with tabs[1]:
    if st.session_state.processed_files:
        hist_data = [{"Fichier": r["file_name"], "Note": f"{r['recommended']['note']} ({get_camelot_pro(r['recommended']['note'])})", "Confiance": f"{r['recommended']['conf']}%", "BPM": r["tempo"]} for r in st.session_state.processed_files.values()]
        st.dataframe(pd.DataFrame(hist_data), use_container_width=True)
