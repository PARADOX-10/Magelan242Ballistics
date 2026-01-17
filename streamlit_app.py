import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Ballistics Elite", layout="wide", initial_sidebar_state="collapsed")

# --- СТИЛІ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; }
        .hud-card { background: rgba(20, 25, 30, 0.9); border-left: 4px solid #00ff41; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .hud-label { color: #888; font-size: 0.7rem; text-transform: uppercase; }
        .hud-value { color: #fff; font-size: 1.8rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.75rem; }
    </style>
""", unsafe_allow_html=True)

# --- БАЛІСТИЧНИЙ ОБЧИСЛЮВАЧ ---
def run_simulation(p):
    # Константи
    g = 9.80665
    dt = 0.0015 # Крок інтегрування (с)
    
    # 1. Адаптація характеристик під вагу (Scale logic)
    ref_w = 175.0
    v_muzzle = p['v0'] * math.sqrt(ref_w / p['weight_gr']) # V0 від маси
    v_muzzle += (p['temp'] - 15) * p['t_coeff'] # Термокорекція
    bc_eff = p['bc'] * (p['weight_gr'] / ref_w) # BC від маси
    
    # Атмосфера
    tk = p['temp'] + 273.15
    c_speed = 331.3 * math.sqrt(tk / 273.15)
    rho_rel = ((p['pressure'] * 100) / (287.05 * tk)) / 1.225
    
    # Вітер (вектори)
    wind_rad = math.radians(p['w_dir'] * 30)
    w_long = p['w_speed'] * math.cos(wind_rad)  # Зустрічний (+) / Попутний (-)
    w_cross = p['w_speed'] * math.sin(wind_rad) # Боковий
    
    # Аеродинамічний стрибок (Vertical Jump)
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    aero_jump_total_mrad = (w_cross * 0.002) * t_dir # ~0.02 mrad на 10 м/с
    
    # Обнулення (Zeroing) - пошук кута вильоту
    t_approx = p['zero_dist'] / v_muzzle
    drop_zero = 0.5 * g * (t_approx**2)
    angle_zero = math.atan((drop_zero + p['sh']/100) / p['zero_dist'])
    
    # Стан
    total_angle = angle_zero + math.radians(p['angle'])
    t, dist, y, z = 0.0, 0.0, -p['sh']/100, 0.0
    vx = v_muzzle * math.cos(total_angle)
    vy = v_muzzle * math.sin(total_angle)
    
    weight_kg = p['weight_gr'] * 0.0000647989
    results = []
    step_check = 0

    # Цикл моделювання (Euler Method)
    while dist <= p['max_dist'] + 5:
        # Швидкість відносно повітря (для опору)
        v_air_x = vx + w_long
        v_air_y = vy
        v_air_total = math.sqrt(v_air_x**2 + v_air_y**2)
        mach = v_air_total / c_speed
        
        # Drag Coefficient (Cd)
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        # Уповільнення
        accel_drag = (0.5 * rho_rel * v_air_total**2 * cd * (1.0/bc_eff)) * 0.00105
        
        ax = -(accel_drag * (v_air_x / v_air_total))
        ay = -(accel_drag * (v_air_y / v_air_total)) - g
        
        # Оновлення координат
        vx += ax * dt
        vy += ay * dt
        dist += vx * dt
        y += vy * dt
        t += dt
        
        if dist >= step_check:
            # Горизонтальне знесення (Вітер + Спін-дрифт)
            wind_drift = w_cross * (t - (dist / v_muzzle))
            spin_drift = -1 * 0.05 * (10 / p['twist']) * (dist / 100)**2 * t_dir
            
            # Вертикаль (Траєкторія + Аеродинамічний стрибок)
            y_final = y + (aero_jump_total_mrad * dist / 100)
            
            # Конвертація в кліки
            is_moa = "MOA" in p['turret_unit']
            conv = 3.4377 if is_moa else 1.0
            click = 0.25 if is_moa else 0.1
            
            mrad_v = (y_final * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = ((wind_drift + spin_drift) * 100) / (dist / 10) if dist > 0 else 0
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if mrad_v > 0 else '⬇️'} {abs(mrad_v*conv/click):.1f}",
                "L/R": f"{'➡️' if mrad_h > 0 else '⬅️'} {abs(mrad_h*conv/click):.1f}",
                "V": int(v_total if 'v_total' in locals() else v_air_total),
                "Mach": round(mach, 2),
                "E": int(0.5 * weight_kg * v_air_total**2),
                "Drop": y_final * 100
            })
            step_check += 10

    return pd.DataFrame(results), v_muzzle, bc_eff

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-container"><div class="header-title">Magelan242 Elite<span class="header-sub">Numerical Solver V3.0</span></div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ НАЛАШТУВАННЯ")
    turret = st.selectbox("Кліки", ["MRAD (0.1)", "MOA (1/4)"])
    model = st.radio("Модель", ["G1", "G7"], index=1)
    twist_dir = st.radio("Нарізи", ["Right (Правий)", "Left (Лівий)"])

c1, c2, c3 = st.columns(3)
with c1:
    v0 = st.number_input("V0 (м/с)", 300, 1200, 820)
    weight = st.number_input("Вага (гран)", 40, 400, 175)
with c2:
    bc = st.number_input("BC", 0.1, 1.2, 0.505, format="%.3f")
    twist = st.number_input("Твіст (дюйм)", 6.0, 15.0, 10.0)
with c3:
    dist_max = st.number_input("Макс. Дист (м)", 100, 3000, 1000)
    zero = st.number_input("Пристрілка (м)", 50, 600, 100)

tabs = st.tabs(["🌪️ ВІТЕР/АТМОСФЕРА", "📊 ТАБЛИЦЯ ТА ГРАФІК"])

with tabs[0]:
    cc1, cc2 = st.columns(2)
    with cc1:
        w_s = st.slider("Швидкість вітру (м/с)", 0.0, 20.0, 3.0)
        w_d = st.slider("Напрямок (год)", 1, 12, 3)
    with cc2:
        temp = st.slider("Температура (°C)", -30, 50, 15)
        press = st.number_input("Тиск (hPa)", 800, 1100, 1013)
        angle = st.slider("Кут цілі (°)", -45, 45, 0)

# ОБЧИСЛЕННЯ
p = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 'pressure': press, 
     'w_speed': w_s, 'w_dir': w_d, 'angle': angle, 'twist': twist, 'zero_dist': zero, 
     'max_dist': dist_max, 'sh': 5.0, 't_coeff': 0.1, 'turret_unit': turret, 'twist_dir': twist_dir}

df, v_final, bc_final = run_simulation(p)
res = df.iloc[-1]

# ВИВІД HUD
st.markdown("---")
h1, h2, h3, h4 = st.columns(4)
h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль</div><div class="hud-value" style="color:#ffcc00">{res["UP/DN"]}</div><div class="hud-sub">Кліків</div></div>', unsafe_allow_html=True)
h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт</div><div class="hud-value" style="color:#ffcc00">{res["L/R"]}</div><div class="hud-sub">Знесення</div></div>', unsafe_allow_html=True)
h3.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість</div><div class="hud-value" style="color:#00f3ff">{res["V"]} м/с</div><div class="hud-sub">M {res["Mach"]}</div></div>', unsafe_allow_html=True)
h4.markdown(f'<div class="hud-card"><div class="hud-label">Енергія</div><div class="hud-value" style="color:#ff3333">{res["E"]} Дж</div><div class="hud-sub">Біля цілі</div></div>', unsafe_allow_html=True)

with tabs[1]:
    st.caption(f"Розрахунок для {weight}gr: V0={int(v_final)}м/с, BC={bc_final:.3f}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Дист.'], y=df['Drop'], name='Path', line=dict(color='#00ff41', width=2)))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)
    
    step = st.select_slider("Крок", [25, 50, 100], 100)
    st.dataframe(df[df['Дист.'] % step == 0], use_container_width=True, hide_index=True)
