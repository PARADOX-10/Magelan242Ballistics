import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Pro Mobile UA", layout="wide", initial_sidebar_state="collapsed")

# --- ФУНКЦІЯ ДЛЯ ЗАВАНТАЖЕННЯ ЛОГОТИПУ ---
def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return None

# --- CSS СТИЛІ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { display: flex; align-items: center; gap: 20px; padding-bottom: 20px; border-bottom: 2px solid #00ff41; margin-bottom: 20px; }
        .responsive-logo { width: 80px; height: auto; }
        .header-title { font-size: 1.8rem; font-weight: 700; text-transform: uppercase; line-height: 1.2; }
        .header-sub { font-size: 0.5em; color: #00ff41; display: block; }
        
        /* Таби та Кнопки */
        .stTabs [data-baseweb="tab"] { height: 50px; background-color: #161b22; border-radius: 8px; color: #8b949e; flex-grow: 1; }
        .stTabs [aria-selected="true"] { border: 1px solid #00ff41 !important; color: #00ff41 !important; }
        
        /* HUD КАРТКИ */
        .hud-card { background: rgba(20, 25, 30, 0.8); border-left: 4px solid #00ff41; border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; }
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; }
        .hud-value { color: #fff; font-size: 2rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- НОВЕ ФІЗИЧНЕ ЯДРО (ЧИСЕЛЬНЕ ІНТЕГРУВАННЯ) ---
def run_simulation(p):
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    c_speed = 331.3 * math.sqrt(tk / 273.15) # Локальна швидкість звуку
    
    rho_rel = rho / 1.225
    i_factor = 1.0 / p['bc']
    
    # Розрахунок кута для "обнулення"
    # Наближення: кут підйому ствола, щоб влучити в нуль на zero_dist
    t_approx = p['zero_dist'] / v0_corr
    drop_at_zero = 0.5 * g * (t_approx**2)
    angle_launch = math.atan((drop_at_zero + p['sh']/100) / p['zero_dist'])
    
    # Початкові параметри вектора
    total_angle = angle_launch + math.radians(p['angle'])
    dt = 0.002 # крок 2мс для балансу точності/швидкості
    t, dist, y = 0.0, 0.0, -p['sh'] / 100
    vx = v0_corr * math.cos(total_angle)
    vy = v0_corr * math.sin(total_angle)
    
    wind_rad = math.radians(p['w_dir'] * 30)
    w_cross = p['w_speed'] * math.sin(wind_rad)
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    
    results = []
    step_to_save = 0
    
    while dist <= p['max_dist'] + 5:
        v_total = math.sqrt(vx**2 + vy**2)
        mach = v_total / c_speed
        
        # Функція опору (Cd) залежно від моделі
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        # Сила опору (прискорення сповільнення)
        accel_drag = (0.5 * rho_rel * v_total**2 * cd * i_factor) * 0.00105 
        
        ax = -(accel_drag * (vx / v_total))
        ay = -(accel_drag * (vy / v_total)) - g
        
        # Оновлення стану
        vx += ax * dt
        vy += ay * dt
        dist += vx * dt
        y += vy * dt
        t += dt
        
        if dist >= step_to_save:
            wind_drift = w_cross * (t - (dist / v0_corr))
            derivation = -1 * 0.05 * (10 / p['twist']) * (dist / 100)**2 * t_dir
            
            # Перевід у кутові одиниці
            mrad_v = (y * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = ((wind_drift + derivation) * 100) / (dist / 10) if dist > 0 else 0
            
            is_moa = "MOA" in p['turret_unit']
            click_val = 0.25 if is_moa else 0.1
            val_v = mrad_v * (3.4377 if is_moa else 1)
            val_h = mrad_h * (3.4377 if is_moa else 1)
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if val_v > 0 else '⬇️'} {abs(val_v/click_val):.1f}",
                "L/R": f"{'➡️' if val_h > 0 else '⬅️'} {abs(val_h/click_val):.1f}",
                "V, м/с": int(v_total),
                "Mach": round(mach, 2),
                "E, Дж": int((weight_kg * v_total**2) / 2),
                "Падіння": y * 100
            })
            step_to_save += 5
            
    return pd.DataFrame(results), v0_corr, c_speed

# --- ІНТЕРФЕЙС ---
logo_b64 = get_img_as_base64("logo.png")
logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="responsive-logo">' if logo_b64 else '🎯'

st.markdown(f"""
    <div class="header-container">
        <div style="font-size: 2.5rem;">{logo_html}</div>
        <div class="header-title">Magelan242 Ballistics<span class="header-sub">Numerical Solver v2.0</span></div>
    </div>
""", unsafe_allow_html=True)

with st.container():
    c1, c2 = st.columns([2, 1])
    with c1: dist_input = st.number_input("ДИСТАНЦІЯ (м)", 100, 3000, 1000, step=50)
    with c2: turret_unit = st.selectbox("КЛІКИ", ["MRAD (0.1)", "MOA (1/4)"])

tab_env, tab_gun, tab_vis = st.tabs(["🌪️ УМОВИ", "🔫 ЗБРОЯ", "📈 АНАЛІЗ"])

with tab_env:
    ec1, ec2 = st.columns(2)
    with ec1:
        w_speed = st.number_input("Вітер (м/с)", 0.0, 20.0, 2.0, step=0.5)
        w_dir = st.number_input("Напрям (год)", 1, 12, 3, step=1)
    with ec2:
        temp = st.number_input("Темп. (°C)", -30, 50, 15)
        press = st.number_input("Тиск (hPa)", 800, 1100, 1013)
        angle = st.number_input("Кут (°)", -45, 45, 0)

with tab_gun:
    gc1, gc2 = st.columns(2)
    with gc1:
        v0 = st.number_input("V0 (м/с)", 300, 1200, 820)
        bc = st.number_input("BC", 0.1, 1.0, 0.505, format="%.3f")
        model = st.radio("Модель", ["G1", "G7"], horizontal=True)
    with gc2:
        zero_dist = st.number_input("Нуль (м)", 50, 600, 100)
        sh = st.number_input("Вис. прицілу (см)", 3.0, 12.0, 5.0)
        twist = st.number_input("Твіст", 7.0, 14.0, 10.0)
        twist_dir = st.radio("Нарізи", ["Right (Правий)", "Left (Лівий)"], horizontal=True)
        t_coeff = st.number_input("Термозалежність %", 0.0, 2.0, 0.1)
        weight = st.number_input("Вага (гран)", 50, 300, 175)

# РОЗРАХУНОК
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': dist_input, 'sh': sh, 
          't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

df, v0_final, local_sound_speed = run_simulation(params)
res = df.iloc[-1]

# HUD РЕЗУЛЬТАТИ
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4 = st.columns(4)
r1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТ</div><div class="hud-value" style="color:#ffcc00">{res["UP/DN"]}</div><div class="hud-sub">Кліків</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">ГОР</div><div class="hud-value" style="color:#ffcc00">{res["L/R"]}</div><div class="hud-sub">Кліків</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">ШВИДКІСТЬ</div><div class="hud-value" style="color:#00f3ff">{res["V, м/с"]}</div><div class="hud-sub">м/с (M {res["Mach"]})</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">ЕНЕРГІЯ</div><div class="hud-value" style="color:#ff3333">{res["E, Дж"]}</div><div class="hud-sub">Джоулів</div></div>', unsafe_allow_html=True)

# ГРАФІК
with tab_vis:
    fig = go.Figure()
    # Траєкторія
    fig.add_trace(go.Scatter(x=df['Дист.'], y=df['Падіння'], name='Траєкторія', line=dict(color='#00ff41', width=3)))
    
    # Лінія звукового бар'єру (Mach 1.2 — межа стабільності)
    transonic_dist = df[df['Mach'] <= 1.2]['Дист.'].min()
    if not np.isnan(transonic_dist):
        fig.add_vline(x=transonic_dist, line_dash="dash", line_color="red", annotation_text="TRANS-SONIC ZONE")

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0, r=0, t=20, b=0),
                      xaxis_title="Дистанція (м)", yaxis_title="Відхилення (см)")
    st.plotly_chart(fig, use_container_width=True)
    
    # ТАБЛИЦЯ
    step = st.select_slider("Крок таблиці", [25, 50, 100], 100)
    st.dataframe(df[df['Дист.'] % step == 0], use_container_width=True, hide_index=True)
