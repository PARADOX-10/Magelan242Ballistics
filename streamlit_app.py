import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go

# --- НАЛАШТУВАННЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 PRO", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 10px; text-align: center; color: white; font-weight: bold; border-radius: 5px; margin-bottom: 20px;}
    .hud-card { background-color: #FFFFFF; border-top: 5px solid #C62828; padding: 10px; text-align: center; border-radius: 4px; }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; }
    .hud-value { color: #000000 !important; font-size: 30px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНИЙ МОДУЛЬ ---
def ballistics_core(p):
    v0_eff = p['v0'] + (p['temp'] - 15) * 0.2
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    
    # Вибір драг-моделі
    # G1 використовується для "тупоносих" куль, G7 - для далекобійних "човнохвостих"
    drag_coeff = 1.0 if p['model'] == "G1" else 0.91
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * drag_coeff
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    
    # Вертикаль
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    
    # Перерахунок годинника стрільби в азимут (12 год = 0°, 3 год = 90° і т.д.)
    az_deg = p['shot_hour'] * 30
    cor_v = 2 * v0_eff * 7.2921e-5 * math.cos(math.radians(p['lat'])) * math.sin(math.radians(az_deg)) * t
    
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Горизонталь
    w_rad = math.radians(p['w_dir'])
    wind_drift = (p['w_speed'] * math.sin(w_rad)) * (t - (p['dist']/v0_eff))
    derivation = 0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2
    
    res_v = round(abs(((y_m + cor_v) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    res_h = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    
    return res_v, res_h, round(t, 3)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : G1/G7 ТА НАПРЯМОК СТРІЛЬБИ</div>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🚀 Параметри Набою")
    model = st.radio("Драг-модель", ["G7", "G1"], horizontal=True)
    v0 = st.number_input("Швидкість V0 (м/с)", 200, 1200, 825)
    bc = st.number_input(f"Коефіцієнт BC ({model})", 0.100, 1.200, 0.450, format="%.3f")
    weight = st.number_input("Вага кулі (гран)", 10.0, 500.0, 168.0)
    twist = st.number_input("Твіст ствола", 7.0, 16.0, 10.0)
    st.divider()
    sh = st.number_input("Висота оптики (см)", 0.0, 15.0, 5.0)
    zero = st.number_input("Пристрілка (м)", 50, 500, 100)

# Атмосфера та Напрямок стрільби
c1, c2, c3 = st.columns(3)
temp = c1.number_input("Темп. (°C)", -30, 50, 15)
press = c2.number_input("Тиск (гПа)", 800, 1100, 1013)
# Заміна азимуту на годинник
shot_hour = c3.selectbox("Напрямок стрільби (Год)", options=list(range(1, 13)), index=11) # За замовчуванням 12 (Північ)

# Основні дані
st.divider()
m1, m2, m3 = st.columns([1, 1, 1])

with m1:
    dist = st.number_input("Дистанція до цілі (м)", 0, 3000, 500)
    angle = st.number_input("Кут місця цілі (°)", -60, 60, 0)

with m2:
    w_speed = st.number_input("Вітер (м/с)", 0.0, 25.0, 2.0)
    w_dir = st.slider("Напрямок вітру (град)", 0, 360, 90)

with m3:
    # Візуалізація напрямку
    fig = go.Figure(go.Scatterpolar(r=[0, 1], theta=[w_dir, w_dir], mode='lines+markers', 
                                    marker=dict(symbol='arrow', size=10, color='#C62828'), line=dict(color='#C62828', width=4)))
    fig.update_layout(polar=dict(bgcolor='#1A1C24', angularaxis=dict(direction='clockwise', rotation=90)), 
                      showlegend=False, height=180, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# РОЗРАХУНОК
params = {
    'dist': dist, 'v0': v0, 'bc': bc, 'model': model, 'temp': temp, 'press': press, 
    'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle, 'zero': zero, 
    'sh': sh, 'twist': twist, 'lat': 50.4, 'shot_hour': shot_hour, 'weight': weight
}
res_v, res_h, res_t = ballistics_core(params)

# ВИВІД РЕЗУЛЬТАТІВ
st.markdown("<br>", unsafe_allow_html=True)
res_c1, res_c2, res_c3 = st.columns(3)

with res_c1:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ (КЛІКИ)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
with res_c2:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ГОР-ТАЛЬ (КЛІКИ)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
with res_c3:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС ПОЛЬОТУ</div><div class="hud-value">{res_t}с</div></div>', unsafe_allow_html=True)
