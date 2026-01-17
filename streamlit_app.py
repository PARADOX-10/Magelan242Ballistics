import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Euler Ultra", layout="wide", initial_sidebar_state="collapsed")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .hud-card { background: rgba(20, 25, 30, 0.95); border-left: 5px solid #00ff41; border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 15px; }
        .hud-label { color: #888; font-size: 0.8rem; text-transform: uppercase; }
        .hud-value { color: #fff; font-size: 2.2rem; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО: МЕТОД ЕЙЛЕРА ---
def run_simulation(p):
    # Константи
    G = 9.80665
    OMEGA_EARTH = 7.292115e-5 # Швидкість обертання Землі
    DT = 0.001 # Крок інтегрування (1 мілісекунда)
    
    # 1. Адаптація характеристик під вагу (Ізоенергетична модель)
    ref_w = 175.0
    v_muzzle = p['v0'] * math.sqrt(ref_w / p['weight_gr']) # Швидкість залежить від маси
    v_muzzle += (p['temp'] - 15) * p['t_coeff'] # Термокорекція
    bc_eff = p['bc'] * (p['weight_gr'] / ref_w) # BC масштабується від маси
    
    # 2. Атмосфера (Враховуємо вологість для густини)
    tk = p['temp'] + 273.15
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0)
    pd_press = p['pressure'] - pv
    rho = (pd_press * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    rho_rel = rho / 1.225
    c_speed = 331.3 * math.sqrt(tk / 273.15)
    
    # 3. Вектори середовища
    lat_rad = math.radians(p['latitude'])
    az_rad = math.radians(p['azimuth'])
    wind_rad = math.radians(p['w_dir'] * 30)
    w_cross = p['w_speed'] * math.sin(wind_rad)
    w_long = p['w_speed'] * math.cos(wind_rad)
    
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1

    # 4. Обнулення (Пошук кута вильоту)
    t_approx = p['zero_dist'] / v_muzzle
    angle_zero = math.atan((0.5 * G * t_approx**2 + p['sh']/100) / p['zero_dist'])
    
    # Початковий стан
    t, dist, y, z = 0.0, 0.0, -p['sh']/100, 0.0
    vx = v_muzzle * math.cos(angle_zero + math.radians(p['angle']))
    vy = v_muzzle * math.sin(angle_zero + math.radians(p['angle']))
    vz = 0.0
    
    weight_kg = p['weight_gr'] * 0.0000647989
    results = []
    step_check = 0

    # --- ЦИКЛ МЕТОДУ ЕЙЛЕРА ---
    while dist <= p['max_dist'] + 5:
        # Швидкість відносно повітря (Airspeed)
        v_air_x = vx + w_long
        v_total = math.sqrt(v_air_x**2 + vy**2 + vz**2)
        mach = v_total / c_speed
        
        # Вибір коефіцієнта опору Cd (Спрощена G-модель)
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        # Прискорення опору
        accel_drag = (0.5 * rho_rel * v_total**2 * cd * (1.0/bc_eff)) * 0.00105
        
        # Ефект Коріоліса
        cori_y = 2 * OMEGA_EARTH * vx * math.cos(lat_rad) * math.sin(az_rad)
        cori_z = 2 * OMEGA_EARTH * (vy * math.cos(lat_rad) * math.cos(az_rad) - vx * math.sin(lat_rad))

        # Оновлення швидкостей (Прискорення -> Швидкість)
        vx += -(accel_drag * (v_air_x / v_total)) * DT
        vy += (-(accel_drag * (vy / v_total)) - G + cori_y) * DT
        vz += (-(accel_drag * (vz / v_total)) + cori_z) * DT
        
        # Оновлення координат (Швидкість -> Позиція)
        dist += vx * DT
        y += vy * DT
        z += vz * DT
        t += DT
        
        if dist >= step_check:
            # Додаткові ефекти: Спін-дрифт та Аеродинамічний стрибок
            wind_drift = w_cross * (t - (dist / v_muzzle))
            spin_drift = -1 * (0.05 * (dist/100)**2 * t_dir)
            aero_jump = (w_cross * 0.002 * t_dir * dist / 100)
            
            y_final = y + aero_jump
            z_final = z + wind_drift + spin_drift
            
            # Конвертація в кутові одиниці
            is_moa = "MOA" in p['turret_unit']
            conv = 3.4377 if is_moa else 1.0
            click = 0.25 if is_moa else 0.1
            
            mrad_v = (y_final * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = (z_final * 100) / (dist / 10) if dist > 0 else 0
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if mrad_v > 0 else '⬇️'} {abs(mrad_v*conv/click):.1f}",
                "L/R": f"{'➡️' if mrad_h > 0 else '⬅️'} {abs(mrad_h*conv/click):.1f}",
                "V": int(v_total), "Mach": round(mach, 2), "E": int(0.5 * weight_kg * v_total**2),
                "Drop": y_final * 100
            })
            step_check += 10

    return pd.DataFrame(results), v_muzzle, bc_eff

# --- ІНТЕРФЕЙС ---
st.header("🎯 Magelan242 Numerical Solver (Euler)")

c1, c2, c3 = st.columns(3)
with c1:
    v0 = st.number_input("V0 (м/с)", 300, 1200, 820)
    bc = st.number_input("BC (G1/G7)", 0.1, 1.2, 0.505, format="%.3f")
    weight = st.number_input("Вага (гран)", 40, 400, 175)
with c2:
    w_s = st.slider("Вітер (м/с)", 0.0, 20.0, 3.0)
    w_d = st.slider("Напрям (год)", 1, 12, 3)
    dist_max = st.number_input("Дистанція (м)", 100, 3000, 1000)
with c3:
    temp = st.slider("Темп. (°C)", -30, 50, 15)
    humid = st.slider("Вологість (%)", 0, 100, 50)
    turret = st.selectbox("Одиниці", ["MRAD", "MOA"])

# ЗАПУСК
p = {'v0': v0, 'bc': bc, 'model': "G7", 'weight_gr': weight, 'temp': temp, 'pressure': 1013, 
     'humid': humid, 'latitude': 50, 'azimuth': 90, 'w_speed': w_s, 'w_dir': w_d, 
     'angle': 0, 'twist': 10, 'zero_dist': 100, 'max_dist': dist_max, 'sh': 5.0, 
     't_coeff': 0.1, 'turret_unit': turret, 'twist_dir': "Right (Правий)"}

df, v_calc, bc_calc = run_simulation(p)
res = df.iloc[-1]

# HUD
st.markdown("---")
h1, h2, h3 = st.columns(3)
h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль</div><div class="hud-value">{res["UP/DN"]}</div></div>', unsafe_allow_html=True)
h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт</div><div class="hud-value">{res["L/R"]}</div></div>', unsafe_allow_html=True)
h3.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість</div><div class="hud-value">{res["V"]} м/с</div></div>', unsafe_allow_html=True)

# ГРАФІК
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['Дист.'], y=df['Drop'], line=dict(color='#00ff41', width=3)))
fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(fig, use_container_width=True)
