import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Ultra Analytics", layout="wide", initial_sidebar_state="collapsed")

# --- БАЗА ДАНИХ КУЛЬ ---
BULLET_DB = {
    "Custom Bullet": None,
    "6.5 CM: Hornady ELD-M 140gr": [0.264, 140, 0.326, "G7"],
    ".308 Win: Sierra SMK 175gr": [0.308, 175, 0.243, "G7"],
    ".338 LM: Lapua Scenar 300gr": [0.338, 300, 0.368, "G7"]
}

# --- БАЛІСТИЧНЕ ЯДРО: RK4 ---
def get_derivatives(state, p):
    _, _, _, vx, vy, vz = state
    G, OMEGA_E = 9.80665, 7.292115e-5
    v_rel_x, v_rel_y, v_rel_z = vx + p['w_long'], vy, vz + p['w_cross']
    v_total_rel = math.sqrt(v_rel_x**2 + v_rel_y**2 + v_rel_z**2)
    mach = v_total_rel / p['c_speed']
    cd = (0.22 + 0.12 / (mach**1.5 + 0.1)) if p['model'] == "G7" else (0.42 + 0.1 / (mach**2 + 0.1))
    accel_drag = (0.5 * p['rho_rel'] * v_total_rel**2 * cd * (1.0/p['bc_eff'])) * 0.00105
    cor_y = 2 * OMEGA_E * vx * math.cos(p['lat_rad']) * math.sin(p['az_rad'])
    cor_z = 2 * OMEGA_E * (vy * math.cos(p['lat_rad']) * math.cos(p['az_rad']) - vx * math.sin(p['lat_rad']))
    return np.array([vx, vy, vz, -(accel_drag * (v_rel_x / v_total_rel)), -(accel_drag * (v_rel_y / v_total_rel)) - G + cor_y, -(accel_drag * (v_rel_z / v_total_rel)) + cor_z])

