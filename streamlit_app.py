import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- ГЛОБАЛЬНА БАЗА НАБОЇВ (Presets) ---
AMMO_DB = {
    "5.45x39 7N6 (AK-74)": {"cal": 0.214, "len": 0.98, "weight": 53.0, "bc": 0.168, "model": "G7", "v0": 880},
    "5.56x45 (.223 Rem) 62gr": {"cal": 0.224, "len": 0.93, "weight": 62.0, "bc": 0.151, "model": "G7", "v0": 915},
    "7.62x39 (AK-47/SKS)": {"cal": 0.311, "len": 0.93, "weight": 123.0, "bc": 0.145, "model": "G7", "v0": 715},
    "7.62x51 (.308 Win) 175gr": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "7.62x54R 174gr (SVD/LPS)": {"cal": 0.311, "len": 1.25, "weight": 174.0, "bc": 0.235, "model": "G7", "v0": 820},
    "6.5 Creedmoor 140gr": {"cal": 0.264, "len": 1.35, "weight": 140.0, "bc": 0.315, "model": "G7", "v0": 825},
    ".300 Win Mag 200gr": {"cal": 0.308, "len": 1.45, "weight": 200.0, "bc": 0.285, "model": "G7", "v0": 870},
    ".338 Lapua Mag 300gr": {"cal": 0.338, "len": 1.78, "weight": 300.0, "bc": 0.368, "model": "G7", "v0": 825},
    ".375 CheyTac 350gr": {"cal": 0.375, "len": 2.05, "weight": 350.0, "bc": 0.405, "model": "G7", "v0": 930},
    ".50 BMG (12.7x99) 750gr": {"cal": 0.510, "len": 2.31, "weight": 750.0, "bc": 0.490, "model": "G7", "v0": 850},
    "Кастомний / Ручне введення": {"cal": 0.308, "len": 1.0, "weight": 150.0, "bc": 0.200, "model": "G7", "v0": 800}
}

st.set_page_config(page_title="Magelan242 Extreme Custom", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 15px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 25px;}
    .hud-card { background-color: #FFFFFF; border-left: 10px solid #C62828; padding: 15px; text-align: center; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; margin-bottom: 3px; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 28px !important; font-weight: 900 !important; }
    .sidebar-header { color: #C62828; font-weight: bold; border-bottom: 1px solid #C62828; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_ballistics(p):
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * (0.2 / 100))
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    v_dist = v0_eff * math.exp(-k * p['dist'])
    energy_j = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    
    aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2)
    wind_drift = (cross_w * (t - (p['dist']/v0_eff)))
    
    v_mil = round(abs(((y_m + aj_shift) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    h_mil = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)
    
    return v_mil, h_mil, round(t, 3), int(energy_j), round(v_dist, 1), round(sg, 2)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : EXTREME CUSTOM HUD</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-header">📦 БАЗА НАБОЇВ (ПРЕСЕТИ)</div>', unsafe_allow_html=True)
    choice = st.selectbox("Вибрати шаблон:", list(AMMO_DB.keys()))
    base = AMMO_DB[choice]
    
    st.markdown('<div class="sidebar-header">📏 ГЕОМЕТРІЯ КУЛІ (РУЧНЕ)</div>', unsafe_allow_html=True)
    m_cal = st.number_input("Діаметр кулі (дюйми)", 0.100, 0.600, base['cal'], format="%.3f")
    m_len = st.number_input("Довжина кулі (дюйми)", 0.200, 3.000, base['len'], format="%.3f")
    m_weight = st.number_input("Вага кулі (гран)", 1.0, 1000.0, base['weight'])
    
    st.markdown('<div class="sidebar-header">🚀 БАЛІСТИКА (РУЧНЕ)</div>', unsafe_allow_html=True)
    m_v0 = st.number_input("Швидкість V0 (м/с)", 100, 1500, base['v0'])
    m_bc = st.number_input("БК (коефіцієнт)", 0.01, 1.50, base['bc'], format="%.3f")
    m_model = st.radio("Драг-модель", ["G7", "G1"], index=0 if base['model']=="G7" else 1, horizontal=True)
    
    st.markdown('<div class="sidebar-header">🔫 ЗБРОЯ</div>', unsafe_allow_html=True)
    m_twist = st.number_input("Твіст 1:", 5.0, 24.0, 10.0)
    m_side = st.radio("Напрямок нарізів", ["Правобічні", "Лівобічні"], horizontal=True)
    m_sh = st.number_input("Висота прицілу (см)", 0.0, 20.0, 5.0)

# ПАНЕЛЬ УМОВ
st.markdown("### 🌍 Умови та Дистанція")
c1, c2, c3, c4 = st.columns(4)
dist = c1.number_input("Дистанція (м)", 0, 4000, 500, step=10)
temp = c2.number_input("Температура (°C)", -50, 60, 15)
press = c3.number_input("Тиск (гПа)", 700, 1150, 1013)
w_speed = c4.number_input("Вітер (м/с)", 0.0, 40.0, 4.0)

c5, c6, c7 = st.columns([1, 1, 2])
w_hour = c5.select_slider("Годинник вітру", options=list(range(1, 13)), value=3)
angle = c6.number_input("Кут місця цілі (°)", -80, 80, 0)

# РОЗРАХУНОК
params = {
    'cal': m_cal, 'len': m_len, 'weight': m_weight, 'v0': m_v0, 'bc': m_bc, 'model': m_model,
    'twist': m_twist, 'twist_side': m_side, 'sh': m_sh, 'dist': dist, 'temp': temp, 
    'press': press, 'w_speed': w_speed, 'wind_hour': w_hour, 'angle': angle, 'zero': 100
}
res_v, res_h, res_t, res_e, res_v_dist, res_sg = calculate_ballistics(params)

# ВИВІД КАРТОК
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f'<div class="hud-card"><div class="hud-label">MIL Вертикаль</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">MIL Горизонт</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{res_e}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">V цілі (м/с)</div><div class="hud-value">{res_v_dist}</div></div>', unsafe_allow_html=True)
r5.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність (SG)</div><div class="hud-value">{res_sg}</div></div>', unsafe_allow_html=True)

# АНАЛІТИКА
st.divider()
st.subheader("📊 Детальний аналіз по дистанції")
if st.checkbox("Показати таблицю поправок"):
    rows = []
    for d in range(0, dist + 201, 50):
        params['dist'] = d
        v, h, t, e, vel, sg = calculate_ballistics(params)
        rows.append({"М": d, "V (MIL)": v, "H (MIL)": h, "Дж": e, "м/с": vel, "SG": sg})
    st.table(pd.DataFrame(rows))
