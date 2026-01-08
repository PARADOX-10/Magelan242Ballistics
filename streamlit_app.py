import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- БАЗА НАБОЇВ ---
AMMO_DB = {
    "5.45x39 7N6 (AK-74)": {"cal": 0.214, "len": 0.98, "weight": 53.0, "bc": 0.168, "model": "G7", "v0": 880},
    "5.56x45 (.223 Rem) 62gr": {"cal": 0.224, "len": 0.93, "weight": 62.0, "bc": 0.151, "model": "G7", "v0": 915},
    "7.62x39 (AK-47/SKS)": {"cal": 0.311, "len": 0.93, "weight": 123.0, "bc": 0.145, "model": "G7", "v0": 715},
    "7.62x51 (.308 Win) 175gr": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "7.62x54R 174gr (SVD/LPS)": {"cal": 0.311, "len": 1.25, "weight": 174.0, "bc": 0.235, "model": "G7", "v0": 820},
    "6.5 Creedmoor 140gr": {"cal": 0.264, "len": 1.35, "weight": 140.0, "bc": 0.315, "model": "G7", "v0": 825},
    ".300 Win Mag 200gr": {"cal": 0.308, "len": 1.45, "weight": 200.0, "bc": 0.285, "model": "G7", "v0": 870},
    ".338 Lapua Mag 300gr": {"cal": 0.338, "len": 1.78, "weight": 300.0, "bc": 0.368, "model": "G7", "v0": 825},
    ".375 CheyTac 350gr": {"cal": 0.375, "len": 2.05, "weight": 350.0, "bc": 0.405, "model": "G7", "v0": 930},
    ".50 BMG (12.7x99) 750gr": {"cal": 0.510, "len": 2.31, "weight": 750.0, "bc": 0.490, "model": "G7", "v0": 850},
}

st.set_page_config(page_title="Magelan242 Analytics", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 10px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 20px;}
    .hud-card { background-color: #FFFFFF; border-left: 8px solid #C62828; padding: 15px; text-align: center; border-radius: 5px; }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 24px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def get_point_data(p, d):
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    v_dist = v0_eff * math.exp(-k * d)
    energy = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    # Траєкторія (MIL)
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    # Вітер та AJ
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
    wind_drift = (cross_w * (t - (d/v0_eff)))
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (d / 100)**2)
    
    v_mil = abs(((y_m + aj_shift) * 100) / (d / 10) / 0.1) if d > 0 else 0
    h_mil = abs(((wind_drift + derivation) * 100) / (d / 10) / 0.1) if d > 0 else 0
    
    return {"dist": d, "v_mil": v_mil, "h_mil": h_mil, "energy": energy, "vel": v_dist, "drop_cm": y_m*100}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : ПОВНИЙ ГРАФІЧНИЙ АНАЛІЗ</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Конфігурація")
    choice = st.selectbox("Набій:", list(AMMO_DB.keys()))
    base = AMMO_DB[choice]
    m_v0 = st.number_input("V0 (м/с)", 100, 1500, base['v0'])
    m_bc = st.number_input("БК", 0.05, 1.5, base['bc'], format="%.3f")
    m_weight = st.number_input("Вага (гран)", 1.0, 1000.0, base['weight'])
    m_twist = st.number_input("Твіст 1:", 5.0, 24.0, 10.0)
    m_side = st.radio("Нарізи", ["Правобічні", "Лівобічні"], horizontal=True)
    m_sh = st.number_input("Висота прицілу (см)", 0.0, 20.0, 5.0)

# Умови
c1, c2, c3, c4 = st.columns(4)
dist_max = c1.number_input("Макс. дистанція (м)", 100, 4000, 1000, step=100)
temp = c2.number_input("Температура (°C)", -50, 60, 15)
press = c3.number_input("Тиск (гПа)", 700, 1150, 1013)
w_speed = c4.number_input("Вітер (м/с)", 0.0, 40.0, 5.0)
w_hour = st.select_slider("Напрямок вітру (година)", options=list(range(1, 13)), value=3)

# Розрахунок даних для графіків
p = {**base, 'v0': m_v0, 'bc': m_bc, 'weight': m_weight, 'twist': m_twist, 'twist_side': m_side, 
     'sh': m_sh, 'temp': temp, 'press': press, 'w_speed': w_speed, 'wind_hour': w_hour, 'angle': 0, 'zero': 100}

steps = np.arange(0, dist_max + 10, 10)
plot_data = [get_point_data(p, d) for d in steps]
df = pd.DataFrame(plot_data)

# HUD РЕЗУЛЬТАТІВ (на макс. дистанції)
st.markdown("<br>", unsafe_allow_html=True)
curr = plot_data[-1]
r1, r2, r3, r4 = st.columns(4)
r1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль (MIL)</div><div class="hud-value">↑ {curr["v_mil"]:.1 (MISSING)}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонталь (MIL)</div><div class="hud-value">↔ {curr["h_mil"]:.1 (MISSING)}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{int(curr["energy"])}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість (м/с)</div><div class="hud-value">{int(curr["vel"])}</div></div>', unsafe_allow_html=True)

# ГРАФІКИ
st.divider()
fig = make_subplots(rows=2, cols=2, 
                    subplot_titles=("Траєкторія (Падіння в см)", "Поправки (MIL)", 
                                    "Енергія (Джоулі)", "Швидкість (м/с)"))

# 1. Траєкторія
fig.add_trace(go.Scatter(x=df['dist'], y=df['drop_cm'], name="Падіння", line=dict(color='#C62828', width=3)), row=1, col=1)
# 2. MIL (Vertical & Horizontal)
fig.add_trace(go.Scatter(x=df['dist'], y=df['v_mil'], name="V MIL", line=dict(color='#FFD700')), row=1, col=2)
fig.add_trace(go.Scatter(x=df['dist'], y=df['h_mil'], name="H MIL", line=dict(color='#00BFFF', dash='dash')), row=1, col=2)
# 3. Енергія
fig.add_trace(go.Scatter(x=df['dist'], y=df['energy'], name="Енергія", fill='tozeroy', line=dict(color='#4CAF50')), row=2, col=1)
# 4. Швидкість
fig.add_trace(go.Scatter(x=df['dist'], y=df['vel'], name="Швидкість", line=dict(color='#9C27B0')), row=2, col=2)
# Додаємо лінію швидкості звуку
fig.add_shape(type="line", x0=0, y0=340, x1=dist_max, y1=340, line=dict(color="white", dash="dot"), row=2, col=2)

fig.update_layout(height=700, template="plotly_dark", showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)
