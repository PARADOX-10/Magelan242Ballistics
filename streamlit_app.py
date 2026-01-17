import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Hyper Pro", layout="wide", initial_sidebar_state="collapsed")

def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except: return None

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #040404; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 20px;}
        .hud-card { background: rgba(15, 20, 25, 0.95); border: 1px solid #333; border-left: 5px solid #00ff41; border-radius: 10px; padding: 15px; text-align: center; }
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;}
        .hud-value { color: #fff; font-size: 1.8rem; font-weight: 700; text-shadow: 0 0 10px rgba(0,255,65,0.2); }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО: МЕТОД РУНГЕ-КУТТИ 4-ГО ПОРЯДКУ (RK4) ---
def get_derivatives(state, p_physics):
    # Розпаковка стану: [x, y, z, vx, vy, vz]
    _, y, z, vx, vy, vz = state
    
    # Константи та параметри
    G = 9.80665
    OMEGA_E = 7.292115e-5
    
    v_air_x = vx + p_physics['w_long']
    v_total = math.sqrt(v_air_x**2 + vy**2 + vz**2)
    mach = v_total / p_physics['c_speed']
    
    # Drag Model
    if p_physics['model'] == "G7":
        cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
    else:
        cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
        
    accel_drag = (0.5 * p_physics['rho_rel'] * v_total**2 * cd * (1.0/p_physics['bc_eff'])) * 0.00105
    
    # Coriolis Forces
    cor_y = 2 * OMEGA_E * vx * math.cos(p_physics['lat_rad']) * math.sin(p_physics['az_rad'])
    cor_z = 2 * OMEGA_E * (vy * math.cos(p_physics['lat_rad']) * math.cos(p_physics['az_rad']) - vx * math.sin(p_physics['lat_rad']))

    # Похідні: [dx/dt, dy/dt, dz/dt, dvx/dt, dvy/dt, dvz/dt]
    ax = -(accel_drag * (v_air_x / v_total))
    ay = -(accel_drag * (vy / v_total)) - G + cor_y
    az = -(accel_drag * (vz / v_total)) + cor_z
    
    return np.array([vx, vy, vz, ax, ay, az])

def run_simulation(p):
    DT = 0.002 # Крок часу (RK4 дозволяє більший крок при вищій точності)
    
    # Параметри середовища
    ref_w = 175.0
    v0_eff = p['v0'] * math.sqrt(ref_w / p['weight_gr']) + (p['temp'] - 15) * p['t_coeff']
    bc_eff = p['bc'] * (p['weight_gr'] / ref_w)
    
    tk = p['temp'] + 273.15
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0)
    rho = ((p['pressure'] - pv) * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    
    p_phys = {
        'rho_rel': rho / 1.225, 'c_speed': 331.3 * math.sqrt(tk / 273.15),
        'bc_eff': bc_eff, 'model': p['model'], 'lat_rad': math.radians(p['latitude']),
        'az_rad': math.radians(p['azimuth']), 'w_long': p['w_speed'] * math.cos(math.radians(p['w_dir'] * 30)),
        'w_cross': p['w_speed'] * math.sin(math.radians(p['w_dir'] * 30))
    }

    s_g = (30 * p['weight_gr']) / ((p['twist']**2) * (p['caliber']**3) * (v0_eff/600))
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    angle_zero = math.atan((0.5 * 9.80665 * (p['zero_dist']/v0_eff)**2 + p['sh']/100) / p['zero_dist'])
    
    # Початковий вектор стану: [x, y, z, vx, vy, vz]
    state = np.array([0.0, -p['sh']/100, 0.0, 
                      v0_eff * math.cos(angle_zero + math.radians(p['angle'])), 
                      v0_eff * math.sin(angle_zero + math.radians(p['angle'])), 0.0])
    
    t, dist = 0.0, 0.0
    results_list = []
    step_check = 0

    while dist <= p['max_dist'] + 5:
        # --- RK4 STEP ---
        k1 = get_derivatives(state, p_phys)
        k2 = get_derivatives(state + k1 * DT / 2, p_phys)
        k3 = get_derivatives(state + k2 * DT / 2, p_phys)
        k4 = get_derivatives(state + k3 * DT, p_phys)
        
        state = state + (k1 + 2*k2 + 2*k3 + k4) * DT / 6
        t += DT
        dist = state[0]
        
        if dist >= step_check:
            v_curr = math.sqrt(state[3]**2 + state[4]**2 + state[5]**2)
            w_drift = p_phys['w_cross'] * (t - (dist / v0_eff))
            s_drift = -1 * (0.06 * (dist/100)**2 * t_dir) / s_g
            aero_jump = (p_phys['w_cross'] * 0.002 * t_dir * dist / 100)
            
            y_f, z_f = state[1] + aero_jump, state[2] + w_drift + s_drift
            is_m = "MRAD" in p['turret_unit']
            conv, clk = (1.0 if is_m else 3.4377), (0.1 if is_m else 0.25)
            mv, mh = (y_f * 100) / (dist / 10) if dist > 0 else 0, (z_f * 100) / (dist / 10) if dist > 0 else 0
            
            results_list.append({
                "Дист.": int(dist), "UP/DN": f"{'⬆️' if mv > 0 else '⬇️'} {abs(mv*conv/clk):.1f}",
                "L/R": f"{'➡️' if mh > 0 else '⬅️'} {abs(mh*conv/clk):.1f}",
                "V": int(v_curr), "Mach": round(v_curr/p_phys['c_speed'], 2), 
                "E": int(0.5 * (p['weight_gr']*0.0000647989) * v_curr**2), "Падіння": y_f * 100, "Sg": round(s_g, 2)
            })
            step_check += 10
            
    return pd.DataFrame(results_list), v0_eff

# --- ІНТЕРФЕЙС (Restored Graphics) ---
logo_html = f'<img src="data:image/png;base64,{get_img_as_base64("logo.png")}" style="width:100px;">' if os.path.exists("logo.png") else '🎯'
st.markdown(f'<div class="header-container">{logo_html}<div class="header-title">Magelan242 ULTRA<span class="header-sub">Hyper Precision RK4 Solver V4.3</span></div></div>', unsafe_allow_html=True)

t_res, t_env, t_gun = st.tabs(["🚀 ОБЧИСЛЕННЯ", "🌍 СЕРЕДОВИЩЕ", "🔫 КОМПЛЕКС"])

with t_env:
    e1, e2 = st.columns(2)
    with e1:
        temp = st.slider("Температура (°C)", -30, 50, 15); hum = st.slider("Вологість (%)", 0, 100, 50); press = st.number_input("Тиск (hPa)", 800, 1100, 1013)
    with e2:
        lat = st.number_input("Широта", 0, 90, 50); az = st.slider("Азимут (°)", 0, 360, 90); w_s = st.number_input("Вітер (м/с)", 0.0, 20.0, 2.0); w_d = st.slider("Напрям (год)", 1, 12, 3)

with t_gun:
    g1, g2 = st.columns(2)
    with g1:
        v0 = st.number_input("V0 еталон", 300, 1300, 820); bc = st.number_input("BC еталон", 0.1, 1.2, 0.505, format="%.3f"); weight = st.number_input("Вага (гран)", 40, 400, 175); model = st.radio("Модель", ["G1", "G7"], index=1, horizontal=True)
    with g2:
        cal = st.number_input("Калібр (дюйм)", 0.22, 0.50, 0.308); twist = st.number_input("Твіст", 6.0, 15.0, 10.0); sh = st.number_input("Вис. прицілу (см)", 3.0, 12.0, 5.0); zero = st.number_input("Пристрілка (м)", 50, 600, 100)

with t_res:
    dist_max = st.number_input("ДИСТАНЦІЯ (м)", 100, 3000, 1000, step=50); unit = st.selectbox("СІТКА", ["MRAD", "MOA"])
    params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 'pressure': press, 'humid': hum, 'latitude': lat, 'azimuth': az, 'w_speed': w_s, 'w_dir': w_d, 'angle': 0, 'twist': twist, 'caliber': cal, 'zero_dist': zero, 'max_dist': dist_max, 'sh': sh, 't_coeff': 0.1, 'turret_unit': unit, 'twist_dir': "Right (Правий)"}

    df, v_f = run_simulation(params); res = df.iloc[-1]

    st.markdown("---")
    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль</div><div class="hud-value" style="color:#ffcc00">{res["UP/DN"]}</div></div>', unsafe_allow_html=True)
    h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт</div><div class="hud-value" style="color:#ffcc00">{res["L/R"]}</div></div>', unsafe_allow_html=True)
    h3.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість</div><div class="hud-value">{res["V"]} м/с</div></div>', unsafe_allow_html=True)
    h4.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність</div><div class="hud-value">{res["Sg"]}</div></div>', unsafe_allow_html=True)

    # ВІЗУАЛІЗАЦІЯ
    y_data, x_data = df['Падіння'].values, df['Дист.'].values
    y_arc = (y_data - y_data[0]) + (- (y_data[-1] - y_data[0]) / x_data[-1] if x_data[-1] > 0 else 0) * x_data
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_data, y=y_arc, mode='lines', line=dict(color='#00ff41', width=3), fill='tozeroy', fillcolor='rgba(0,255,65,0.1)'))
    fig.add_trace(go.Scatter(x=[x_data[np.argmax(y_arc)]], y=[np.max(y_arc)], mode='markers+text', text=[f"MAX: {np.max(y_arc):.1f}см"], textposition="top center", marker=dict(color='#ffcc00', size=10, symbol='diamond')))
    fig.add_trace(go.Scatter(x=[x_data[-1]], y=[y_data[-1]], mode='markers+text', text=[f"DROP: {y_data[-1]:.0f}см"], textposition="bottom center", marker=dict(color='#ff3333', size=12, symbol='x')))
    trans = df[df['Mach'] <= 1.2]
    if not trans.empty: fig.add_vline(x=trans.iloc[0]['Дист.'], line_dash="dash", line_color="#ff00ff", annotation_text="TRANSONIC")
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,15,20,0.5)')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df[df['Дист.'] % 100 == 0], use_container_width=True, hide_index=True)
