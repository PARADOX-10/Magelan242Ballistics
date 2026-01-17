import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Ultra V4.0", layout="wide", initial_sidebar_state="collapsed")

def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except: return None

# --- CSS СТИЛІ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #040404; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 20px;}
        .hud-card { background: rgba(15, 20, 25, 0.95); border: 1px solid #333; border-left: 5px solid #00ff41; border-radius: 10px; padding: 15px; text-align: center; }
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;}
        .hud-value { color: #fff; font-size: 2rem; font-weight: 700; text-shadow: 0 0 10px rgba(0,255,65,0.2); }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
        .stTabs [data-baseweb="tab"] { font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО V4.0 ---
def run_simulation(p):
    # Константи
    G = 9.80665
    OMEGA_EARTH = 7.292115e-5 # Кутова швидкість Землі
    DT = 0.0012 # Підвищена точність (1.2 мс)
    
    # Адаптація характеристик під вагу
    ref_weight = 175.0 
    v_muzzle = p['v0'] * math.sqrt(ref_weight / p['weight_gr'])
    v_muzzle += (p['temp'] - 15) * p['t_coeff'] 
    bc_eff = p['bc'] * (p['weight_gr'] / ref_weight) 
    
    # Розрахунок щільності вологого повітря
    tk = p['temp'] + 273.15
    # Тиск насиченої пари (SVP)
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0) # Парціальний тиск пари
    pd = p['pressure'] - pv # Тиск сухого повітря
    rho = (pd * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    rho_rel = rho / 1.225
    c_speed = 331.3 * math.sqrt(tk / 273.15) 

    # Вектори середовища
    lat_rad = math.radians(p['latitude'])
    az_rad = math.radians(p['azimuth'])
    wind_rad = math.radians(p['w_dir'] * 30)
    w_cross = p['w_speed'] * math.sin(wind_rad)
    w_long = p['w_speed'] * math.cos(wind_rad)

    # Гіроскопічна стабільність (Miller Stability Factor)
    # Спрощена оцінка для Aero Jump та Spin Drift
    s_g = (30 * p['weight_gr']) / ((p['twist']**2) * (p['caliber']**3) * (v_muzzle/600))
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1

    # Обнулення
    t_approx = p['zero_dist'] / v_muzzle
    angle_zero = math.atan((0.5 * G * t_approx**2 + p['sh']/100) / p['zero_dist'])
    
    total_angle = angle_zero + math.radians(p['angle'])
    t, dist, y, z = 0.0, 0.0, -p['sh']/100, 0.0
    vx = v_muzzle * math.cos(total_angle)
    vy = v_muzzle * math.sin(total_angle)
    vz = 0.0 # Z - бокове відхилення
    
    weight_kg = p['weight_gr'] * 0.0000647989
    results = []
    step_check = 0

    while dist <= p['max_dist'] + 5:
        v_air_x = vx + w_long
        v_total = math.sqrt(v_air_x**2 + vy**2 + vz**2)
        mach = v_total / c_speed
        
        # Cd Model
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        accel_drag = (0.5 * rho_rel * v_total**2 * cd * (1.0/bc_eff)) * 0.00105
        
        # --- ЕФЕКТ КОРІОЛІСА ---
        coriolis_x = 0 # Вплив на дальність мізерний
        # Вертикальний Коріоліс (Eötvös)
        coriolis_y = 2 * OMEGA_EARTH * vx * math.cos(lat_rad) * math.sin(az_rad)
        # Горизонтальний Коріоліс
        coriolis_z = 2 * OMEGA_EARTH * (vy * math.cos(lat_rad) * math.cos(az_rad) - vx * math.sin(lat_rad))

        # Сумарні прискорення
        ax = -(accel_drag * (v_air_x / v_total))
        ay = -(accel_drag * (vy / v_total)) - G + coriolis_y
        az = -(accel_drag * (vz / v_total)) + coriolis_z
        
        # Інтегрування
        vx += ax * DT
        vy += ay * DT
        vz += az * DT
        dist += vx * DT
        y += vy * DT
        z += vz * DT
        t += DT
        
        if dist >= step_check:
            # Вітер + Спін-дрифт (залежить від стабільності Sg)
            wind_drift = w_cross * (t - (dist / v_muzzle))
            spin_drift = -1 * (0.06 * (dist/100)**2 * t_dir) / s_g
            
            # Aero Jump (вертикальний стрибок від вітру)
            aero_jump = (w_cross * 0.002 * t_dir * dist / 100)
            
            y_final = y + aero_jump
            z_final = z + wind_drift + spin_drift
            
            is_moa = "MOA" in p['turret_unit']
            conv = 3.4377 if is_moa else 1.0
            click = 0.25 if is_moa else 0.1
            
            mrad_v = (y_final * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = (z_final * 100) / (dist / 10) if dist > 0 else 0
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if mrad_v > 0 else '⬇️'} {abs(mrad_v*conv/click):.1f}",
                "L/R": f"{'➡️' if mrad_h > 0 else '⬅️'} {abs(mrad_h*conv/click):.1f}",
                "V, м/с": int(v_total),
                "Mach": round(mach, 2),
                "E, Дж": int(0.5 * weight_kg * v_total**2),
                "Drop": y_final * 100,
                "Sg": round(s_g, 2)
            })
            step_check += 10

    return pd.DataFrame(results), v_muzzle, bc_eff

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-container"><div class="header-title">Magelan242 ULTRA<span class="header-sub">Scientific Numerical Solver V4.0</span></div></div>', unsafe_allow_html=True)

