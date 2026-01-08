import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 Ultimate", layout="wide")

# --- СТИЛІЗАЦІЯ (ТЕМНИЙ ТАКТИЧНИЙ ІНТЕРФЕЙС) ---
st.markdown("""
    <style>
    .stApp { background-color: #0A0C10; color: #E0E0E0; }
    .header { background-color: #C62828; padding: 15px; text-align: center; color: white; font-weight: 900; font-size: 24px; border-radius: 0 0 15px 15px; box-shadow: 0 4px 20px rgba(198, 40, 40, 0.4); }
    .hud-card { background-color: #FFFFFF; border-left: 8px solid #C62828; padding: 15px; text-align: center; border-radius: 6px; margin-bottom: 10px; }
    .hud-label { color: #C62828; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
    .hud-value { color: #000000 !important; font-size: 34px !important; font-weight: 900 !important; }
    .status-box { background-color: #161B22; border: 1px solid #30363D; padding: 15px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО (ПОВНА ФІЗИЧНА МОДЕЛЬ) ---
def advanced_simulation(p):
    # 1. Термозалежність швидкості
    v0_eff = p['v0'] * (1 + (p['temp'] - p['v0_temp']) * (p['v0_sens'] / 100))
    
    # 2. Атмосфера (Density Altitude & Speed of Sound)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    v_sound = 20.046 * math.sqrt(p['temp'] + 273.15)
    
    # 3. Фактор стабільності SG (Формула Міллера)
    m_grains = p['weight']
    d_inches = p['caliber']
    l_inches = p['bullet_len']
    t_inches = p['twist']
    # Спрощена формула Міллера
    sg = (30 * m_grains) / ( (t_inches/d_inches)**2 * d_inches**3 * l_inches * (1 + l_inches**2) ) * (v0_eff / 853.44)**(1/3)
    
    # 4. Моделювання траєкторії
    drag_m = 1.0 if p['model'] == "G1" else 0.91
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * drag_m
    
    steps = np.arange(0, p['max_d'] + 1, 10)
    results = []
    
    for d in steps:
        t = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
        v_curr = v0_eff * math.exp(-k * d)
        mach = v_curr / v_sound
        
        # Вертикаль (Гравітація + Кут)
        t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
        drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
        drop_z = 0.5 * 9.806 * (t_z**2)
        y_m_base = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
        
        # Аеродинамічний стрибок (AJ) та Вітер
        w_dir_rad = math.radians(p['wind_hour'] * 30)
        cross_w = p['w_speed'] * math.sin(w_dir_rad)
        twist_dir = 1 if p['twist_side'] == "Правий" else -1
        aj_shift = twist_dir * (cross_w * v0_eff * 0.000025 * (10/p['twist'])) * (t**2)
        
        # Деривація
        derivation = twist_dir * (0.05 * (p['twist'] / 10) * (d / 100)**2)
        wind_drift = (cross_w * (t - (d/v0_eff)))
        
        # Кліки (MRAD)
        v_mil = round(abs(((y_m_base + aj_shift) * 100) / (d / 10) / 0.1), 1) if d > 0 else 0
        h_mil = round(abs(((wind_drift + derivation) * 100) / (d / 10) / 0.1), 1) if d > 0 else 0
        
        results.append({
            "Range": d, "V_mil": v_mil, "H_mil": h_mil, "Velocity": v_curr, 
            "Mach": mach, "Energy": (m_grains * 0.0000648 * v_curr**2)/2, "Time": t, "Drop_cm": (y_m_base + aj_shift)*100
        })
    
    return pd.DataFrame(results), sg, v0_eff

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 HUD PRO : ULTIMATE EDITION</div>', unsafe_allow_html=True)

# СЛОВАЙДЕР ДЛЯ НАЛАШТУВАНЬ
with st.sidebar:
    st.header("⚙️ Гвинтівка")
    t_side = st.radio("Напрямок нарізів", ["Правий", "Лівий"], horizontal=True)
    t_twist = st.number_input("Твіст (дюйми)", 7.0, 16.0, 10.0)
    t_sh = st.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)
    t_zero = st.number_input("Пристрілка (м)", 50, 1000, 100)
    
    st.header("💊 Куля")
    t_cal = st.number_input("Калібр (дюйми)", 0.22, 0.50, 0.308, format="%.3f")
    t_len = st.number_input("Довжина кулі (дюйми)", 0.5, 2.5, 1.18)
    t_weight = st.number_input("Вага (гран)", 10.0, 700.0, 168.0)
    
    st.header("🔥 Порох (V0)")
    t_v0 = st.number_input("Базова V0 (м/с)", 200, 1500, 825)
    t_v0_t = st.number_input("При темп. (°C)", -20, 50, 15)
    t_v0_s = st.number_input("Термочутливість (%/1°C)", 0.0, 2.0, 0.2)

# ОСНОВНА ПАНЕЛЬ
c1, c2, c3, c4 = st.columns(4)
m_model = c1.selectbox("Drag Model", ["G7", "G1"])
m_bc = c2.number_input(f"BC ({m_model})", 0.1, 1.2, 0.450, format="%.3f")
m_temp = c3.number_input("Температура (°C)", -40, 60, 20)
m_press = c4.number_input("Тиск (гПа)", 700, 1100, 1013)

st.divider()

# ВІТЕР ТА ЦІЛЬ
col_w1, col_w2, col_w3 = st.columns([1, 1, 1.5])
with col_w1:
    m_dist = st.number_input("Дистанція (м)", 0, 4000, 800)
    m_angle = st.number_input("Кут цілі (°)", -70, 70, 0)
with col_w2:
    m_w_s = st.number_input("Вітер (м/с)", 0.0, 30.0, 4.0)
    m_w_h = st.select_slider("Годинник вітру", options=list(range(1, 13)), value=3)

# РОЗРАХУНОК
params = {
    'v0': t_v0, 'v0_temp': t_v0_t, 'v0_sens': t_v0_s, 'bc': m_bc, 'model': m_model,
    'temp': m_temp, 'press': m_press, 'w_speed': m_w_s, 'wind_hour': m_w_h,
    'angle': m_angle, 'zero': t_zero, 'sh': t_sh, 'twist': t_twist, 'twist_side': t_side,
    'weight': t_weight, 'caliber': t_cal, 'bullet_len': t_len, 'max_d': 2000
}
df, sg_val, v0_now = advanced_simulation(params)
current = df.iloc[m_dist//10] if m_dist <= 2000 else df.iloc[-1]

with col_w3:
    st.markdown('<div class="status-box">', unsafe_allow_html=True)
    st.write(f"🔹 Скоригована швидкість: **{v0_now:.1f} м/с**")
    color_sg = "green" if 1.4 <= sg_val <= 2.0 else "orange"
    st.markdown(f"🔹 Гіроскопічна стабільність (SG): <span style='color:{color_sg}; font-weight:bold;'>{sg_val:.2f}</span>", unsafe_allow_html=True)
    st.write(f"🔹 Дистанція дозвуку: **{df[df['Mach'] < 1.05]['Range'].min()} м**")
    st.markdown('</div>', unsafe_allow_html=True)

# ВИВІД КАРТОК
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4 = st.columns(4)
r1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ</div><div class="hud-value">↑ {current["V_mil"]}</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТАЛЬ</div><div class="hud-value">↔ {current["H_mil"]}</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">ЕНЕРГІЯ (Дж)</div><div class="hud-value">{int(current["Energy"])}</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС ПОЛЬОТУ</div><div class="hud-value">{current["Time"]:.3f}с</div></div>', unsafe_allow_html=True)

# ГРАФІКИ
st.divider()
fig = make_subplots(rows=2, cols=2, subplot_titles=("Траєкторія (см)", "Швидкість (Mach)", "Енергія (Дж)", "Поправки (MIL)"))

fig.add_trace(go.Scatter(x=df['Range'], y=df['Drop_cm'], name="Drop", line=dict(color='#C62828', width=3)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['Range'], y=df['Mach'], name="Mach", line=dict(color='#2196F3')), row=1, col=2)
fig.add_trace(go.Scatter(x=df['Range'], y=df['Energy'], name="Energy", fill='tozeroy', line=dict(color='#4CAF50')), row=2, col=1)
fig.add_trace(go.Scatter(x=df['Range'], y=df['V_mil'], name="V Поправка", line=dict(color='#FFEB3B')), row=2, col=2)

fig.update_layout(height=600, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
st.plotly_chart(fig, use_container_width=True)
