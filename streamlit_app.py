import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- ГЛОБАЛЬНА БАЗА НАБОЇВ ---
AMMO_DB = {
    "5.45x39 7N6 (AK-74)": {"cal": 0.214, "len": 0.98, "weight": 53.0, "bc": 0.168, "model": "G7", "v0": 880},
    "5.56x45 (.223 Rem) 62gr": {"cal": 0.224, "len": 0.93, "weight": 62.0, "bc": 0.151, "model": "G7", "v0": 915},
    "7.62x39 (AK-47/SKS)": {"cal": 0.311, "len": 0.93, "weight": 123.0, "bc": 0.145, "model": "G7", "v0": 715},
    "7.62x51 (.308 Win) 175gr": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "7.62x54R 174gr (SVD/LPS)": {"cal": 0.311, "len": 1.25, "weight": 174.0, "bc": 0.235, "model": "G7", "v0": 820},
    "6.5 Creedmoor 140gr": {"cal": 0.264, "len": 1.35, "weight": 140.0, "bc": 0.315, "model": "G7", "v0": 825},
    ".300 Win Mag 200gr": {"cal": 0.308, "len": 1.45, "weight": 200.0, "bc": 0.285, "model": "G7", "v0": 870},
    ".338 Lapua Mag 250gr": {"cal": 0.338, "len": 1.62, "weight": 250.0, "bc": 0.310, "model": "G7", "v0": 900},
    ".338 Lapua Mag 300gr": {"cal": 0.338, "len": 1.78, "weight": 300.0, "bc": 0.368, "model": "G7", "v0": 825},
    ".375 CheyTac 350gr": {"cal": 0.375, "len": 2.05, "weight": 350.0, "bc": 0.405, "model": "G7", "v0": 930},
    ".408 CheyTac 419gr": {"cal": 0.408, "len": 2.15, "weight": 419.0, "bc": 0.450, "model": "G7", "v0": 885},
    ".50 BMG (12.7x99) 750gr": {"cal": 0.510, "len": 2.31, "weight": 750.0, "bc": 0.490, "model": "G7", "v0": 850},
    "9x19 Parabellum 115gr": {"cal": 0.355, "len": 0.61, "weight": 115.0, "bc": 0.140, "model": "G1", "v0": 360},
    ".45 ACP 230gr": {"cal": 0.451, "len": 0.66, "weight": 230.0, "bc": 0.195, "model": "G1", "v0": 255},
    "Кастомний": {"cal": 0.308, "len": 1.0, "weight": 150.0, "bc": 0.200, "model": "G7", "v0": 800}
}

st.set_page_config(page_title="Magelan242 Ultimate", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 15px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(198,40,40,0.3);}
    .hud-card { background-color: #FFFFFF; border-top: 6px solid #C62828; padding: 15px; text-align: center; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 26px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_ballistics(p):
    # Корекція швидкості (температурна чутливість 0.2%/1C від 15C)
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    v_dist = v0_eff * math.exp(-k * p['dist'])
    
    # Енергія (1 гран = 0.0000648 кг)
    energy_j = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    # Траєкторія
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Вітер та Деривація
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    
    # Aerodynamic Jump (AJ)
    aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2)
    wind_drift = (cross_w * (t - (p['dist']/v0_eff)))
    
    # Фінальні MRAD
    v_mil = round(abs(((y_m + aj_shift) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    h_mil = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    
    # SG (Стабільність Міллера)
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)
    
    return v_mil, h_mil, round(t, 3), int(energy_j), round(v_dist, 1), round(sg, 2)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : БАЗА ДАНИХ ТА АНАЛІТИКА</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📦 Вибір боєприпасу")
    choice = st.selectbox("Набій/Куля", list(AMMO_DB.keys()))
    ammo = AMMO_DB[choice]
    
    st.success(f"Калібр: {ammo['cal']}″ | Довжина кулі: {ammo['len']}″")
    
    st.divider()
    v0 = st.number_input("Початкова швидкість (м/с)", 100, 1500, ammo['v0'])
    bc = st.number_input(f"БК ({ammo['model']})", 0.05, 1.5, ammo['bc'], format="%.3f")
    weight = st.number_input("Вага (гран)", 1.0, 1000.0, ammo['weight'])
    
    st.divider()
    st.header("🔫 Параметри ствола")
    twist = st.number_input("Крок нарізів (1:X)", 5.0, 24.0, 10.0)
    side = st.radio("Напрямок нарізів", ["Правобічні", "Лівобічні"], horizontal=True)
    sh = st.number_input("Висота прицілу (см)", 0.0, 20.0, 5.0)

# ОСНОВНА ПАНЕЛЬ
c1, c2, c3, c4 = st.columns(4)
dist = c1.number_input("Дистанція (м)", 0, 4000, 500, step=10)
temp = c2.number_input("Температура (°C)", -50, 60, 15)
press = c3.number_input("Тиск (гПа)", 700, 1150, 1013)
w_speed = c4.number_input("Швидкість вітру (м/с)", 0.0, 40.0, 4.0)

c5, c6, c7 = st.columns([1, 1, 2])
w_hour = c5.select_slider("Вітер (год)", options=list(range(1, 13)), value=3)
angle = c6.number_input("Кут (°)", -80, 80, 0)

# РОЗРАХУНОК
params = {
    'dist': dist, 'temp': temp, 'press': press, 'v0': v0, 'bc': bc, 
    'weight': weight, 'twist': twist, 'twist_side': side, 
    'wind_hour': w_hour, 'w_speed': w_speed, 'angle': angle, 
    'model': ammo['model'], 'sh': sh, 'zero': 100,
    'cal': ammo['cal'], 'len': ammo['len']
}
res_v, res_h, res_t, res_e, res_v_dist, res_sg = calculate_ballistics(params)

# ВИВІД HUD
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль (MIL)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонталь (MIL)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{res_e}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість (м/с)</div><div class="hud-value">{res_v_dist}</div></div>', unsafe_allow_html=True)
r5.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність (SG)</div><div class="hud-value">{res_sg}</div></div>', unsafe_allow_html=True)

# ГРАФІК ЕФЕКТИВНОСТІ
st.divider()
st.subheader("📊 Аналіз траєкторії та енергії")

steps = np.arange(0, dist + 501, 20)
v_data = []
e_data = []
for d in steps:
    params['dist'] = d
    _, _, _, e, v, _ = calculate_ballistics(params)
    v_data.append(v)
    e_data.append(e)

fig = go.Figure()
fig.add_trace(go.Scatter(x=steps, y=v_data, name="Швидкість (м/с)", line=dict(color='#2196F3', width=3)))
fig.add_trace(go.Scatter(x=steps, y=e_data, name="Енергія (Дж)", yaxis="y2", line=dict(color='#4CAF50', width=3)))

fig.update_layout(
    template="plotly_dark",
    yaxis=dict(title="Швидкість (м/с)"),
    yaxis2=dict(title="Енергія (Дж)", overlaying='y', side='right'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    height=450, showlegend=True
)
st.plotly_chart(fig, use_container_width=True)

# ТАБЛИЦЯ ПОПРАВОК
if st.checkbox("Показати таблицю поправок"):
    table_rows = []
    for d in range(0, dist + 101, 50):
        params['dist'] = d
        v, h, t, e, vel, _ = calculate_ballistics(params)
        table_rows.append({"Метри": d, "Вертикаль (MIL)": v, "Горизонт (MIL)": h, "Енергія": e, "Швидкість": vel})
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)
