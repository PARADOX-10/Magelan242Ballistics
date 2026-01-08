import streamlit as st
import pandas as pd
import numpy as np
import math

# --- БАЗА .300 WM ---
AMMO_DB = {
    ".300 WM Berger Hybrid 215gr": {"cal": 0.308, "len": 1.60, "weight": 215.0, "bc": 0.354, "model": "G7", "v0": 850},
    ".300 WM Hornady ELD-M 208gr": {"cal": 0.308, "len": 1.54, "weight": 208.0, "bc": 0.320, "model": "G7", "v0": 855},
    "7.62x51 M118LR (175gr)": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "Кастомный патрон": {"cal": 0.308, "len": 1.2, "weight": 175.0, "bc": 0.250, "model": "G7", "v0": 800}
}

st.set_page_config(page_title="Magelan242 Dynamic HUD", layout="wide")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #C62828 0%, #1a1a1a 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid white; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 26px; font-weight: 900; }
    .lead-value { color: #00FF00 !important; font-size: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛЛИСТИКА + УПРЕЖДЕНИЕ ---
def calculate_lead(p, d, angle_deg, target_speed_kmh):
    # Угол и эффективная дистанция
    angle_rad = math.radians(angle_deg)
    cos_val = math.cos(angle_rad)
    
    # Атмосфера и БК
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    # Время полета (ToF)
    tof = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    
    # Вертикаль (MIL)
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (tof**2) * cos_val
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    v_mil = abs((y_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    
    # Горизонталь (Ветер)
    w_rad = math.radians(p['wind_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (tof - (d/v0_eff)))
    h_mil_wind = (wind_drift * 100) / (d / 10) / 0.1 if d > 0 else 0
    
    # УПРЕЖДЕНИЕ (Lead)
    # Перевод скорости в м/с: км/ч / 3.6
    v_target_ms = target_speed_kmh / 3.6
    # Дистанция, которую пройдет цель за время полета пули
    lead_distance_m = v_target_ms * tof
    # Перевод в MIL
    lead_mil = (lead_distance_m * 100) / (d / 10) / 0.1 if d > 0 else 0
    
    return {
        "v_mil": round(v_mil, 1),
        "h_mil_wind": round(abs(h_mil_wind), 1),
        "lead_mil": round(lead_mil, 1),
        "tof": round(tof, 3),
        "cos": cos_val
    }

# --- ИНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | DYNAMIC TARGET HUD</h1></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Конфигурация")
    bullet = st.selectbox("Набой:", list(AMMO_DB.keys()))
    b = AMMO_DB[bullet]
    v0 = st.number_input("V0 м/с", 100, 1200, b['v0'])
    bc = st.number_input("БК (G7)", 0.1, 1.0, b['bc'], format="%.3f")
    sh = st.number_input("Высота прицела (см)", 0.0, 15.0, 5.0)

# ОСНОВНОЙ РАСЧЕТНЫЙ МОДУЛЬ
col_env, col_target, col_hud = st.columns([1, 1, 1.5])

with col_env:
    st.subheader("🌍 Среда")
    dist = st.slider("Дистанция (м)", 0, 1500, 600, step=10)
    temp = st.number_input("Температура (°C)", -30, 50, 15)
    press = st.number_input("Давление (гПа)", 800, 1100, 1013)
    angle = st.slider("Угол цели (°)", -45, 45, 0)

with col_target:
    st.subheader("🏃 Цель и Ветер")
    target_speed = st.slider("Скорость цели (км/ч)", 0.0, 25.0, 0.0, step=0.5)
    st.caption("5 км/ч — шаг, 12 км/ч — бег")
    
    st.markdown("---")
    w_speed = st.slider("Ветер (м/с)", 0.0, 15.0, 3.0)
    w_hour = st.select_slider("Ветер (час)", options=list(range(1, 13)), value=3)

# РАСЧЕТ
params = {'v0': v0, 'bc': bc, 'model': "G7", 'sh': sh, 'temp': temp, 'press': press, 'w_speed': w_speed, 'wind_hour': w_hour, 'zero': 100}
res = calculate_lead(params, dist, angle, target_speed)

with col_hud:
    st.subheader("🎯 Огневое решение")
    
    r1, r2 = st.columns(2)
    r1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль (MIL)</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    r2.markdown(f'<div class="hud-card"><div class="hud-label">Ветер (MIL)</div><div class="hud-value">↔ {res["h_mil_wind"]}</div></div>', unsafe_allow_html=True)
    
    # БЛОК УПРЕЖДЕНИЯ
    st.markdown(f'<div class="hud-card"><div class="hud-label">УПРЕЖДЕНИЕ (MIL)</div><div class="hud-value lead-value">⟹ {res["lead_mil"]}</div><div style="font-size:10px; color:#888;">Время полета: {res["tof"]} сек</div></div>', unsafe_allow_html=True)
    
    if target_speed > 0:
        st.info(f"Суммарный горизонтальный вынос: {round(res['h_mil_wind'] + res['lead_mil'], 1)} MIL (если ветер и цель в одну сторону)")

