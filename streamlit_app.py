import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- БАЗА ДАНИХ КАЛІБРІВ (Вшиті параметри для точності) ---
CALIBER_DB = {
    ".223 Remington (5.56x45)": {"cal": 0.224, "len": 0.90, "weight": 69, "bc": 0.175},
    ".308 Winchester (7.62x51)": {"cal": 0.308, "len": 1.18, "weight": 168, "bc": 0.230},
    ".300 Win Mag": {"cal": 0.308, "len": 1.35, "weight": 190, "bc": 0.265},
    ".338 Lapua Magnum": {"cal": 0.338, "len": 1.62, "weight": 250, "bc": 0.320},
    "6.5 Creedmoor": {"cal": 0.264, "len": 1.32, "weight": 140, "bc": 0.305},
    ".50 BMG": {"cal": 0.510, "len": 2.31, "weight": 750, "bc": 0.490}
}

st.set_page_config(page_title="Magelan242 PRO", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 15px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 25px;}
    .hud-card { background-color: #FFFFFF; border-left: 10px solid #C62828; padding: 15px; text-align: center; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; margin-bottom: 3px; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 28px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_ballistics(p):
    # Корекція швидкості від температури
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * (0.2 / 100))
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    # Час польоту та швидкість на дистанції
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    v_dist = v0_eff * math.exp(-k * p['dist'])
    
    # Енергія в Джоулях: (маса в кг * швидкість^2) / 2
    # 1 гран = 0.0000647989 кг
    mass_kg = p['weight'] * 0.0000647989
    energy_j = (mass_kg * v_dist**2) / 2
    
    # Вертикальна поправка
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Вітер та AJ
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
    
    # Деривація
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2)
    wind_drift = (cross_w * (t - (p['dist']/v0_eff)))
    
    # Результати в MIL
    v_mil = round(abs(((y_m + aj_shift) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    h_mil = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    
    return v_mil, h_mil, round(t, 3), int(energy_j), round(v_dist, 1)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : БАЛІСТИКА ТА ЕНЕРГІЯ</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("🎯 Калібр")
    caliber_choice = st.selectbox("Виберіть набій:", list(CALIBER_DB.keys()))
    caliber_data = CALIBER_DB[caliber_choice]
    
    # Автоматично заповнюємо дані, приховуючи редагування діаметра та довжини
    st.info(f"Діаметр: {caliber_data['cal']}″ | Довжина: {caliber_data['len']}″")
    
    st.divider()
    st.header("🔧 Налаштування")
    v0 = st.number_input("Швидкість V0 (м/с)", 200, 1500, 825)
    bc = st.number_input("Баліст. коефіцієнт", 0.1, 1.2, caliber_data['bc'], format="%.3f")
    weight = st.number_input("Вага кулі (гран)", 10.0, 800.0, float(caliber_data['weight']))
    twist = st.number_input("Твіст ствола 1:", 5.0, 20.0, 10.0)
    side = st.radio("Напрямок нарізів", ["Правобічні", "Лівобічні"], horizontal=True)

# ПАНЕЛЬ УМОВ
c1, c2, c3, c4 = st.columns(4)
dist = c1.number_input("Дистанція (м)", 0, 3000, 500, step=10)
temp = c2.number_input("Температура (°C)", -40, 50, 15)
press = c3.number_input("Тиск (гПа)", 800, 1100, 1013)
w_speed = c4.number_input("Швидкість вітру (м/с)", 0.0, 30.0, 4.0)

c5, c6, c7, c8 = st.columns(4)
w_hour = c5.select_slider("Вітер (год)", options=list(range(1, 13)), value=3)
angle = c6.number_input("Кут місця цілі (°)", -60, 60, 0)
model = c7.radio("Модель", ["G7", "G1"], horizontal=True)
sh = c8.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)

# РОЗРАХУНОК
params = {
    'dist': dist, 'temp': temp, 'press': press, 'v0': v0, 'bc': bc, 
    'weight': weight, 'twist': twist, 'twist_side': side, 
    'wind_hour': w_hour, 'w_speed': w_speed, 'angle': angle, 
    'model': model, 'sh': sh, 'zero': 100,
    # Параметри для розрахунку (не редагуються користувачем)
    'cal': caliber_data['cal'], 'len': caliber_data['len']
}
res_v, res_h, res_t, res_e, res_v_dist = calculate_ballistics(params)

# ВИВІД КАРТОК
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль (MIL)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонталь (MIL)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{res_e}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість (м/с)</div><div class="hud-value">{res_v_dist}</div></div>', unsafe_allow_html=True)
r5.markdown(f'<div class="hud-card"><div class="hud-label">Час (с)</div><div class="hud-value">{res_t}</div></div>', unsafe_allow_html=True)

# ТАБЛИЦЯ ТА ГРАФІК
st.divider()
if st.button("📊 ПОБУДУВАТИ ГРАФІК ЕНЕРГІЇ ТА ПАДІННЯ"):
    steps = np.arange(0, dist + 201, 50)
    data = []
    for d in steps:
        params['dist'] = d
        v, h, t, e, vel = calculate_ballistics(params)
        data.append({"Дистанція": d, "Вертикаль": v, "Енергія": e, "Швидкість": vel})
    
    chart_df = pd.DataFrame(data)
    st.line_chart(chart_df.set_index("Дистанція")[["Енергія", "Швидкість"]])
    st.table(chart_df)
