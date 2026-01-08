import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- БАЗА ДАНИХ КАЛІБРІВ (Середні значення для розрахунків) ---
CALIBER_DB = {
    ".223 Remington (5.56x45)": {"cal": 0.224, "len": 0.90, "weight": 69, "bc": 0.175},
    ".308 Winchester (7.62x51)": {"cal": 0.308, "len": 1.18, "weight": 168, "bc": 0.230},
    ".300 Win Mag": {"cal": 0.308, "len": 1.35, "weight": 190, "bc": 0.265},
    ".338 Lapua Magnum": {"cal": 0.338, "len": 1.62, "weight": 250, "bc": 0.320},
    "6.5 Creedmoor": {"cal": 0.264, "len": 1.32, "weight": 140, "bc": 0.305},
    ".50 BMG": {"cal": 0.510, "len": 2.31, "weight": 750, "bc": 0.490},
    "Кастомний": {"cal": 0.308, "len": 1.18, "weight": 168, "bc": 0.230}
}

st.set_page_config(page_title="Magelan242 PRO", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 15px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 25px;}
    .hud-card { background-color: #FFFFFF; border-left: 10px solid #C62828; padding: 20px; text-align: center; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .hud-label { color: #C62828; font-size: 13px; font-weight: bold; margin-bottom: 5px; }
    .hud-value { color: #000000 !important; font-size: 38px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_ballistics(p):
    v0_eff = p['v0'] * (1 + (p['temp'] - p['v0_temp']) * (p['v0_sens'] / 100))
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (1.0 if p['model'] == "G1" else 0.91)
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    
    # Вертикаль
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # AJ та Вітер
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
    
    # Деривація та Дрейф
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2)
    wind_drift = (cross_w * (t - (p['dist']/v0_eff)))
    
    # Поправки
    v_mil = round(abs(((y_m + aj_shift) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0
    h_mil = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0
    
    # SG (Міллер)
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)
    
    return v_mil, h_mil, round(t, 3), round(sg, 2)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : ВІЙСЬКОВИЙ БАЛІСТИЧНИЙ ХАБ</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("🗃️ Вибір Калібру")
    selected_name = st.selectbox("Оберіть набій зі списку:", list(CALIBER_DB.keys()))
    base_data = CALIBER_DB[selected_name]
    
    st.divider()
    st.header("🔧 Тонке налаштування")
    cal_val = st.number_input("Діаметр кулі (дюйми)", 0.200, 0.600, base_data['cal'], format="%.3f")
    weight_val = st.number_input("Вага кулі (гран)", 10.0, 800.0, float(base_data['weight']))
    len_val = st.number_input("Довжина кулі (дюйми)", 0.3, 3.0, base_data['len'])
    bc_val = st.number_input("Балістичний коефіцієнт", 0.05, 1.2, base_data['bc'], format="%.3f")
    
    st.divider()
    st.header("🔫 Параметри зброї")
    side = st.radio("Нарізи", ["Правобічні", "Лівобічні"])
    twist = st.number_input("Крок нарізів (1:X дюймів)", 5.0, 20.0, 10.0)
    v0 = st.number_input("V0 швидкість (м/с)", 200, 1500, 825)

# ОСНОВНА ПАНЕЛЬ УМОВ
st.markdown("### 📍 Поточні умови стрільби")
c1, c2, c3, c4 = st.columns(4)
dist = c1.number_input("Дистанція (м)", 0, 4000, 500, step=10)
temp = c2.number_input("Температура (°C)", -40, 50, 15)
press = c3.number_input("Тиск (гПа)", 800, 1100, 1013)
w_speed = c4.number_input("Швидкість вітру (м/с)", 0.0, 25.0, 4.0)

# ДРУГИЙ РЯД УМОВ
c5, c6, c7, c8 = st.columns(4)
w_hour = c5.select_slider("Годинник вітру", options=list(range(1, 13)), value=3)
angle = c6.number_input("Кут місця цілі (°)", -60, 60, 0)
model = c7.radio("Модель", ["G7", "G1"], horizontal=True)
sh = c8.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)

# РОЗРАХУНОК
params = {
    'cal': cal_val, 'weight': weight_val, 'len': len_val, 'bc': bc_val,
    'twist': twist, 'twist_side': side, 'v0': v0, 'sh': sh, 'zero': 100,
    'temp': temp, 'press': press, 'dist': dist, 'angle': angle,
    'w_speed': w_speed, 'wind_hour': w_hour, 'model': model,
    'v0_temp': 15, 'v0_sens': 0.2
}
res_v, res_h, res_t, res_sg = calculate_ballistics(params)

# КАРТКИ РЕЗУЛЬТАТІВ
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4 = st.columns(4)
r1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ (MIL)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТАЛЬ (MIL)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС ПОЛЬОТУ</div><div class="hud-value">{res_t}с</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">СТАБІЛЬНІСТЬ (SG)</div><div class="hud-value">{res_sg}</div></div>', unsafe_allow_html=True)

# ГРАФІК ТРАЄКТОРІЇ
st.divider()
st.subheader("📊 Візуалізація польоту кулі")
# Створення масиву для графіка
ranges = np.arange(0, dist + 100, 10)
drops = []
for d in ranges:
    params['dist'] = d
    v, _, _, _ = calculate_ballistics(params)
    drops.append(v)

fig = go.Figure()
fig.add_trace(go.Scatter(x=ranges, y=drops, mode='lines', name='Поправка', line=dict(color='#C62828', width=4)))
fig.update_layout(template="plotly_dark", xaxis_title="Дистанція (м)", yaxis_title="Поправка (MIL)", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)
