import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# Конфігурація
st.set_page_config(page_title="Magelan242 Ballistics Pro", layout="wide")

# Стилізація інтерфейсу та кнопок
st.markdown("""
    <style>
    @media print {
        .stButton, .stTabs, .stSidebar, .stSelectbox, .stSlider { display: none !important; }
        .main { background-color: white !important; color: black !important; }
    }
    .stButton>button { width: 100%; font-size: 24px; font-weight: bold; height: 3.5rem; border-radius: 10px; }
    .metric-card { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #00FF00; text-align: center; }
    .status-safe { color: #00FF00; font-weight: bold; }
    .status-warn { color: #FFA500; font-weight: bold; }
    .status-danger { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Ініціалізація значень у Session State для кнопок
if 'dist_val' not in st.session_state: st.session_state.dist_val = 800
if 'wind_val' not in st.session_state: st.session_state.wind_val = 0.0

def run_simulation(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    vsound = 331.3 * math.sqrt(tk / 273.15)
    
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    angle_rad = math.radians(p['angle'])

    # Розрахунок траєкторії
    for d in range(0, 2001, 1): # Рахуємо до 2км для аналізу зон
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
        mach = v_curr / vsound
        
        mrad_v = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        if d % 5 == 0:
            results.append({
                "Дистанція": d,
                "Падіння_см": round(y_m * 100, 1),
                "Кліки_V": round(abs(mrad_v / 0.1), 1),
                "Кліки_H": round(abs(mrad_h / 0.1), 1),
                "Швидкість": v_curr,
                "Енергія": int(energy),
                "Мах": mach
            })
    return pd.DataFrame(results), v0_corr, vsound

# --- БОКОВЕ МЕНЮ ---
st.sidebar.title("🛡️ Magelan242 Ballistics")
tab_1, tab_2, tab_3 = st.sidebar.tabs(["🚀 Набій", "🔭 Зброя", "🌍 Умови"])

with tab_1:
    v0 = st.number_input("Початкова швидкість (м/с)", 200.0, 1500.0, 830.0)
    weight = st.number_input("Вага кулі (гран)", 1.0, 1000.0, 175.0)
    bc = st.number_input("Балістичний коефіцієнт BC", 0.01, 2.0, 0.310, format="%.3f")
    model = st.selectbox("Модель опору", ["G7", "G1"])
    t_coeff = st.number_input("Термозалежність (м/с на 1°C)", 0.0, 2.0, 0.1)

with tab_2:
    sh = st.number_input("Висота прицілу (см)", 0.0, 30.0, 4.5)
    zero_dist = st.number_input("Пристрілка (м)", 1, 1000, 100)
    twist = st.number_input("Твіст", 5.0, 20.0, 10.0)

with tab_3:
    temp = st.slider("Температура (°C)", -40, 60, 15)
    press = st.number_input("Атмосферний тиск (hPa)", 500, 1100, 1013)
    w_dir = st.slider("Напрям вітру (год)", 1, 12, 3)
    angle = st.slider("Кут пострілу (°)", -80, 80, 0)

# --- ГОЛОВНИЙ ЕКРАН: КНОПКИ + / - ---
st.title("🏹 Magelan242 Ballistics Pro")

col_d, col_w = st.columns(2)

with col_d:
    st.subheader("🎯 Дистанція цілі")
    c1, c2, c3 = st.columns([1, 2, 1])
    if c1.button("− 50", key="d_minus"): st.session_state.dist_val -= 50
    dist_input = c2.number_input("Метри", value=st.session_state.dist_val, step=50, label_visibility="collapsed")
    st.session_state.dist_val = dist_input
    if c3.button("+ 50", key="d_plus"): 
        st.session_state.dist_val += 50
        st.rerun()

with col_w:
    st.subheader("💨 Боковий вітер")
    w1, w2, w3 = st.columns([1, 2, 1])
    if w1.button("− 1", key="w_minus"): st.session_state.wind_val -= 1.0
    wind_input = w2.number_input("м/с", value=st.session_state.wind_val, step=1.0, label_visibility="collapsed")
    st.session_state.wind_val = wind_input
    if w3.button("+ 1", key="w_plus"): 
        st.session_state.wind_val += 1.0
        st.rerun()

# Виконання розрахунку
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': st.session_state.wind_val, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': 2000, 'sh': sh, 't_coeff': t_coeff}

try:
    df, v0_final, vsound = run_simulation(params)
    
    # Отримання даних для поточної дистанції (знаходимо найближче значення)
    target_idx = (df['Дистанція'] - st.session_state.dist_val).abs().idxmin()
    res = df.loc[target_idx]

    # Визначення статусу стабільності
    if res['Мах'] >= 1.2:
        status_html = '<span class="status-safe">СВЕРХЗВУК (Стабільно)</span>'
    elif res['Мах'] >= 1.05:
        status_html = '<span class="status-warn">ТРАНСЗВУК (Ризик)</span>'
    else:
        status_html = '<span class="status-danger">ДОЗВУК (Нестабільно)</span>'

    # Метрики
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Вертикаль (Кліки)", f"{res['Кліки_V']}")
    m2.metric("Горизонталь (Кліки)", f"{res['Кліки_H']}")
    m3.metric("Швидкість", f"{int(res['Швидкість'])} м/с")
    m4.markdown(f"<div class='metric-card'><small>Статус кулі</small><br>{status_html}</div>", unsafe_allow_html=True)

    # Графіки
    
    tab_graphs, tab_print = st.tabs(["📊 Аналітичні Графіки", "🖨️ Картка для друку"])

    with tab_graphs:
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Траєкторія падіння", "Швидкість та Мах"))
        fig.add_trace(go.Scatter(x=df['Дистанція'], y=df['Падіння_см'], name="см", line=dict(color='lime')), 1, 1)
        fig.add_trace(go.Scatter(x=df['Дистанція'], y=df['Швидкість'], name="м/с", line=dict(color='cyan')), 1, 2)
        # Лінія швидкості звуку
        fig.add_hline(y=vsound * 1.2, line_dash="dash", line_color="orange", row=1, col=2, annotation_text="1.2 Мах")
        
        fig.update_xaxes(range=[0, st.session_state.dist_val + 100])
        fig.update_layout(template="plotly_dark", height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab_print:
        st.subheader("📋 Картка вогню")
        print_step = st.selectbox("Крок таблиці:", [50, 100, 200], index=1)
        print_df = df[(df['Дистанція'] % print_step == 0) & (df['Дистанція'] <= st.session_state.dist_val + 200)]
        st.table(print_df[['Дистанція', 'Кліки_V', 'Кліки_H', 'Швидкість', 'Енергія']].style.format(precision=1))

except Exception as e:
    st.error(f"Помилка розрахунку: {e}")
