import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Pro Elite", layout="wide", initial_sidebar_state="collapsed")

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
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 20px; margin-bottom: 20px; display: flex; align-items: center; gap: 20px;}
        .hud-card { background: rgba(20, 25, 30, 0.9); border-left: 4px solid #00ff41; border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; }
        .hud-label { color: #888; font-size: 0.8rem; text-transform: uppercase; }
        .hud-value { color: #fff; font-size: 2.2rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

# --- ФІЗИЧНЕ ЯДРО (NUMERICAL SOLVER V3.0) ---
def run_simulation(p):
    g = 9.80665
    dt = 0.0015 
    
    # Адаптація характеристик під вагу
    ref_weight = 175.0 
    v_muzzle = p['v0'] * math.sqrt(ref_weight / p['weight_gr'])
    v_muzzle += (p['temp'] - 15) * p['t_coeff'] 
    bc_eff = p['bc'] * (p['weight_gr'] / ref_weight) 
    
    tk = p['temp'] + 273.15
    rho_rel = ((p['pressure'] * 100) / (287.05 * tk)) / 1.225
    c_speed = 331.3 * math.sqrt(tk / 273.15) 
    
    wind_rad = math.radians(p['w_dir'] * 30)
    w_cross = p['w_speed'] * math.sin(wind_rad)
    w_long = p['w_speed'] * math.cos(wind_rad) 
    
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    aero_jump_mrad = (w_cross * 0.002) * t_dir
    
    t_approx = p['zero_dist'] / v_muzzle
    drop_zero = 0.5 * g * (t_approx**2)
    angle_zero = math.atan((drop_zero + p['sh']/100) / p['zero_dist'])
    
    total_angle = angle_zero + math.radians(p['angle'])
    t, dist, y = 0.0, 0.0, -p['sh']/100
    vx = v_muzzle * math.cos(total_angle)
    vy = v_muzzle * math.sin(total_angle)
    
    weight_kg = p['weight_gr'] * 0.0000647989
    results = []
    step_check = 0

    while dist <= p['max_dist'] + 5:
        v_air_x = vx + w_long
        v_air_total = math.sqrt(v_air_x**2 + vy**2)
        mach = v_air_total / c_speed
        
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        accel_drag = (0.5 * rho_rel * v_air_total**2 * cd * (1.0/bc_eff)) * 0.00105
        ax = -(accel_drag * (v_air_x / v_air_total))
        ay = -(accel_drag * (vy / v_air_total)) - g
        
        vx += ax * dt
        vy += ay * dt
        dist += vx * dt
        y += vy * dt
        t += dt
        
        if dist >= step_check:
            wind_drift = w_cross * (t - (dist / v_muzzle))
            spin_drift = -1 * 0.05 * (10 / p['twist']) * (dist / 100)**2 * t_dir
            y_final = y + (aero_jump_mrad * dist / 100)
            
            is_moa = "MOA" in p['turret_unit']
            mrad_v = (y_final * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = ((wind_drift + spin_drift) * 100) / (dist / 10) if dist > 0 else 0
            
            conv = 3.4377 if is_moa else 1.0
            click = 0.25 if is_moa else 0.1
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if mrad_v > 0 else '⬇️'} {abs(mrad_v*conv/click):.1f}",
                "L/R": f"{'➡️' if mrad_h > 0 else '⬅️'} {abs(mrad_h*conv/click):.1f}",
                "V, м/с": int(v_air_total),
                "Mach": round(mach, 2),
                "E, Дж": int(0.5 * weight_kg * v_air_total**2),
                "Падіння": y_final * 100
            })
            step_check += 10

    return pd.DataFrame(results), v_muzzle, bc_eff

# --- ІНТЕРФЕЙС ---
logo_html = f'<img src="data:image/png;base64,{get_img_as_base64("logo.png")}" style="width:80px;">' if os.path.exists("logo.png") else '🎯'

st.markdown(f"""<div class="header-container">{logo_html}<div class="header-title">Magelan242 Elite<span class="header-sub">Restored Visuals V3.1</span></div></div>""", unsafe_allow_html=True)

with st.container():
    c1, c2 = st.columns([2, 1])
    with c1: dist_input = st.number_input("ДИСТАНЦІЯ (м)", 100, 3000, 1000, step=50)
    with c2: turret_unit = st.selectbox("ОДИНИЦІ", ["MRAD", "MOA"])

tab_env, tab_gun, tab_vis = st.tabs(["🌪️ УМОВИ", "🔫 ЗБРОЯ", "📈 АНАЛІЗ"])

# ... (Введення параметрів аналогічне попереднім версіям) ...
with tab_env:
    ec1, ec2 = st.columns(2)
    with ec1:
        w_speed = st.number_input("Вітер (м/с)", 0.0, 20.0, 3.0)
        w_dir = st.number_input("Напрям (год)", 1, 12, 3)
        angle = st.number_input("Кут цілі (°)", -60, 60, 0)
    with ec2:
        temp = st.number_input("Темп. (°C)", -30, 50, 15)
        press = st.number_input("Тиск (hPa)", 800, 1150, 1013)

with tab_gun:
    gc1, gc2 = st.columns(2)
    with gc1:
        v0 = st.number_input("V0 (м/с)", 300, 1200, 820)
        bc = st.number_input("BC", 0.1, 1.2, 0.505, format="%.3f")
        model = st.radio("Модель", ["G1", "G7"], horizontal=True, index=1)
    with gc2:
        weight = st.number_input("Вага (гран)", 40, 400, 175)
        twist = st.number_input("Твіст", 7.0, 14.0, 10.0)
        sh = st.number_input("Вис. прицілу (см)", 3.0, 12.0, 5.0)
        zero_dist = st.number_input("Нуль (м)", 50, 600, 100)
        twist_dir = st.radio("Нарізи", ["Right (Правий)", "Left (Лівий)"], horizontal=True)
        t_coeff = st.number_input("Термо %", 0.0, 2.0, 0.1)

# ОБЧИСЛЕННЯ
p = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 'pressure': press, 
     'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle, 'twist': twist, 'zero_dist': zero_dist, 
     'max_dist': dist_input, 'sh': sh, 't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

df, v_final, bc_final = run_simulation(p)
res = df.iloc[-1]

# HUD
st.markdown("<br>", unsafe_allow_html=True)
r1, r2 = st.columns(2)
r1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ</div><div class="hud-value" style="color:#ffcc00">{res["UP/DN"]}</div><div class="hud-sub">Падіння: {int(res["Падіння"])} см</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТАЛЬ</div><div class="hud-value" style="color:#ffcc00">{res["L/R"]}</div><div class="hud-sub">Вітер + Дер.</div></div>', unsafe_allow_html=True)

# ГРАФІКИ (ПОВЕРНЕННЯ ОРИГІНАЛЬНОГО СТИЛЮ)
with tab_vis:
    st.markdown("### 📉 Траєкторія польоту")
    
    y_data = df['Падіння'].values
    x_data = df['Дист.'].values
    
    # Розрахунок дуги (лінеаризація відносно лінії прицілювання)
    y_shifted = y_data - y_data[0]
    slope = -y_shifted[-1] / x_data[-1] if x_data[-1] > 0 else 0
    y_arc = y_shifted + slope * x_data
    
    max_h_val = np.max(y_arc)
    max_h_idx = np.argmax(y_arc)
    dist_at_max = x_data[max_h_idx]
    drop_at_target = y_data[-1]

    fig = go.Figure()

    # Зелена дуга (Траєкторія)
    fig.add_trace(go.Scatter(
        x=x_data, y=y_arc, mode='lines', name='Траєкторія',
        line=dict(color='#00ff41', width=3),
        fill='tozeroy', fillcolor='rgba(0, 255, 65, 0.1)'
    ))

    # Жовта точка (Макс. висота)
    fig.add_trace(go.Scatter(
        x=[dist_at_max], y=[max_h_val], mode='markers+text',
        text=[f"МАКС: {max_h_val:.1f} см"], textposition="top center",
        marker=dict(color='#ffcc00', size=10, symbol='diamond')
    ))

    # Червоний хрест (Абсолютне падіння)
    fig.add_trace(go.Scatter(
        x=[x_data[-1]], y=[drop_at_target], mode='markers+text',
        text=[f"Без попр: {drop_at_target:.0f} см"], textposition="bottom center",
        marker=dict(color='#ff3333', size=12, symbol='x')
    ))
    
    # Трансзвукова зона (Mach 1.2)
    transonic = df[df['Mach'] <= 1.2]
    if not transonic.empty:
        m_dist = transonic.iloc[0]['Дист.']
        fig.add_vline(x=m_dist, line_dash="dash", line_color="#ff00ff", 
                      annotation_text="ТРАНСЗВУК", annotation_position="top left")

    fig.update_layout(
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,15,20,0.5)',
        height=400, margin=dict(l=10, r=10, t=20, b=10), showlegend=False,
        xaxis=dict(title="Відстань (м)", gridcolor='#333'),
        yaxis=dict(title="Висота/Падіння (см)", gridcolor='#333')
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📋 Таблиця поправок")
    step = st.select_slider("Крок таблиці", [25, 50, 100], 100)
    st.dataframe(df[df['Дист.'] % step == 0], use_container_width=True, hide_index=True)
