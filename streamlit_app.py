import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 Ultra V4.7", layout="wide", initial_sidebar_state="collapsed")

# --- БАЗА ДАНИХ КУЛЬ ---
BULLET_DB = {
    "Custom Bullet (Ручне введення)": None,
    "6.5 CM: Hornady ELD-M 140gr": [0.264, 140, 0.326, "G7"],
    "6.5 CM: Lapua Scenar-L 136gr": [0.264, 136, 0.274, "G7"],
    ".308 Win: Sierra SMK 175gr": [0.308, 175, 0.243, "G7"],
    ".308 Win: Lapua Scenar 167gr": [0.308, 167, 0.216, "G7"],
    ".338 LM: Lapua Scenar 300gr": [0.338, 300, 0.368, "G7"],
    ".50 BMG: Hornady A-MAX 750gr": [0.510, 750, 0.511, "G7"]
}

# --- CSS СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #040404; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 20px;}
        .hud-card { background: rgba(15, 20, 25, 0.95); border-left: 5px solid #00ff41; border-radius: 10px; padding: 15px; text-align: center; }
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;}
        .hud-value { color: #fff; font-size: 1.8rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО: ПОВНИЙ ВЕКТОРНИЙ RK4 ---
def get_derivatives(state, p):
    # state: [x, y, z, vx, vy, vz]
    vx, vy, vz = state[3], state[4], state[5]
    G, OMEGA_E = 9.80665, 7.292115e-5
    
    # Вектор відносної швидкості (Bullet - Wind)
    v_rel_x, v_rel_y, v_rel_z = vx + p['w_long'], vy, vz + p['w_cross']
    v_total_rel = math.sqrt(v_rel_x**2 + v_rel_y**2 + v_rel_z**2)
    mach = v_total_rel / p['c_speed']
    
    # Drag Model
    cd = (0.22 + 0.12 / (mach**1.5 + 0.1)) if p['model'] == "G7" else (0.42 + 0.1 / (mach**2 + 0.1))
    accel_drag = (0.5 * p['rho_rel'] * v_total_rel**2 * cd * (1.0/p['bc_eff'])) * 0.00105
    
    # Coriolis
    cor_y = 2 * OMEGA_E * vx * math.cos(p['lat_rad']) * math.sin(p['az_rad'])
    cor_z = 2 * OMEGA_E * (vy * math.cos(p['lat_rad']) * math.cos(p['az_rad']) - vx * math.sin(p['lat_rad']))

    return np.array([vx, vy, vz, 
                     -(accel_drag * (v_rel_x / v_total_rel)), 
                     -(accel_drag * (v_rel_y / v_total_rel)) - G + cor_y, 
                     -(accel_drag * (v_rel_z / v_total_rel)) + cor_z])

def run_simulation(p):
    DT = 0.0015
    ref_w = 175.0
    v0_eff = p['v0'] * math.sqrt(ref_w / p['weight_gr']) + (p['temp'] - 15) * p['t_coeff']
    
    # Атмосфера
    tk = p['temp'] + 273.15
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0)
    rho = ((p['pressure'] - pv) * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    
    p_phys = {
        'rho_rel': rho / 1.225, 'c_speed': 331.3 * math.sqrt(tk / 273.15),
        'bc_eff': p['bc'] * (p['weight_gr'] / ref_w), 'model': p['model'], 
        'lat_rad': math.radians(p['latitude']), 'az_rad': math.radians(p['azimuth']),
        'w_long': p['w_speed'] * math.cos(math.radians(p['w_dir'] * 30)),
        'w_cross': p['w_speed'] * math.sin(math.radians(p['w_dir'] * 30))
    }
    
    s_g = (30 * p['weight_gr']) / ((p['twist']**2) * (p['caliber']**3) * (v0_eff/600))
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    angle_zero = math.atan((0.5 * 9.80665 * (p['zero_dist']/v0_eff)**2 + p['sh']/100) / p['zero_dist'])
    
    state = np.array([0.0, -p['sh']/100, 0.0, v0_eff * math.cos(angle_zero), v0_eff * math.sin(angle_zero), 0.0])
    t, dist, results = 0.0, 0.0, []
    step_check = 0

    while dist <= p['max_dist'] + 5:
        k1 = get_derivatives(state, p_phys)
        k2 = get_derivatives(state + k1*DT/2, p_phys)
        k3 = get_derivatives(state + k2*DT/2, p_phys)
        k4 = get_derivatives(state + k3*DT, p_phys)
        state += (k1 + 2*k2 + 2*k3 + k4) * DT / 6
        t += DT; dist = state[0]
        
        if dist >= step_check:
            v_curr = math.sqrt(state[3]**2 + state[4]**2 + state[5]**2)
            s_drift = -1 * (0.06 * (dist/100)**2 * t_dir) / s_g
            aero_jump = (p_phys['w_cross'] * 0.002 * t_dir * dist / 100)
            y_f, z_f = state[1] + aero_jump, state[2] + s_drift
            
            mv, mh = (y_f * 100) / (dist / 10) if dist > 0 else 0, (z_f * 100) / (dist / 10) if dist > 0 else 0
            results.append({"Дист.": int(dist), "V": int(v_curr), "Mach": round(v_curr/p_phys['c_speed'], 2), 
                            "Падіння": y_f * 100, "MV": mv, "MH": mh, "Sg": round(s_g, 2)})
            step_check += 10
    return pd.DataFrame(results)

# --- ВІЗУАЛІЗАЦІЯ СІТКИ ТА WEZ ---
def draw_reticle(mrad_v, mrad_h, unit, wez=None):
    limit = 12 if "MRAD" in unit else 40
    fig = go.Figure()
    
    if wez: # Зона розсіювання
        fig.add_trace(go.Scatter(x=[-wez['h_min'], -wez['h_max'], -wez['h_max'], -wez['h_min']], 
                                 y=[wez['v_min'], wez['v_min'], wez['v_max'], wez['v_max']],
                                 fill="toself", fillcolor="rgba(255, 0, 0, 0.2)", line=dict(color="red", width=1)))
    
    fig.add_shape(type="line", x0=-limit, y0=0, x1=limit, y1=0, line=dict(color="white", width=1))
    fig.add_shape(type="line", x0=0, y0=-limit, x1=0, y1=limit, line=dict(color="white", width=1))
    fig.add_trace(go.Scatter(x=[-mrad_h], y=[mrad_v], mode='markers', 
                             marker=dict(color='#00ff41', size=14, symbol='circle-open', line=dict(width=3))))
    fig.update_layout(template="plotly_dark", height=500, width=500, showlegend=False, 
                      xaxis=dict(range=[-limit, limit]), yaxis=dict(range=[-limit, limit]))
    return fig

# --- UI INTERFACE ---
st.markdown('<div class="header-container"><div style="font-size:2rem;">🎯</div><div class="header-title">Magelan242 ULTRA<span class="header-sub">Ultimate V4.7 | RK4 Analytics Edition</span></div></div>', unsafe_allow_html=True)

t_res, t_env, t_gun, t_wez = st.tabs(["🚀 ОБЧИСЛЕННЯ", "🌍 СЕРЕДОВИЩЕ", "🔫 ЗБРОЯ", "📊 АНАЛІТИКА WEZ"])

with t_env:
    c1, c2 = st.columns(2)
    temp = c1.slider("Температура (°C)", -30, 50, 15)
    hum = c1.slider("Вологість (%)", 0, 100, 50)
    press = c1.number_input("Тиск (hPa)", 800, 1150, 1013)
    lat = c2.number_input("Широта (Коріолiс)", 0, 90, 50)
    az = c2.slider("Азимут вогню (°)", 0, 360, 90)
    w_s = c2.number_input("Вітер (м/с)", 0.0, 20.0, 2.0)
    w_d = c2.slider("Напрям вітру (год)", 1, 12, 3)

with t_gun:
    bullet = st.selectbox("База даних куль", list(BULLET_DB.keys()))
    db = BULLET_DB[bullet]
    g1, g2 = st.columns(2)
    v0 = g1.number_input("V0 (м/с)", 300, 1300, 820)
    weight = g1.number_input("Вага (гран)", 40, 600, db[1] if db else 175)
    bc = g1.number_input("BC G7", 0.1, 1.2, db[2] if db else 0.505, format="%.3f")
    cal = g2.number_input("Калібр (дюйм)", 0.22, 0.51, db[0] if db else 0.308)
    twist = g2.number_input("Твіст", 6.0, 15.0, 10.0)
    sh = g2.number_input("Висота прицілу (см)", 3.0, 15.0, 5.0)
    zero = g2.number_input("Пристрілка (м)", 50, 600, 100)

with t_wez:
    st.markdown("### Аналіз ймовірності влучання")
    err_w = st.slider("Похибка вітру (+/- м/с)", 0.0, 5.0, 1.0)
    err_v = st.slider("Похибка V0 (SD м/с)", 0.0, 10.0, 2.0)

# ОСНОВНИЙ РОЗРАХУНОК
p_main = {'v0': v0, 'bc': bc, 'model': "G7", 'weight_gr': weight, 'temp': temp, 'pressure': press, 'humid': hum, 
          'latitude': lat, 'azimuth': az, 'w_speed': w_s, 'w_dir': w_d, 'angle': 0, 'twist': twist, 
          'caliber': cal, 'zero_dist': zero, 'max_dist': 1000, 'sh': sh, 't_coeff': 0.1, 'turret_unit': "MRAD", 'twist_dir': "Right (Правий)"}

try:
    df = run_simulation(p_main); res = df.iloc[-1]
    
    # РОЗРАХУНОК WEZ (Зони розсіювання)
    p_min = p_main.copy(); p_min.update({'w_speed': max(0, w_s - err_w), 'v0': v0 - err_v})
    p_max = p_main.copy(); p_max.update({'w_speed': w_s + err_w, 'v0': v0 + err_v})
    res_min, res_max = run_simulation(p_min).iloc[-1], run_simulation(p_max).iloc[-1]
    wez_zone = {'v_min': min(res_min['MV'], res_max['MV']), 'v_max': max(res_min['MV'], res_max['MV']),
                'h_min': min(res_min['MH'], res_max['MH']), 'h_max': max(res_min['MH'], res_max['MH'])}

    with t_res:
        st.markdown("---")
        h1, h2, h3 = st.columns(3)
        h1.metric("ВЕРТИКАЛЬ (MRAD)", round(abs(res['MV']), 2))
        h2.metric("ГОРИЗОНТ (MRAD)", round(abs(res['MH']), 2))
        h3.metric("СТАБІЛЬНІСТЬ Sg", res['Sg'])
        st.plotly_chart(draw_reticle(res['MV'], res['MH'], "MRAD", wez_zone), use_container_width=True)
        st.dataframe(df[df['Дист.'] % 100 == 0], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Помилка: {e}")
