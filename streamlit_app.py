import streamlit as st
import pandas as pd
import numpy as np
import math
import json

st.set_page_config(page_title="Magelan242 Lab PRO", layout="wide")

# --- ФУНКЦІЇ ЗБЕРЕЖЕННЯ ---
def save_settings(data):
    return json.dumps(data, indent=4)

def load_settings(json_file):
    return json.load(json_file)

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #1a1a1a 0%, #C62828 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; border-right: 5px solid white; text-align: right; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 28px; font-weight: 900; }
    .section-head { color: #C62828; font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def calculate_physics(p):
    d = p['target_dist']
    angle_rad = math.radians(p['angle'])
    cos_val = math.cos(angle_rad)
    v0_eff = p['v0']
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    v_dist = v0_eff * math.exp(-k * d)
    energy_j = (p['weight'] * 0.0000647989 * v_dist**2) / 2
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (tof**2) * cos_val
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    w_rad = math.radians(p['wind_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (tof - (d/v0_eff)))
    derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2 if p['enable_der'] else 0
    
    v_mil = abs((y_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    h_mil = abs(((wind_drift + derivation) * 100) / (d / 10) / 0.1) if d > 0 else 0
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)

    return {"v_mil": round(v_mil, 1), "h_mil": round(h_mil, 1), "v_at_dist": int(v_dist), "energy": int(energy_j), "tof": round(tof, 3), "sg": round(sg, 2)}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | PHYSICS & DATA HUB</h1></div>', unsafe_allow_html=True)

# Керування даними
with st.expander("💾 Зберегти / Завантажити профіль набою"):
    col_up, col_down = st.columns(2)
    uploaded_file = col_up.file_uploader("Завантажити JSON профіль", type="json")
    
    # Defaults
    d_v = {"weight": 175.0, "cal": 0.308, "len": 1.24, "bc": 0.450, "v0": 800, "twist": 10.0, "sh": 5.0, "zero": 100}
    if uploaded_file:
        d_v.update(load_settings(uploaded_file))
        st.success("Профіль успішно завантажено!")

# Колонки налаштувань
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown('<div class="section-head">📦 КУЛЯ</div>', unsafe_allow_html=True)
    m_weight = st.number_input("Вага (гран)", 1.0, 1000.0, d_v["weight"])
    m_cal = st.number_input("Калібр (дюйми)", 0.10, 0.60, d_v["cal"], format="%.3f")
    m_len = st.number_input("Довжина (дюйми)", 0.10, 3.00, d_v["len"], format="%.3f")
    m_bc = st.number_input("БК", 0.01, 1.50, d_v["bc"], format="%.3f")
    m_model = st.radio("Драг-модель", ["G7", "G1"])

with c2:
    st.markdown('<div class="section-head">🔫 ЗБРОЯ</div>', unsafe_allow_html=True)
    m_v0 = st.number_input("V0 (м/с)", 100, 1500, d_v["v0"])
    m_twist = st.number_input("Твіст 1:X", 5.0, 20.0, d_v["twist"])
    m_sh = st.number_input("Висота оптики (см)", 0.0, 15.0, d_v["sh"])
    m_zero = st.number_input("Нуль (м)", 10, 1000, d_v["zero"])
    m_der = st.checkbox("Деривація", value=True)

with c3:
    st.markdown('<div class="section-head">🌍 УМОВИ</div>', unsafe_allow_html=True)
    m_dist = st.number_input("Дистанція (м)", 0, 3000, 500)
    m_temp = st.slider("Темп (°C)", -40, 50, 15)
    m_press = st.slider("Тиск (гПа)", 700, 1100, 1013)
    m_w_speed = st.number_input("Вітер (м/с)", 0.0, 25.0, 3.0)
    m_w_hour = st.select_slider("Година вітру", options=list(range(1, 13)), value=3)

with c4:
    st.markdown('<div class="section-head">🎯 РЕЗУЛЬТАТ</div>', unsafe_allow_html=True)
    p = {'weight': m_weight, 'cal': m_cal, 'len': m_len, 'bc': m_bc, 'model': m_model, 'v0': m_v0, 'twist': m_twist, 'sh': m_sh, 'zero': m_zero, 'enable_der': m_der, 'temp': m_temp, 'press': m_press, 'target_dist': m_dist, 'angle': 0, 'w_speed': m_w_speed, 'wind_hour': m_w_hour}
    res = calculate_physics(p)
    
    st.markdown(f'<div class="hud-card"><div class="hud-label">MIL Vertical</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hud-card"><div class="hud-label">MIL Horizontal</div><div class="hud-value">↔ {res["h_mil"]}</div></div>', unsafe_allow_html=True)
    st.info(f"SG: {res['sg']} | ToF: {res['tof']}s")

# Кнопка скачування профілю
current_data = {"weight": m_weight, "cal": m_cal, "len": m_len, "bc": m_bc, "v0": m_v0, "twist": m_twist, "sh": m_sh, "zero": m_zero}
st.download_button("📥 Скачати поточний профіль набою", data=save_settings(current_data), file_name="ammo_profile.json", mime="application/json")

# ТАБЛИЦЯ
st.divider()
steps = np.arange(0, m_dist + 51, 50)
table_data = []
for s in steps:
    p['target_dist'] = s
    r = calculate_physics(p)
    table_data.append({"М": s, "↑ MIL": r['v_mil'], "↔ MIL": r['h_mil'], "Дж": r['energy'], "м/с": r['v_at_dist']})
st.table(pd.DataFrame(table_data))
