import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

# Налаштування для мобільних пристроїв
st.set_page_config(
    page_title="Magelan242 PRO", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Стилізація для кращого вигляду на малих екранах
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    .stTable { font-size: 12px !important; }
    @media (max-width: 640px) {
        .main .block-container { padding: 1rem !important; }
        [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- БАЗА ПРОФІЛІВ ---
if 'profiles' not in st.session_state:
    st.session_state.profiles = {
        "Гвинтівка 1": {'v0': 825.0, 'weight': 168.0, 'bc': 0.450, 'model': "G7", 'sh': 5.0, 'twist': 10.0, 'zero': 100},
        "Гвинтівка 2": {'v0': 900.0, 'weight': 180.0, 'bc': 0.510, 'model': "G7", 'sh': 6.0, 'twist': 11.0, 'zero': 100}
    }

# --- МАТЕМАТИЧНЕ ЯДРО ---
def run_simulation(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    for d in range(0, p['max_dist'] + 1, 1):
        t = (math.exp(k_drag * d) - 1) / (k_drag * v0_corr) if d > 0 else 0
        drop = 0.5 * g * (t**2)
        t_zero = (math.exp(k_drag * p['zero_dist']) - 1) / (k_drag * v0_corr)
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        wind_rad = math.radians(p['w_dir'] * 30)
        wind_drift = (p['w_speed'] * math.sin(wind_rad)) * (t - (d/v0_corr)) if d > 0 else 0
        derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2 if d > 0 else 0
        
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy_curr = (weight_kg * v_curr**2) / 2
        mrad_v = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        if d % 5 == 0 or d == p['max_dist']:
            results.append({
                "Дистанція": d, "Час (с)": round(t, 3), 
                "Кліки (V)": round(abs(mrad_v / 0.1), 1), 
                "Кліки (H)": round(abs(mrad_h / 0.1), 1),
                "Швидкість": int(v_curr), "Енергія": int(energy_curr)
            })
    return pd.DataFrame(results), v0_corr

# --- SIDEBAR (ВСІ НАЛАШТУВАННЯ ТУТ) ---
st.sidebar.title("🛡️ Налаштування")
selected_p = st.sidebar.selectbox("🎯 Профіль:", list(st.session_state.profiles.keys()))
p_data = st.session_state.profiles[selected_p]

with st.sidebar.expander("🚀 Набій", expanded=False):
    v0 = st.number_input("V0 швидкість", 100.0, 1500.0, p_data['v0'])
    weight = st.number_input("Вага (гран)", 1.0, 1000.0, p_data['weight'])
    bc = st.number_input("BC", 0.01, 2.0, p_data['bc'], format="%.3f")
    model = st.selectbox("Модель", ["G7", "G1"])
    t_coeff = st.number_input("Термоз.", 0.0, 3.0, 0.2)

with st.sidebar.expander("🔭 Зброя", expanded=False):
    sh = st.number_input("Висота прицілу", 0.0, 30.0, p_data['sh'])
    zero_dist = st.number_input("Пристрілка", 1, 1000, p_data['zero'])
    twist = st.number_input("Твіст", 5.0, 25.0, p_data['twist'])

with st.sidebar.expander("🌍 Умови та Вітер", expanded=True):
    temp = st.number_input("Темп. (°C)", -40.0, 50.0, 15.0)
    press = st.number_input("Тиск (hPa)", 500, 1100, 1013)
    w_speed = st.number_input("Вітер (м/с)", 0.0, 30.0, 2.0)
    w_dir = st.slider("Напрямок (год)", 1, 12, 3)

max_d = st.sidebar.number_input("Макс. дистанція (м)", 100, 5000, 1000, step=100)

# --- ГОЛОВНИЙ ЕКРАН ---
st.header("🏹 Magelan242")

params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 'pressure': press, 
          'w_speed': w_speed, 'w_dir': w_dir, 'angle': 0, 'twist': twist, 'zero_dist': zero_dist, 
          'max_dist': max_d, 'sh': sh, 't_coeff': t_coeff}

try:
    df, v0_final = run_simulation(params)
    res = df.iloc[-1]

    # Метрики: на смартфоні вони стануть 2х2 або 4х1
    c1, c2 = st.columns(2)
    c1.metric("Кліки (V)", f"{res['Кліки (V)']}")
    c2.metric("Кліки (H)", f"{res['Кліки (H)']}")
    
    c3, c4 = st.columns(2)
    c3.metric("Час (с)", f"{res['Час (с)']}")
    c4.metric("V цілі (м/с)", f"{res['Швидкість']}")

    # Візуалізація вітру (компактна)
    with st.expander("🌀 Напрямок вітру"):
        wind_angle = w_dir * 30
        fig_wind = go.Figure(go.Scatterpolar(r=[0, 1], theta=[wind_angle, wind_angle], mode='lines+markers', marker=dict(symbol='arrow', size=15), line=dict(color='red', width=6)))
        fig_wind.update_layout(polar=dict(angularaxis=dict(tickvals=[0, 90, 180, 270], ticktext=['12', '3', '6', '9'], direction='clockwise')), height=200, margin=dict(l=40, r=40, t=20, b=20), template="plotly_dark")
        st.plotly_chart(fig_wind, use_container_width=True)

    # Таблиця
    st.subheader("📋 Таблиця")
    step = st.selectbox("Крок:", [10, 25, 50, 100], index=2)
    st.dataframe(df[df['Дистанція'] % step == 0], use_container_width=True)

except Exception as e:
    st.error(f"Помилка: {e}")
