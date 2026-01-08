import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
import requests

# Налаштування сторінки
st.set_page_config(page_title="Magelan242 HUD PRO", layout="centered")

# --- СТИЛІЗАЦІЯ (ВИСОКИЙ КОНТРАСТ) ---
st.markdown("""
    <style>
    /* Головний фон - світло-сірий для відсутності бліків */
    .stApp { background-color: #E8E8E8; }
    
    /* Хедер */
    .header { 
        background-color: #C62828; padding: 15px; text-align: center; 
        color: white; font-weight: bold; font-size: 22px; 
        border-radius: 0 0 15px 15px; margin-bottom: 10px;
    }
    
    /* Панель статусів */
    .status-bar { 
        background-color: #FFFFFF; padding: 12px; border-radius: 8px; 
        border: 2px solid #C62828; margin-bottom: 15px;
    }
    .status-label { font-size: 11px; color: #555; font-weight: bold; text-transform: uppercase; }
    .status-val { font-size: 16px; font-weight: bold; color: #000; }

    /* Картки результатів (Нижні) */
    .result-box { 
        background-color: #FFFFFF; border-top: 6px solid #C62828; 
        padding: 15px; text-align: center; border-radius: 5px; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .res-lab { color: #C62828; font-size: 13px; font-weight: bold; margin-bottom: 8px; }
    .res-val { color: #000000; font-size: 34px; font-weight: 900; }

    /* Текст у віджетах Streamlit */
    label, p, span { color: #000000 !important; font-weight: 600 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНІ РОЗРАХУНКИ ---
def advanced_calc(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * 0.2
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * 0.91
    t = (math.exp(k * p['dist']) - 1) / (k * v0_corr) if p['dist'] > 0 else 0
    
    # Вертикаль (Падіння + Коріоліс)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_corr)
    drop_z = 0.5 * 9.806 * (t_z**2)
    cor_v = 2 * v0_corr * 7.2921e-5 * math.cos(math.radians(p['lat'])) * math.sin(math.radians(p['azimuth'])) * t
    y_m = -(drop - (drop_z + p['sh']/100) * (p['dist'] / p['zero']) + p['sh']/100)
    
    # Горизонталь (Вітер + Деривація + Коріоліс)
    w_rad = math.radians(p['w_dir'])
    wind_drift = (p['w_speed'] * math.sin(w_rad)) * (t - (p['dist']/v0_corr))
    derivation = 0.05 * (p['twist'] / 10) * (p['dist'] / 100)**2
    cor_h = 7.2921e-5 * p['dist'] * t * math.sin(math.radians(p['lat']))
    
    res_v = ((y_m + cor_v) * 100) / (p['dist'] / 10) if p['dist'] > 0 else 0
    res_h = ((wind_drift + derivation + cor_h) * 100) / (p['dist'] / 10) if p['dist'] > 0 else 0
    return round(abs(res_v/0.1), 2), round(abs(res_h/0.1), 2), round(t, 3)

# --- ГОЛОВНИЙ ЕКРАН ---
st.markdown('<div class="header">MAGELAN242 HUD PRO</div>', unsafe_allow_html=True)

# Авто-дані
if st.button("📡 ОНОВИТИ GPS ТА ПОГОДУ"):
    try:
        geo = requests.get('http://ip-api.com/json/').json()
        st.session_state.lat = geo['lat']
        st.session_state.temp = 15 # Заглушка, потребує API Key для OpenWeather
        st.session_state.press = 1013
        st.success("Дані оновлено!")
    except:
        st.error("Помилка зв'язку")

# Панель статусів
st.markdown(f"""
    <div class="status-bar">
    <table style="width:100%; text-align:center;">
        <tr>
            <td><p class="status-label">Темп.</p><p class="status-val">{st.session_state.get('temp', 15)}°C</p></td>
            <td><p class="status-label">Тиск</p><p class="status-val">{st.session_state.get('press', 1013)} гПа</p></td>
            <td><p class="status-label">Широта</p><p class="status-val">{st.session_state.get('lat', 50.4):.1f}°</p></td>
        </tr>
    </table>
    </div>
""", unsafe_allow_html=True)

# Основний ввід
col_d, col_c = st.columns([1, 1.3])
with col_d:
    st.write("🎯 **ДИСТАНЦІЯ**")
    dist = st.number_input("", 0, 3000, 486, step=1, label_visibility="collapsed")
    st.markdown(f"<div style='border-left:5px solid #C62828; padding-left:10px;'><h1 style='color:#000; font-size:65px; margin:0;'>{dist}</h1><p style='color:#C62828;'>METERS</p></div>", unsafe_allow_html=True)

with col_c:
    st.write("🌀 **ВІТЕР (НАПРЯМОК)**")
    w_dir = st.slider("", 0, 360, 326, label_visibility="collapsed")
    fig = go.Figure(go.Scatterpolar(r=[0, 1], theta=[w_dir, w_dir], mode='lines+markers', marker=dict(symbol='arrow', size=15), line=dict(color='#C62828', width=6)))
    fig.update_layout(polar=dict(angularaxis=dict(direction='clockwise', rotation=90, tickfont=dict(color="black"))), showlegend=False, height=220, margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# Розрахунок
p = {
    'dist': dist, 'v0': 825, 'bc': 0.45, 'temp': st.session_state.get('temp', 15), 
    'press': st.session_state.get('press', 1013), 'w_speed': 5, 'w_dir': w_dir, 
    'angle': 0, 'zero': 100, 'sh': 5, 'twist': 10, 'lat': st.session_state.get('lat', 50.4), 'azimuth': 0
}
cv, ch, tf = advanced_calc(p)

# Результати
st.markdown("<br>", unsafe_allow_html=True)
res1, res2, res3 = st.columns(3)
res1.markdown(f'<div class="result-box"><p class="res-lab">ВЕРТИКАЛЬ</p><p class="res-val">↑{cv}</p></div>', unsafe_allow_html=True)
res2.markdown(f'<div class="result-box"><p class="res-lab">ВІТЕР</p><p class="res-val">→{ch}</p></div>', unsafe_allow_html=True)
res3.markdown(f'<div class="result-box"><p class="res-lab">ЧАС (с)</p><p class="res-val">{tf}</p></div>', unsafe_allow_html=True)

# Кнопка налаштувань
st.markdown("<br>", unsafe_allow_html=True)
if st.button("⚙️ РЕДАГУВАТИ ПРОФІЛЬ ЗБРОЇ"):
    st.sidebar.header("Налаштування")
    p['v0'] = st.sidebar.number_input("Швидкість V0", 100, 1200, 825)
    p['bc'] = st.sidebar.number_input("Коефіцієнт BC", 0.1, 1.0, 0.45)
    p['sh'] = st.sidebar.number_input("Висота прицілу (см)", 0, 20, 5)