tab_calc, tab_env, tab_gun = st.tabs(["🚀 ОБЧИСЛЕННЯ", "🌍 СЕРЕДОВИЩЕ", "🔫 КОМПЛЕКС"])

with tab_env:
    e1, e2 = st.columns(2)
    with e1:
        temp = st.slider("Температура (°C)", -30, 50, 15)
        humid = st.slider("Вологість (%)", 0, 100, 50)
        press = st.number_input("Тиск (hPa)", 800, 1100, 1013)
    with e2:
        lat = st.number_input("Широта (0-90°)", 0, 90, 50, help="Україна ~50°")
        azimuth = st.slider("Азимут вогню (°)", 0, 360, 90, help="0-Пн, 90-Сх")
        w_s = st.number_input("Вітер (м/с)", 0.0, 20.0, 3.0)
        w_d = st.slider("Напрям вітру (год)", 1, 12, 3)

with tab_gun:
    g1, g2 = st.columns(2)
    with g1:
        v0 = st.number_input("V0 еталон (м/с)", 300, 1300, 820)
        bc = st.number_input("BC еталон", 0.1, 1.2, 0.505, format="%.3f")
        model = st.radio("Модель", ["G1", "G7"], index=1, horizontal=True)
        weight = st.number_input("Вага кулі (гран)", 40, 400, 175)
    with g2:
        caliber = st.number_input("Калібр (дюйм)", 0.22, 0.50, 0.308, step=0.001)
        twist = st.number_input("Твіст (дюйм)", 6.0, 15.0, 10.0)
        zero = st.number_input("Пристрілка (м)", 50, 600, 100)
        sh = st.number_input("Вис. прицілу (см)", 3.0, 12.0, 5.0)

with tab_calc:
    c1, c2 = st.columns([2, 1])
    with c1: dist_max = st.number_input("ДИСТАНЦІЯ (м)", 100, 3000, 1000)
    with c2: turret = st.selectbox("СІТКА", ["MRAD", "MOA"])

    # ЗАПУСК
    p = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 'pressure': press, 
         'humid': humid, 'latitude': lat, 'azimuth': azimuth, 'w_speed': w_s, 'w_dir': w_d, 
         'angle': 0, 'twist': twist, 'caliber': caliber, 'zero_dist': zero, 'max_dist': dist_max, 
         'sh': sh, 't_coeff': 0.1, 'turret_unit': turret, 'twist_dir': "Right (Правий)"}

    df, v_final, bc_final = run_simulation(p)
    res = df.iloc[-1]

    st.markdown("---")
    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль</div><div class="hud-value">{res["UP/DN"]}</div><div class="hud-sub">Кліків</div></div>', unsafe_allow_html=True)
    h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт</div><div class="hud-value">{res["L/R"]}</div><div class="hud-sub">Коріоліс+Вітер</div></div>', unsafe_allow_html=True)
    h3.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість</div><div class="hud-value">{res["V, м/с"]} м/с</div><div class="hud-sub">Mach {res["Mach"]}</div></div>', unsafe_allow_html=True)
    h4.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність</div><div class="hud-value">{res["Sg"]}</div><div class="hud-sub"> Miller Sg</div></div>', unsafe_allow_html=True)

    # Графік
    st.markdown("### 📉 Аналіз траєкторії")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Дист.'], y=df['Drop'], mode='lines', name='Trajectory', line=dict(color='#00ff41', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=10,b=0), xaxis_title="Метри", yaxis_title="Падіння (см)")
    st.plotly_chart(fig, use_container_width=True)
    
    step = st.select_slider("Крок таблиці", [50, 100], 100)
    st.dataframe(df[df['Дист.'] % step == 0], use_container_width=True, hide_index=True)