def run_simulation(p):
    DT = 0.002
    v0_eff = p['v0'] * math.sqrt(175.0 / p['weight_gr']) + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0)
    rho = ((p['pressure'] - pv) * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    p_phys = {
        'rho_rel': rho / 1.225, 'c_speed': 331.3 * math.sqrt(tk / 273.15), 'bc_eff': p['bc'] * (p['weight_gr'] / 175.0),
        'model': p['model'], 'lat_rad': math.radians(p['latitude']), 'az_rad': math.radians(p['azimuth']),
        'w_long': p['w_speed'] * math.cos(math.radians(p['w_dir'] * 30)), 'w_cross': p['w_speed'] * math.sin(math.radians(p['w_dir'] * 30))
    }
    s_g = (30 * p['weight_gr']) / ((p['twist']**2) * (p['caliber']**3) * (v0_eff/600))
    angle_zero = math.atan((0.5 * 9.80665 * (p['zero_dist']/v0_eff)**2 + p['sh']/100) / p['zero_dist'])
    state = np.array([0.0, -p['sh']/100, 0.0, v0_eff * math.cos(angle_zero), v0_eff * math.sin(angle_zero), 0.0])
    t, dist, results = 0.0, 0.0, []
    while dist <= p['max_dist']:
        k1 = get_derivatives(state, p_phys); k2 = get_derivatives(state + k1*DT/2, p_phys)
        k3 = get_derivatives(state + k2*DT/2, p_phys); k4 = get_derivatives(state + k3*DT, p_phys)
        state += (k1 + 2*k2 + 2*k3 + k4) * DT / 6; t += DT; dist = state[0]
        if dist >= (len(results) * 10):
            mv, mh = (state[1] * 100) / (dist / 10), (state[2] + p_phys['w_cross']*(t - dist/v0_eff) - (0.06*(dist/100)**2)/s_g)*100/(dist/10)
            results.append({"D": int(dist), "V": int(math.sqrt(state[3]**2+state[4]**2)), "MV": mv, "MH": mh})
    return pd.DataFrame(results)

# --- ВІЗУАЛІЗАЦІЯ СІТКИ З WEZ ---
def draw_reticle_analytics(mrad_v, mrad_h, unit, wez_data=None):
    limit = 10 if "MRAD" in unit else 35
    fig = go.Figure()
    # Осі
    fig.add_shape(type="line", x0=-limit, y0=0, x1=limit, y1=0, line=dict(color="white", width=1))
    fig.add_shape(type="line", x0=0, y0=-limit, x1=0, y1=limit, line=dict(color="white", width=1))
    
    # "Хмара" влучань (WEZ)
    if wez_data:
        fig.add_trace(go.Scatter(
            x=[-wez_data['h_min'], -wez_data['h_max'], -wez_data['h_max'], -wez_data['h_min']],
            y=[wez_data['v_min'], wez_data['v_min'], wez_data['v_max'], wez_data['v_max']],
            fill="toself", fillcolor="rgba(255, 0, 0, 0.2)", line=dict(color="red", width=1), name="Impact Zone"
        ))

    # Точка влучання
    fig.add_trace(go.Scatter(x=[-mrad_h], y=[mrad_v], mode='markers', marker=dict(color='#00ff41', size=12, symbol='circle-open', line=dict(width=3))))
    fig.update_layout(template="plotly_dark", height=500, width=500, showlegend=False, xaxis=dict(range=[-limit, limit]), yaxis=dict(range=[-limit, limit]))
    return fig

# --- UI ---
st.markdown('<div style="border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px;"><h2>🎯 Magelan242 ULTRA Analytics V4.7</h2></div>', unsafe_allow_html=True)

t_res, t_env, t_gun, t_wez = st.tabs(["🚀 ОБЧИСЛЕННЯ", "🌍 СЕРЕДОВИЩЕ", "🔫 ЗБРОЯ", "🎯 ЙМОВІРНІСТЬ"])

with t_env:
    e1, e2 = st.columns(2)
    temp = e1.slider("Температура (°C)", -20, 40, 15)
    hum = e1.slider("Вологість (%)", 0, 100, 50)
    press = e1.number_input("Тиск (hPa)", 900, 1100, 1013)
    w_s = e2.number_input("Вітер (м/с)", 0.0, 15.0, 3.0)
    w_d = e2.slider("Напрям (год)", 1, 12, 3)
    lat = e2.number_input("Широта", 0, 90, 50)
    az = e2.slider("Азимут (°)", 0, 360, 90)

with t_gun:
    bullet_choice = st.selectbox("База куль", list(BULLET_DB.keys()))
    db = BULLET_DB[bullet_choice]
    g1, g2 = st.columns(2)
    v0 = g1.number_input("V0 (м/с)", 300, 1200, 820)
    weight = g1.number_input("Вага (гран)", 40, 500, db[1] if db else 175)
    bc = g1.number_input("BC G7", 0.1, 1.0, db[2] if db else 0.243, format="%.3f")
    twist = g2.number_input("Твіст", 7.0, 14.0, 10.0)
    cal = g2.number_input("Калібр", 0.22, 0.50, db[0] if db else 0.308)
    sh = g2.number_input("Висота прицілу", 3.0, 12.0, 5.0)
    zero = g2.number_input("Пристрілка (м)", 50, 300, 100)

with t_wez:
    st.markdown("### Аналіз похибок вимірювання")
    w1, w2 = st.columns(2)
    err_wind = w1.slider("Похибка вітру (+/- м/с)", 0.0, 5.0, 1.0)
    err_v0 = w1.slider("Похибка V0 (SD м/с)", 0.0, 10.0, 2.0)
    target_h = w2.number_input("Висота цілі (см)", 10, 200, 50)
    target_w = w2.number_input("Ширина цілі (см)", 10, 200, 30)

# ОБЧИСЛЕННЯ ОСНОВНЕ
params = {'v0': v0, 'bc': bc, 'model': "G7", 'weight_gr': weight, 'temp': temp, 'pressure': press, 'humid': hum, 
          'latitude': lat, 'azimuth': az, 'w_speed': w_s, 'w_dir': w_d, 'angle': 0, 'twist': twist, 
          'caliber': cal, 'zero_dist': zero, 'max_dist': 1000, 'sh': sh, 't_coeff': 0.1, 'turret_unit': "MRAD", 'twist_dir': "Right"}

df = run_simulation(params)
res = df.iloc[-1]

# ОБЧИСЛЕННЯ WEZ (Monte Carlo Lite)
# Рахуємо 4 екстремальні точки
p_min = params.copy(); p_min.update({'w_speed': max(0, w_s - err_wind), 'v0': v0 - err_v0})
p_max = params.copy(); p_max.update({'w_speed': w_s + err_wind, 'v0': v0 + err_v0})
df_min = run_simulation(p_min).iloc[-1]
df_max = run_simulation(p_max).iloc[-1]

wez = {
    'v_min': min(df_min['MV'], df_max['MV']), 'v_max': max(df_min['MV'], df_max['MV']),
    'h_min': min(df_min['MH'], df_max['MH']), 'h_max': max(df_min['MH'], df_max['MH'])
}

with t_res:
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("ВЕРТИКАЛЬ (MRAD)", round(abs(res['MV']), 2))
    c2.metric("ГОРИЗОНТ (MRAD)", round(abs(res['MH']), 2))
    c3.metric("ШВИДКІСТЬ (м/с)", res['V'])
    
    st.plotly_chart(draw_reticle_analytics(res['MV'], res['MH'], "MRAD", wez), use_container_width=True)

with t_wez:
    st.info(f"Червона зона на вкладці 'ОБЧИСЛЕННЯ' показує розсіювання через твої помилки виміру. Чим більша зона, тим менший шанс влучити.")
    st.markdown(f"**Вертикальний розкид:** {abs(wez['v_max'] - wez['v_min']):.2f} MRAD")
    st.markdown(f"**Горизонтальний розкид:** {abs(wez['h_max'] - wez['h_min']):.2f} MRAD")
