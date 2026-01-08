import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- РОЗШИРЕНА БАЗА МОДИФІКАЦІЙ НАБОЇВ ---
AMMO_EXTENDED_DB = {
    "5.45x39 7N6 (PS)": {"cal": 0.214, "len": 0.98, "weight": 53.0, "bc": 0.168, "model": "G7", "v0": 880},
    "5.45x39 7N10 (PP)": {"cal": 0.214, "len": 0.98, "weight": 56.0, "bc": 0.172, "model": "G7", "v0": 870},
    "5.56x45 M193 (55gr)": {"cal": 0.224, "len": 0.74, "weight": 55.0, "bc": 0.122, "model": "G7", "v0": 990},
    "5.56x45 M855 (SS109)": {"cal": 0.224, "len": 0.91, "weight": 62.0, "bc": 0.151, "model": "G7", "v0": 915},
    "5.56x45 MK262 (77gr)": {"cal": 0.224, "len": 0.99, "weight": 77.0, "bc": 0.190, "model": "G7", "v0": 840},
    "7.62x39 M43 (123gr)": {"cal": 0.311, "len": 0.93, "weight": 123.0, "bc": 0.145, "model": "G7", "v0": 715},
    "7.62x51 M80 (147gr)": {"cal": 0.308, "len": 1.12, "weight": 147.0, "bc": 0.195, "model": "G7", "v0": 850},
    "7.62x51 M118LR (175gr)": {"cal": 0.308, "len": 1.24, "weight": 175.0, "bc": 0.243, "model": "G7", "v0": 790},
    "7.62x54R LPS (148gr)": {"cal": 0.311, "len": 1.15, "weight": 148.0, "bc": 0.185, "model": "G7", "v0": 830},
    "7.62x54R 7N1 (Sniper)": {"cal": 0.311, "len": 1.25, "weight": 151.0, "bc": 0.215, "model": "G7", "v0": 825},
    "6.5 Creedmoor ELD-M 140gr": {"cal": 0.264, "len": 1.35, "weight": 140.0, "bc": 0.315, "model": "G7", "v0": 825},
    "6.5 Creedmoor ELD-M 147gr": {"cal": 0.264, "len": 1.43, "weight": 147.0, "bc": 0.351, "model": "G7", "v0": 810},
    ".300 Win Mag Berger 215gr": {"cal": 0.308, "len": 1.60, "weight": 215.0, "bc": 0.354, "model": "G7", "v0": 870},
    ".338 LM Scenar 250gr": {"cal": 0.338, "len": 1.62, "weight": 250.0, "bc": 0.310, "model": "G7", "v0": 900},
    ".338 LM Scenar 300gr": {"cal": 0.338, "len": 1.78, "weight": 300.0, "bc": 0.368, "model": "G7", "v0": 825},
    ".375 CheyTac 350gr Solid": {"cal": 0.375, "len": 2.05, "weight": 350.0, "bc": 0.405, "model": "G7", "v0": 930},
    ".408 CheyTac 419gr Solid": {"cal": 0.408, "len": 2.15, "weight": 419.0, "bc": 0.450, "model": "G7", "v0": 885},
    ".50 BMG M2 Ball (706gr)": {"cal": 0.510, "len": 2.30, "weight": 706.0, "bc": 0.470, "model": "G7", "v0": 890},
    ".50 BMG A-MAX (750gr)": {"cal": 0.510, "len": 2.31, "weight": 750.0, "bc": 0.520, "model": "G7", "v0": 850},
    "Ручне введення (Custom)": {"cal": 0.308, "len": 1.0, "weight": 150.0, "bc": 0.200, "model": "G7", "v0": 800}
}

