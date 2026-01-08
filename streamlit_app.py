import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ГОЛОВНА БАЗА ДАНИХ ---
AMMO_DB = {
    # .300 Win Mag (Розширено)
    ".300 WM Berger Elite Hunter 230gr": {"cal": 0.308, "len": 1.68, "weight": 230.0, "bc": 0.410, "model": "G7", "v0": 820},
    ".300 WM Hornady ELD-M 225gr": {"cal": 0.308, "len": 1.64, "weight": 225.0, "bc": 0.391, "model": "G7", "v0": 830},
    ".300 WM Berger Hybrid 215gr": {"cal": 0.308, "len": 1.60, "weight": 215.0, "bc": 0.354, "model": "G7", "v0": 850},
    ".300 WM Hornady ELD-M 208gr": {"cal": 0.308, "len": 1.54, "weight": 208.0, "bc": 0.320, "model": "G7", "v0": 855},
    ".300 WM Sierra MK 200gr": {"cal": 0.308, "len": 1.48, "weight": 200.0, "bc": 0.287, "model": "G7", "v0": 870},
    ".300 WM Sierra MK 190gr": {"cal": 0.308, "len": 1.35, "weight": 190.0, "bc": 0.265, "model": "G7", "v0": 880},
    # Інші популярні набої
    "7.62x51 M118LR (175gr)": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "6.5 Creedmoor ELD-M 147gr": {"cal": 0.264, "len": 1.43, "weight": 147.0, "bc": 0.351, "model": "G7", "v0": 810},
    ".338 LM Scenar 300gr": {"cal": 0.338, "len": 1.78, "weight": 300.0, "bc": 0.368, "model": "G7", "v0": 825},
    ".50 BMG Hornady A-MAX": {"cal": 0.510, "len": 2.31, "weight": 750.0, "bc": 0.520, "model": "G7", "v0": 850},
    "Кастомний (Custom)": {"cal": 0.308, "len": 1.2, "weight": 175.0, "bc": 0.250, "model": "G7", "v0": 800}
}

st.set_page_config(page_title="Magelan242 Ultimate", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 10px; text-align: center; border-radius: 5px; margin-bottom: 20px;}
    .hud-card { background-color: #FFFFFF; border-left: 10px solid #C62828; padding: 15px; border-radius: 8px; text-align: center;}
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; text-transform: uppercase; }
    .hud-value { color: #000000; font-size: 26px; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНИЙ ОБЧИСЛЮВАЧ ---
def calculate(p, d):
    # Температурна корекція швидкості (0.2% на 1 градус від 15C)
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    v_dist = v0_eff * math.exp(-k * d)
    energy = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    # Траєкторія (Drop)
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2)
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    # Поправки
    w_rad = math.radians(p['wind_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (t - (d/v0_eff)))
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (d / 100)**2)
    
    v_mil = abs((y_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    h_mil = abs(((wind_drift + derivation) * 100) / (d / 10) / 0.1) if d > 0 else 0
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)
    
    return {"dist": d, "v_mil": v_mil, "h_mil": h_mil, "energy": energy, "vel": v_dist, "drop_cm": y_m*100, "sg": sg}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header"><h1>MAGELAN242 HUD PRO</h1></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📦 Набій")
    choice = st.selectbox("Вибрати набій:", list(AMMO_DB.keys()))
    base = AMMO_DB[choice]
    
    # РУЧНЕ РЕДАГУВАННЯ
    st.divider()
    m_v0 = st.number_input("V0 (м/с)", 100, 1500, base['v0'])
    m_bc = st.number_input("БК (G1/G7)", 0.01, 1.5, base['bc'], format="%.3f")
    m_weight = st.number_input("Вага (гран)", 1.0, 1000.0, base['weight'])
    m_len = st.number_input("Довжина кулі (дюйми)", 0.1, 3.5, base['len'], format="%.3f")
    m_cal = st.number_input("Калібр (дюйми)", 0.1, 0.6, base['cal'], format="%.3f")
    m_model = st.radio("Драг-модель", ["G7", "G1"], index=0 if base['model']=="G7" else 1)
    
    st.header("🔫 Ствол")
    m_twist = st.number_input("Твіст 1:", 5.0, 20.0, 10.0)
    m_side = st.radio("Нарізи:", ["Правобічні", "Лівобічні"])
    m_sh = st.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)

# ОСНОВНИЙ БЛОК
c1, c2, c3, c4 = st.columns(4)
target_d = c1.number_input("Дистанція (м)", 0, 4000, 800)
temp = c2.number_input("Темп (°C)", -50, 60, 15)
press = c3.number_input("Тиск (гПа)", 700, 1150, 1013)
w_speed = c4.number_input("Вітер (м/с)", 0.0, 30.0, 4.0)
w_hour = st.select_slider("Година вітру:", options=list(range(1, 13)), value=3)

# ОБЧИСЛЕННЯ
p = {'v0': m_v0, 'bc': m_bc, 'weight': m_weight, 'len': m_len, 'cal': m_cal, 'model': m_model,
     'twist': m_twist, 'twist_side': m_side, 'sh': m_sh, 'temp': temp, 'press': press, 
     'w_speed': w_speed, 'wind_hour': w_hour, 'zero': 100, 'angle': 0}

res = calculate(p, target_d)

# HUD
st.markdown("<br>", unsafe_allow_html=True)
h1, h2, h3, h4, h5 = st.columns(5)
h1.markdown(f'<div class="hud-card"><div class="hud-label">MIL Vertical</div><div class="hud-value">↑ {res["v_mil"]:.1f}</div></div>', unsafe_allow_html=True)
h2.markdown(f'<div class="hud-card"><div class="hud-label">MIL Horizontal</div><div class="hud-value">↔ {res["h_mil"]:.1f}</div></div>', unsafe_allow_html=True)
h3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{int(res["energy"])}</div></div>', unsafe_allow_html=True)
h4.markdown(f'<div class="hud-card"><div class="hud-label">V цілі (м/с)</div><div class="hud-value">{int(res["vel"])}</div></div>', unsafe_allow_html=True)
h5.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність</div><div class="hud-value">{res["sg"]:.2f}</div></div>', unsafe_allow_html=True)

# ГРАФІКИ
st.divider()
steps = np.arange(0, target_d + 201, 10)
df = pd.DataFrame([calculate(p, d) for d in steps])

fig = make_subplots(rows=2, cols=2, subplot_titles=("Падіння (см)", "MIL Поправки", "Енергія", "Швидкість"))
fig.add_trace(go.Scatter(x=df['dist'], y=df['drop_cm'], name="Drop", line=dict(color="red")), row=1, col=1)
fig.add_trace(go.Scatter(x=df['dist'], y=df['v_mil'], name="V-MIL", line=dict(color="yellow")), row=1, col=2)
fig.add_trace(go.Scatter(x=df['dist'], y=df['h_mil'], name="H-MIL", line=dict(color="blue", dash="dash")), row=1, col=2)
fig.add_trace(go.Scatter(x=df['dist'], y=df['energy'], name="Дж", line=dict(color="green")), row=2, col=1)
fig.add_trace(go.Scatter(x=df['dist'], y=df['vel'], name="м/с", line=dict(color="purple")), row=2, col=2)
fig.add_shape(type="line", x0=0, y0=340, x1=target_d+200, y1=340, line=dict(color="white", dash="dot"), row=2, col=2)

fig.update_layout(height=700, template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)
