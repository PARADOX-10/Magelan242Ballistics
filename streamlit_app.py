import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go

# --- НАЛАШТУВАННЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 PRO", layout="wide")

# --- СТИЛІЗАЦІЯ (ТЕМНА ТЕМА) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header { background-color: #C62828; padding: 10px; text-align: center; color: white; font-weight: bold; border-radius: 5px; }
    .hud-card { background-color: #FFFFFF; border-top: 5px solid #C62828; padding: 10px; text-align: center; border-radius: 4px; }
    .hud-label { color: #C62828; font-size: 11px; font-weight: bold; }
    .hud-value { color: #000000 !important; font-size: 28px !important; font-weight: 900 !important; }
    .stNumberInput label { color: #E0E0E0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНИЙ МОДУЛЬ ---
def ballistics_core(p):
    # Корекція швидкості від температури (спрощено)
    v0_eff = p['v0'] + (p['temp'] - 15) * 0.2
    # Щільність повітря
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * 0.91 # Коефіцієнт опору
    
    t = (math.exp(k * p['dist']) - 1) / (k * v0_eff) if p['dist'] > 0 else 0
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    
    # Вертикальне падіння (з врахуванням кута)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Ефект Коріоліса (Вертикаль)
    cor_v = 2 * v0_eff * 7.2921e-5 * math.cos(math.radians(p['lat'])) * math.sin(math.radians(p['azimuth'])) * t
    
    # Вітер та Деривація
    w_rad = math.radians(p['w_dir'])
    drift = (p['w_speed'] * math.sin(w_rad)) * (t - (p['dist']/v0_eff))
    derivation = 0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2
    
    # Результати в MRAD
    mrad_v = round(abs(((y_m + cor_v) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    mrad_h = round(abs(((drift + derivation) * 100) / (p['dist'] / 10) / 0.1), 1) if p['dist'] > 0 else 0.0
    
    return mrad_v, mrad_h, round(t, 3)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">MAGELAN242 : ПОВНИЙ РУЧНИЙ КОНТРОЛЬ</div>', unsafe_allow_html=True)

# ГРУПА 1: Бокова панель (Налаштування гвинтівки та набою)
with st.sidebar:
    st.subheader("🎯 Гвинтівка та Набій")
    v0 = st.number_input("Початкова швидкість (м/с)", 200, 1200, 825)
    bc = st.number_input("Баліст. коефіцієнт (G7)", 0.100, 1.000, 0.450, format="%.3f")
    weight = st.number_input("Вага кулі (гран)", 10.0, 500.0, 168.0)
    twist = st.number_input("Крок нарізів (Twist)", 7.0, 16.0, 10.0)
    sh = st.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)
    zero = st.number_input("Дистанція пристрілки (м)", 50, 500, 100)

# ГРУПА 2: Верхня панель (Атмосфера та Гео)
st.markdown("### ☁️ Атмосферні умови та Геопозиція")
at1, at2, at3, at4 = st.columns(4)
temp = at1.number_input("Темп. (°C)", -30, 50, 15)
press = at2.number_input("Тиск (гПа)", 800, 1100, 1013)
lat = at3.number_input("Широта (°)", -90.0, 90.0, 50.4)
azimuth = at4.number_input("Азимут стрільби (°)", 0, 360, 0)

# ГРУПА 3: Основні змінні (Дистанція, Вітер, Кут)
st.divider()
main_col1, main_col2, main_col3 = st.columns([1, 1, 1])

with main_col1:
    st.markdown("**ЦІЛЬ ТА КУТ**")
    dist = st.number_input("Дистанція (м)", 0, 3000, 500)
    angle = st.number_input("Кут місця цілі (°)", -60, 60, 0)

with main_col2:
    st.markdown("**ВІТЕР**")
    w_speed = st.number_input("Швидкість вітру (м/с)", 0.0, 30.0, 3.0)
    w_dir = st.slider("Напрямок вітру (°)", 0, 360, 90)

with main_col3:
    # Компас для візуалізації
    fig = go.Figure(go.Scatterpolar(r=[0, 1], theta=[w_dir, w_dir], mode='lines+markers', 
                                    marker=dict(symbol='arrow', size=12, color='#C62828'), line=dict(color='#C62828', width=4)))
    fig.update_layout(polar=dict(bgcolor='#1A1C24', angularaxis=dict(direction='clockwise', rotation=90)), 
                      showlegend=False, height=180, margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# --- РОЗРАХУНОК ТА ВИВІД ---
params = {
    'dist': dist, 'v0': v0, 'bc': bc, 'temp': temp, 'press': press, 
    'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle, 'zero': zero, 
    'sh': sh, 'twist': twist, 'lat': lat, 'azimuth': azimuth, 'weight': weight
}
res_v, res_h, res_t = ballistics_core(params)

st.markdown("<br>", unsafe_allow_html=True)
res_c1, res_c2, res_c3 = st.columns(3)

with res_c1:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ (КЛІКИ)</div><div class="hud-value">↑ {res_v}</div></div>', unsafe_allow_html=True)
with res_c2:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ГОР-ТАЛЬ (КЛІКИ)</div><div class="hud-value">↔ {res_h}</div></div>', unsafe_allow_html=True)
with res_c3:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС ПОЛЬОТУ (С)</div><div class="hud-value">{res_t}</div></div>', unsafe_allow_html=True)

# Кнопка для швидкої таблиці
if st.button("📊 ПОБУДУВАТИ ТАБЛИЦЮ ПОПРАВОК"):
    table_data = []
    for d in range(0, dist + 201, 50):
        params['dist'] = d
        v, h, _ = ballistics_core(params)
        table_data.append({"Дистанція": d, "Вертикаль": v, "Горизонталь": h})
    st.table(pd.DataFrame(table_data))
