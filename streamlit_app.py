import streamlit as st
import pandas as pd
import numpy as np
import math

# --- БАЗА МОДИФІКАЦІЙ (Калібр та довжина зашиті всередині) ---
AMMO_DB = {
    ".300 WM Berger Hybrid 215gr": {"cal": 0.308, "len": 1.60, "weight": 215.0, "bc": 0.354, "model": "G7", "v0": 850},
    ".300 WM Hornady ELD-M 208gr": {"cal": 0.308, "len": 1.54, "weight": 208.0, "bc": 0.320, "model": "G7", "v0": 855},
    ".300 WM Sierra MK 190gr": {"cal": 0.308, "len": 1.35, "weight": 190.0, "bc": 0.265, "model": "G7", "v0": 880},
    "7.62x51 M118LR (175gr)": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "5.45x39 7N6 (53gr)": {"cal": 0.214, "len": 0.98, "weight": 53.0, "bc": 0.168, "model": "G7", "v0": 880},
    "5.56x45 MK262 (77gr)": {"cal": 0.224, "len": 0.99, "weight": 77.0, "bc": 0.190, "model": "G7", "v0": 840}
}

st.set_page_config(page_title="Magelan242 Ballistics HUD", layout="wide")

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

# --- БАЛІСТИЧНЕ ЯДРО ---
def calculate_lead(p, d, angle_deg, target_speed_kmh):
    angle_rad = math.radians(angle_deg)
    cos_val = math.cos(angle_rad)
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (tof**2) * cos_val
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    v_mil = abs((y_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    
    w_rad = math.radians(p['wind_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (tof - (d/v0_eff)))
    h_mil_wind = (wind_drift * 100) / (d / 10) / 0.1 if d > 0 else 0
    
    v_target_ms = target_speed_kmh / 3.6
    lead_mil = (v_target_ms * tof * 100) / (d / 10) / 0.1 if d > 0 else 0
    
    return {"v_mil": round(v_mil, 1), "h_mil_wind": round(abs(h_mil_wind), 1), "lead_mil": round(lead_mil, 1), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | ОПЕРАТИВНИЙ ХАБ</h1></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📦 Вибір боєприпасу")
    bullet_key = st.selectbox("Набій:", list(AMMO_DB.keys()))
    b = AMMO_DB[bullet_key]
    
    # Виводимо інформацію про обраний набій без можливості редагувати калібр
    st.write(f"**Вага:** {b['weight']} гран")
    st.write(f"**БК:** {b['bc']} ({b['model']})")
    
    st.divider()
    v0 = st.number_input("Початкова швидкість (м/с)", 100, 1200, b['v0'])
    sh = st.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)

# ОСНОВНА ПАНЕЛЬ
col_env, col_target, col_hud = st.columns([1.2, 1.2, 1.5])

with col_env:
    st.subheader("🌍 Середовище")
    dist = st.slider("Дистанція (м)", 0, 1500, 500, step=10)
    temp = st.number_input("Температура (°C)", -30, 50, 15)
    press = st.number_input("Тиск (гПа)", 800, 1100, 1013)
    angle = st.slider("Кут цілі (°)", -45, 45, 0)

with col_target:
    st.subheader("🏃 Ціль та Вітер")
    t_speed = st.slider("Швидкість цілі (км/год)", 0.0, 20.0, 0.0, step=0.5)
    st.divider()
    w_speed = st.slider("Вітер (м/с)", 0.0, 15.0, 3.0)
    w_hour = st.select_slider("Година вітру", options=list(range(1, 13)), value=3)

# РЕЗУЛЬТАТ
params = {**b, 'v0': v0, 'sh': sh, 'temp': temp, 'press': press, 'w_speed': w_speed, 'wind_hour': w_hour, 'zero': 100}
res = calculate_lead(params, dist, angle, t_speed)

with col_hud:
    st.subheader("🎯 Рішення (MIL)")
    
    st.markdown(f'<div class="hud-card"><div class="hud-label">Вертикальна поправка</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="hud-card"><div class="hud-label">Поправка на вітер</div><div class="hud-value">↔ {res["h_mil_wind"]}</div></div>', unsafe_allow_html=True)
    
    if t_speed > 0:
        st.markdown(f'<div class="hud-card"><div class="hud-label">Упредження (рух)</div><div class="hud-value lead-value">⟹ {res["lead_mil"]}</div></div>', unsafe_allow_html=True)
    
    st.info(f"Час польоту: {res['tof']} с")

# ТАБЛИЦЯ ПОПРАВОК
st.divider()
quick_steps = [dist-100, dist-50, dist, dist+50, dist+100]
table_data = []
for d in quick_steps:
    if d >= 0:
        r = calculate_lead(params, d, angle, t_speed)
        table_data.append({"Метри": d, "Вертикаль": r['v_mil'], "Вітер": r['h_mil_wind'], "Упредження": r['lead_mil']})
st.table(pd.DataFrame(table_data))
