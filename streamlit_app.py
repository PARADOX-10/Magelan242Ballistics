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
    /* Стилізація слайдера */
    .stSlider label { color: #E0E0E0 !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНИЙ МОДУЛЬ ---
def ballistics_core(p):
    v0_eff = p['v0'] + (p['temp'] - 15) * 0.2
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    
    # Вибір драг-моделі
    drag_coeff = 1.0 if p['model'] == "G1" else 0.91
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * drag_coeff
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    
    # Вертикаль (Падіння кулі)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Горизонталь (Вітер та Деривація)
    # Перерахунок годинника вітру в градуси (12 год = 0°, 3 год = 90° і т.д.)
    w_dir_deg = p['wind_hour'] * 30
    w_rad = math.radians(w_dir_deg)
    
    # Розрахунок дрейфу вітру
    wind_drift = (p['w_speed'] * math.sin(w_rad)) * (t - (p['dist']/v0_eff))
    derivation = 0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2
    
    # Результати в MRAD (кліки 0.1)
    res_v = round(abs(((y_m) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    res_h = round(abs(((wind_drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    
    return res_v, res_h, round(t, 3), w_dir_deg

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : ВІТЕР ЗА ГОДИННИКОМ</div>', unsafe_allow_html=True)

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

# Атмосфера
c1, c2, c3 = st.columns(3)
temp = c1.number_input("Темп. (°C)", -30, 50, 15)
press = c2.number_input("Тиск (гПа)", 800, 1100, 1013)
dist = c3.number_input("Дистанція (м)", 0, 3000, 500)

st.divider()

# СЕКЦІЯ ВІТРУ (ГОДИННИК)
m1, m2, m3 = st.columns([1, 1, 1])

with m1:
    st.markdown("### 🌀 Параметри вітру")
    w_speed = st.number_input("Швидкість вітру (м/с)", 0.0, 25.0, 2.0)
    wind_hour = st.select_slider(
        "Напрямок вітру (Год)",
        options=[12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        value=3
    )
    angle = st.number_input("Кут місця цілі (°)", -60, 60, 0)

with m2:
    # Розрахунок для візуалізації
    temp_dir = wind_hour * 30
    # Візуалізація вітру на компасі
    fig = go.Figure(go.Scatterpolar(
        r=[0, 1], 
        theta=[temp_dir, temp_dir], 
        mode='lines+markers', 
        marker=dict(symbol='arrow', size=15, color='#C62828'), 
        line=dict(color='#C62828', width=6)
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='#1A1C24', 
            angularaxis=dict(direction='clockwise', rotation=90, tickvals=[0, 90, 180, 270], ticktext=['12', '3', '6', '9'])
        ), 
        showlegend=False, height=250, margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True)

with m3:
    st.markdown("### ℹ️ Підказка")
    st.write(f"Вибрано напрямок: **{wind_hour} година**")
    if wind_hour in [12, 6]: st.info("Поздовжній вітер: впливає переважно на вертикаль.")
    elif wind_hour in [3, 9]: st.info("Повний боковий вітер: максимальне горизонтальне відхилення.")
    else: st.info("Косий вітер: впливає на обидві осі.")

# РОЗРАХУНОК
params = {
    'dist': dist, 'v0': v0, 'bc': bc, 'model': model, 'temp': temp, 'press': press, 
    'w_speed': w_speed, 'wind_hour': wind_hour, 'angle': angle, 'zero': zero, 
    'sh': sh, 'twist': twist, 'weight': weight
}
res_v, res_h, res_t, _ = ballistics_core(params)

# ВИВІД РЕЗУЛЬТАТІВ
st.markdown("<br>", unsafe_allow_html=True)
res_c1, res_c2, res_c3 = st.columns(3)

with res_c1:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ (КЛІКИ)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
with res_c2:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ГОР-ТАЛЬ (КЛІКИ)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
with res_c3:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС ПОЛЬОТУ</div><div class="hud-value">{res_t}с</div></div>', unsafe_allow_html=True)
