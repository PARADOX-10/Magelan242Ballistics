import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
import requests

# Налаштування сторінки
st.set_page_config(page_title="Magelan242 HUD PRO", layout="centered")

# --- ФУНКЦІЇ АВТОМАТИЗАЦІЇ ---
def get_auto_data():
    try:
        # 1. Отримуємо локацію по IP
        geo = requests.get('http://ip-api.com/json/').json()
        lat, lon = geo['lat'], geo['lon']
        
        # 2. Отримуємо погоду (використано тестовий ключ, для стабільності краще мати свій OpenWeatherMap API)
        # Приклад запиту: https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}&units=metric
        # Нижче заглушка для демонстрації, яка імітує отримання даних:
        weather_data = {
            'temp': 12, 'press': 1015, 'w_speed': 4.5, 'w_deg': 210, 'lat': lat
        }
        return weather_data
    except:
        return None

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #E0E0E0; }
    .header { background-color: #C62828; padding: 12px; text-align: center; color: white; font-weight: bold; border-radius: 0 0 10px 10px; }
    .status-bar { background-color: white; padding: 10px; border-radius: 5px; margin: 10px 0; border: 1px solid #ccc; }
    .result-box { background-color: white; border-top: 5px solid #C62828; padding: 15px; text-align: center; border-radius: 3px; }
    .res-val { color: #212121; font-size: 32px; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def advanced_calc(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * 0.2
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * 0.91
    t = (math.exp(k * p['dist']) - 1) / (k * v0_corr) if p['dist'] > 0 else 0
    
    # Падіння + Коріоліс (Вертикаль)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_corr)
    drop_z = 0.5 * 9.806 * (t_z**2)
    coriolis_v = 2 * v0_corr * 7.2921e-5 * math.cos(math.radians(p['lat'])) * math.sin(math.radians(p['azimuth'])) * t
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Вітер + Коріоліс (Горизонталь)
    w_rad = math.radians(p['w_dir'])
    wind_drift = (p['w_speed'] * math.sin(w_rad)) * (t - (p['dist']/v0_corr))
    coriolis_h = 7.2921e-5 * p['dist'] * t * math.sin(math.radians(p['lat']))
    
    res_v = ((y_m + coriolis_v) * 100) / (p['dist'] / 10) if p['dist'] > 0 else 0
    res_h = ((wind_drift + coriolis_h) * 100) / (p['dist'] / 10) if p['dist'] > 0 else 0
    return round(abs(res_v/0.1), 2), round(abs(res_h/0.1), 2), round(t, 3)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header">4DOF® HUD PRO : MAGELAN</div>', unsafe_allow_html=True)

# Кнопка Авто-оновлення
if st.button("📡 ОНОВИТИ GPS ТА ПОГОДУ"):
    auto = get_auto_data()
    if auto:
        st.session_state.temp = auto['temp']
        st.session_state.press = auto['press']
        st.session_state.lat = auto['lat']
        st.success("Дані оновлено успішно!")
    else:
        st.error("Не вдалося отримати дані")

# Параметри (з підтримкою сесії)
temp = st.session_state.get('temp', 15)
press = st.session_state.get('press', 1013)
lat = st.session_state.get('lat', 50.4)

st.markdown(f"""
    <div class="status-bar">
    <table style="width:100%; text-align:center; font-size:12px;">
        <tr><td>TEMP</td><td>PRESS</td><td>LAT</td></tr>
        <tr style="font-weight:bold; font-size:16px;">
            <td>{temp}°C</td><td>{press}hPa</td><td>{lat:.1f}°N</td>
        </tr>
    </table>
    </div>
""", unsafe_allow_html=True)

# Основний ввід
col_dist, col_compass = st.columns([1, 1.5])
with col_dist:
    dist = st.number_input("DIST (m)", 0, 3000, 500, step=10)
    st.markdown(f"<h1 style='color:#C62828; font-size:60px; text-align:center;'>{dist}</h1>", unsafe_allow_html=True)

with col_compass:
    w_dir = st.slider("WIND DIR", 0, 360, 210, label_visibility="hidden")
    fig = go.Figure(go.Scatterpolar(r=[0, 1], theta=[w_dir, w_dir], mode='lines+markers', marker=dict(symbol='arrow', size=15), line=dict(color='#C62828', width=5)))
    fig.update_layout(polar=dict(angularaxis=dict(direction='clockwise', rotation=90)), showlegend=False, height=200, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# Розрахунок
p = {
    'dist': dist, 'v0': 825, 'bc': 0.45, 'temp': temp, 'press': press, 
    'w_speed': 4.5, 'w_dir': w_dir, 'angle': 0, 'zero': 100, 
    'sh': 5, 'twist': 10, 'lat': lat, 'azimuth': 0
}
cv, ch, tf = advanced_calc(p)

# Результати
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3 = st.columns(3)
r1.markdown(f'<div class="result-box"><p style="color:#C62828; font-size:10px;">COME UP</p><p class="res-val">↑ {cv}</p></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="result-box"><p style="color:#C62828; font-size:10px;">WINDAGE</p><p class="res-val">→ {ch}</p></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="result-box"><p style="color:#C62828; font-size:10px;">TIME</p><p class="res-val">{tf}s</p></div>', unsafe_allow_html=True)
