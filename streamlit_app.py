import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan242 ELR Precision", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #1a1a1a 0%, #C62828 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; border-right: 5px solid white; text-align: right; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 24px; font-weight: 900; }
    .section-head { color: #C62828; font-size: 16px; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #444; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- ПОВНА ФІЗИЧНА МОДЕЛЬ ---
def calculate_precision_ballistics(p):
    d = p['dist']
    lat_rad = math.radians(p['lat'])
    azimuth_rad = math.radians(p['azimuth'])
    
    # 1. Атмосфера та щільність
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    # 2. Час польоту та швидкість
    tof = (math.exp(k * d) - 1) / (k * p['v0']) if d > 0 else 0
    v_dist = p['v0'] * math.exp(-k * d)
    
    # 3. Вертикальне падіння (Gravity + Angle)
    cos_angle = math.cos(math.radians(p['angle']))
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = 0.5 * 9.806 * (tof**2) * cos_angle
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)

    # 4. Вітер та Аеродинамічний стрибок
    w_rad = math.radians(p['w_hour'] * 30)
    wind_x = p['w_speed'] * math.sin(w_rad) # Боковий вітер
    wind_drift = wind_x * (tof - (d/p['v0']))
    # Аеродинамічний стрибок (вертикальне зміщення від бокового вітру)
    aj_drift = 0.001 * wind_x * (d / 100) 

    # 5. Деривація (Spin Drift)
    # Спрощена формула для стабілізованої кулі
    derivation = 0.06 * (p['twist'] / 10) * (d / 100)**1.5
    
    # 6. Ефект Коріоліса (Земля)
    omega = 7.292115e-5 # Кутова швидкість Землі
    coriolis_hor = -2 * omega * tof * wind_x * math.sin(lat_rad) # Спрощено
    coriolis_vert = 2 * omega * d * p['v0'] * math.cos(lat_rad) * math.sin(azimuth_rad) / 9.806 * 0.01

    # 7. Підсумок MIL
    total_v_m = y_m + aj_drift + coriolis_vert
    total_h_m = wind_drift + derivation + coriolis_hor
    
    v_mil = abs((total_v_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    h_mil = abs((total_h_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    
    # Гіроскопічна стабільність (Miller)
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['bullet_len'] * (1 + p['bullet_len']**2) ) * (p['v0'] / 853.44)**(1/3)

    return {"v_mil": round(v_mil, 1), "h_mil": round(h_mil, 1), "v_at_dist": int(v_dist), "energy": int((p['weight'] * 0.0000648 * v_dist**2) / 2), "tof": round(tof, 3), "sg": round(sg, 2)}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | ELR PRECISION SYSTEM</h1></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 1.5])

with c1:
    st.markdown('<div class="section-head">📦 Специфікації набою</div>', unsafe_allow_html=True)
    p_v0 = st.number_input("Швидкість V0 (м/с)", value=860)
    p_bc = st.number_input("БК (G7)", value=0.354, format="%.3f")
    p_weight = st.number_input("Вага кулі (гран)", value=215.0)
    p_cal = st.number_input("Калібр (дюйм)", value=0.308, format="%.3f")
    p_len = st.number_input("Довжина кулі (дюйм)", value=1.60, format="%.3f")
    
    st.markdown('<div class="section-head">🔫 Параметри зброї</div>', unsafe_allow_html=True)
    p_twist = st.number_input("Твіст ствола 1:", value=10.0)
    p_sh = st.number_input("Висота прицілу (см)", value=5.0)
    p_zero = st.number_input("Дистанція пристрілки (м)", value=100)

with c2:
    st.markdown('<div class="section-head">🌍 Зовнішні фактори</div>', unsafe_allow_html=True)
    p_temp = st.slider("Температура (°C)", -30, 50, 15)
    p_press = st.slider("Тиск (гПа)", 800, 1100, 1013)
    p_w_speed = st.slider("Вітер (м/с)", 0.0, 15.0, 4.0)
    p_w_hour = st.slider("Вітер (год)", 1, 12, 3)
    p_angle = st.slider("Кут цілі (°)", -45, 45, 0)
    
    st.markdown('<div class="section-head">🗺 Ефект Коріоліса</div>', unsafe_allow_html=True)
    p_lat = st.number_input("Широта (0-90°)", value=50)
    p_azimuth = st.number_input("Азимут стрільби (0-360°)", value=0)

with c3:
    st.markdown('<div class="section-head">🎯 Розрахунок поправки</div>', unsafe_allow_html=True)
    p_dist = st.slider("Дистанція до цілі (м)", 0, 2000, 1000, step=10)
    
    data = {
        'v0': p_v0, 'bc': p_bc, 'weight': p_weight, 'cal': p_cal, 'bullet_len': p_len,
        'twist': p_twist, 'sh': p_sh, 'zero': p_zero, 'temp': p_temp, 'press': p_press,
        'w_speed': p_w_speed, 'w_hour': p_w_hour, 'angle': p_angle, 'dist': p_dist,
        'lat': p_lat, 'azimuth': p_azimuth, 'model': 'G7'
    }
    
    res = calculate_precision_ballistics(data)
    
    # HUD
    h1, h2 = st.columns(2)
    h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт MIL</div><div class="hud-value">↔ {res["h_mil"]}</div></div>', unsafe_allow_html=True)
    
    h3, h4, h5 = st.columns(3)
    h3.markdown(f'<div class="hud-card"><div class="hud-label">ToF</div><div class="hud-value" style="font-size:18px;">{res["tof"]} с</div></div>', unsafe_allow_html=True)
    h4.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність</div><div class="hud-value" style="font-size:18px; color:{"#00FF00" if 1.4 <= res["sg"] <= 2.0 else "#FFD700"}">{res["sg"]}</div></div>', unsafe_allow_html=True)
    h5.markdown(f'<div class="hud-card"><div class="hud-label">Енергія</div><div class="hud-value" style="font-size:18px;">{res["energy"]} Дж</div></div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Аналіз дистанції")
    steps = [p_dist-200, p_dist-100, p_dist, p_dist+100, p_dist+200]
    table = []
    for s in steps:
        if s >= 0:
            data['dist'] = s
            r = calculate_precision_ballistics(data)
            table.append({"Дист": s, "Вертикаль": r['v_mil'], "Горизонт": r['h_mil'], "Швидкість": r['v_at_dist']})
    st.table(pd.DataFrame(table))
