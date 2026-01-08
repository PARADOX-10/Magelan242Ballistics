import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# Конфігурація
st.set_page_config(page_title="Magelan242 Ballistics", layout="wide")

# Стилізація для друку та інтерфейсу
st.markdown("""
    <style>
    @media print {
        .stButton, .stTabs, .stSidebar, .stSelectbox, .stSlider { display: none !important; }
        .main { background-color: white !important; color: black !important; }
    }
    .metric-card { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #00FF00; }
    </style>
    """, unsafe_allow_html=True)

def run_simulation(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    angle_rad = math.radians(p['angle'])

    for d in range(0, p['max_dist'] + 1, 1):
        t = d / (v0_corr * math.exp(-k_drag * d / 2)) if d > 0 else 0
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        t_zero = p['zero_dist'] / (v0_corr * math.exp(-k_drag * p['zero_dist'] / 2))
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        wind_rad = math.radians(p['w_dir'] * 30)
        wind_drift = (p['w_speed'] * math.sin(wind_rad)) * (t - (d/v0_corr)) if d > 0 else 0
        derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2 if d > 0 else 0
        
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy = (weight_kg * v_curr**2) / 2
        
        mrad_v = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        if d % 5 == 0 or d == p['max_dist']:
            results.append({
                "Дистанція": d,
                "Падіння (см)": round(y_m * 100, 1),
                "Кліки (V)": round(abs(mrad_v / 0.1), 1),
                "Кліки (H)": round(abs(mrad_h / 0.1), 1),
                "Швидкість": round(v_curr, 1),
                "Енергія": int(energy)
            })
    return pd.DataFrame(results), v0_corr

# --- БОКОВЕ МЕНЮ ---
st.sidebar.title("🛡️ Magelan242 Ballistics")
tab_1, tab_2, tab_3 = st.sidebar.tabs(["🚀 Набій", "🔭 Зброя", "🌍 Умови"])

with tab_1:
    v0 = st.number_input("Початкова швидкість (м/с)", 200.0, 1500.0, 961.0)
    weight = st.number_input("Вага кулі (гран)", 1.0, 1000.0, 200.0)
    input_energy = st.number_input("Енергія набою (Дж)", value=int((weight * 0.0000647989 * v0**2) / 2))
    bc = st.number_input("Балістичний коефіцієнт BC", 0.01, 2.0, 0.395, format="%.3f")
    model = st.selectbox("Модель опору", ["G1", "G7"])
    t_coeff = st.number_input("Термозалежність (м/с на 1°C)", 0.0, 2.0, 0.2)

with tab_2:
    sh = st.number_input("Висота прицілу (см)", 0.0, 30.0, 5.0)
    zero_dist = st.number_input("Пристрілка (м)", 1, 1000, 300)
    twist = st.number_input("Твіст", 5.0, 20.0, 11.0)

with tab_3:
    temp = st.slider("Температура (°C)", -40, 60, 15)
    press = st.number_input("Атмосферний тиск (hPa)", 500, 1100, 1013)
    w_speed = st.slider("Швидкість вітру (м/с)", 0.0, 30.0, 0.0)
    w_dir = st.slider("Напрям вітру (год)", 1, 12, 12)
    max_d = st.number_input("Дистанція пострілу (м)", 10, 5000, 1200)
    angle = st.slider("Кут пострілу (°)", -80, 80, 0)

# Розрахунок
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': max_d, 'sh': sh, 't_coeff': t_coeff}

try:
    df, v0_final = run_simulation(params)
    res = df.iloc[-1]

    st.title("🏹 Magelan242 Ballistics")
    
    # Метрики
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Початкова швидкість", f"{v0_final:.1f} м/с")
    c2.metric("Кліки (Вертикаль)", int(res['Кліки (V)']))
    c3.metric("Кліки (Горизонталь)", int(res['Кліки (H)']))
    c4.metric("Швидкість у цілі", f"{res['Швидкість']} м/с")

    # Вкладки: Графіки / Картка для друку
    tab_graphs, tab_print = st.tabs(["📊 Аналітичні Графіки", "🖨️ Картка для друку (Print Card)"])

    with tab_graphs:
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Траєкторія", "Енергія"))
        fig.add_trace(go.Scatter(x=df['Дистанція'], y=df['Падіння (см)'], fill='tozeroy', name="см", line=dict(color='lime')), 1, 1)
        fig.add_trace(go.Scatter(x=df['Дистанція'], y=df['Енергія'], fill='tozeroy', name="Дж", line=dict(color='red')), 1, 2)
        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tab_print:
        st.subheader("📋 Компактна картка вогню")
        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            st.write(f"**V0:** {v0_final:.1f} м/с | **BC:** {bc} ({model})")
            st.write(f"**T:** {temp}°C | **P:** {press} hPa | **Вітер:** {w_speed} м/с на {w_dir} год")
        
        print_step = st.selectbox("Крок для друку:", [25, 50, 100, 200], index=2)
        print_df = df[df['Дистанція'] % print_step == 0][['Дистанція', 'Кліки (V)', 'Кліки (H)', 'Швидкість', 'Енергія']]
        
        # Стилізація таблиці для друку
        st.table(print_df.style.format(precision=1))
        st.caption("Примітка: 1 клік = 0.1 MRAD (1 см / 100 м)")

except Exception as e:
    st.error(f"Помилка: {e}")