st.set_page_config(page_title="Magelan242 Ultimate", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 10px; text-align: center; font-weight: 900; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(198,40,40,0.4);}
    .sidebar-label { color: #C62828; font-weight: bold; margin-top: 15px; border-bottom: 1px solid #333; }
    .hud-card { background-color: #FFFFFF; border-left: 10px solid #C62828; padding: 15px; text-align: center; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 26px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_ballistics(p, target_dist):
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t = (math.exp(k * target_dist) - 1) / (k * v0_eff) if target_dist > 0 else 0
    v_dist = v0_eff * math.exp(-k * target_dist)
    energy = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    # Траєкторія
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (target_dist / p['zero']) + p['sh']/100)
    
    # Вітер та Деривація
    w_rad = math.radians(p['wind_hour'] * 30)
    cross_w = p['w_speed'] * math.sin(w_rad)
    twist_dir = 1 if p['twist_side'] == "Правобічні" else -1
    
    wind_drift = (cross_w * (t - (target_dist/v0_eff)))
    derivation = twist_dir * (0.05 * (p['twist'] / 10) * (target_dist / 100)**2)
    
    v_mil = round(abs(((y_m) * 100) / (target_dist / 10) / 0.1), 1) if target_dist > 0 else 0.0
    h_mil = round(abs(((wind_drift + derivation) * 100) / (target_dist / 10) / 0.1), 1) if target_dist > 0 else 0.0
    sg = (30 * p['weight']) / ( (p['twist']/p['cal'])**2 * p['cal']**3 * p['len'] * (1 + p['len']**2) ) * (v0_eff / 853.44)**(1/3)
    
    return v_mil, h_mil, round(t, 3), int(energy), round(v_dist, 1), round(sg, 2), y_m*100

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : ULTIMATE AMMO LABORATORY</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-label">📦 ВИБІР ТИПУ НАБОЮ</div>', unsafe_allow_html=True)
    choice = st.selectbox("База модифікацій:", list(AMMO_EXTENDED_DB.keys()))
    base = AMMO_EXTENDED_DB[choice]
    
    st.markdown('<div class="sidebar-label">📏 ГЕОМЕТРІЯ (РУЧНЕ РЕДАГУВАННЯ)</div>', unsafe_allow_html=True)
    m_cal = st.number_input("Діаметр (дюйми)", 0.100, 0.600, base['cal'], format="%.3f")
    m_len = st.number_input("Довжина кулі (дюйми)", 0.200, 3.500, base['len'], format="%.3f")
    m_weight = st.number_input("Вага (гран)", 1.0, 1000.0, base['weight'])
    
    st.markdown('<div class="sidebar-label">🚀 БАЛІСТИКА ТА V0</div>', unsafe_allow_html=True)
    m_v0 = st.number_input("Швидкість V0 (м/с)", 100, 1500, base['v0'])
    m_bc = st.number_input("Коефіцієнт (BC)", 0.01, 1.5, base['bc'], format="%.3f")
    m_model = st.radio("Драг-модель", ["G7", "G1"], index=0 if base['model']=="G7" else 1, horizontal=True)
    
    st.markdown('<div class="sidebar-label">🔫 ПАРАМЕТРИ ЗБРОЇ</div>', unsafe_allow_html=True)
    m_twist = st.number_input("Твіст ствола 1:", 5.0, 24.0, 10.0)
    m_side = st.radio("Нарізи", ["Правобічні", "Лівобічні"], horizontal=True)
    m_sh = st.number_input("Висота прицілу (см)", 0.0, 20.0, 5.0)

# ПАНЕЛЬ УМОВ
c1, c2, c3, c4 = st.columns(4)
target_d = c1.number_input("Ціль (метри)", 0, 4000, 500, step=10)
temp = c2.number_input("Температура (°C)", -50, 60, 15)
press = c3.number_input("Тиск (гПа)", 700, 1150, 1013)
w_speed = c4.number_input("Вітер (м/с)", 0.0, 40.0, 5.0)

w_hour = st.select_slider("Напрямок вітру (година)", options=list(range(1, 13)), value=3)

# РОЗРАХУНОК
p = {
    'cal': m_cal, 'len': m_len, 'weight': m_weight, 'v0': m_v0, 'bc': m_bc, 
    'model': m_model, 'twist': m_twist, 'twist_side': m_side, 'sh': m_sh, 
    'temp': temp, 'press': press, 'w_speed': w_speed, 'wind_hour': w_hour, 
    'angle': 0, 'zero': 100
}

res_v, res_h, res_t, res_e, res_v_d, res_sg, _ = calculate_ballistics(p, target_d)

# КАРТКИ HUD
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f'<div class="hud-card"><div class="hud-label">MIL Vertical</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">MIL Horizontal</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">Енергія (Дж)</div><div class="hud-value">{res_e}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість (м/с)</div><div class="hud-value">{int(res_v_d)}</div></div>', unsafe_allow_html=True)
r5.markdown(f'<div class="hud-card"><div class="hud-label">Стабільність SG</div><div class="hud-value">{res_sg}</div></div>', unsafe_allow_html=True)

# ГРАФІЧНИЙ БЛОК
st.divider()
st.subheader("📊 Повний балістичний аналіз")

steps = np.arange(0, target_d + 501, 10)
data = [calculate_ballistics(p, d) for d in steps]
df = pd.DataFrame(data, columns=['v_mil', 'h_mil', 'time', 'energy', 'velocity', 'sg', 'drop_cm'])
df['dist'] = steps

fig = make_subplots(rows=2, cols=2, 
                    subplot_titles=("Падіння кулі (см)", "Поправки (MIL)", "Втрата Енергії (Дж)", "Графік швидкості (м/с)"))

fig.add_trace(go.Scatter(x=df['dist'], y=df['drop_cm'], name="Drop", line=dict(color='#C62828', width=3)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['dist'], y=df['v_mil'], name="V-MIL", line=dict(color='#FFD700')), row=1, col=2)
fig.add_trace(go.Scatter(x=df['dist'], y=df['h_mil'], name="H-MIL", line=dict(color='#00BFFF', dash='dash')), row=1, col=2)
fig.add_trace(go.Scatter(x=df['dist'], y=df['energy'], name="Дж", fill='tozeroy', line=dict(color='#4CAF50')), row=2, col=1)
fig.add_trace(go.Scatter(x=df['dist'], y=df['velocity'], name="м/с", line=dict(color='#9C27B0')), row=2, col=2)
# Поріг звуку
fig.add_shape(type="line", x0=0, y0=340, x1=target_d+500, y1=340, line=dict(color="white", dash="dot"), row=2, col=2)

fig.update_layout(height=800, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)

if st.checkbox("Показати таблицю даних"):
    st.dataframe(df[['dist', 'v_mil', 'h_mil', 'energy', 'velocity', 'sg']].iloc[::5], use_container_width=True)
