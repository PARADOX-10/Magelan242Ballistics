import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan242 v15.0 PRO", layout="wide")

# --- СТИЛІЗАЦІЯ (З ВЕРСІЇ v47.0) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #1a1a1a 0%, #C62828 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; border-right: 5px solid white; text-align: right; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 28px; font-weight: 900; }
    .section-head { color: #C62828; font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНА МОДЕЛЬ ---
def get_ballistics(p, dist):
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * dist) - 1) / (k * p['v0']) if dist > 0 else 0
    v_dist = p['v0'] * math.exp(-k * dist)
    energy = (p['weight'] * 0.0000648 * v_dist**2) / 2
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = 0.5 * 9.806 * (tof**2)
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (dist / p['zero']) + p['sh']/100)
    
    v_mil = abs((y_m * 100) / (dist / 10) / 0.1) if dist > 0 else 0
    w_rad = math.radians(p['w_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (tof - (dist/p['v0'])))
    h_mil = abs((wind_drift * 100) / (dist / 10) / 0.1) if dist > 0 else 0
    
    return {"v_mil": round(v_mil, 1), "h_mil": round(h_mil, 1), "v_at_dist": int(v_dist), "energy": int(energy), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | BALLISTIC HUD v15.0 PRO</h1></div>', unsafe_allow_html=True)

col_input, col_display = st.columns([1, 2])

with col_input:
    st.markdown('<div class="section-head">🛠 НАЛАШТУВАННЯ СИСТЕМИ</div>', unsafe_allow_html=True)
    
    with st.container():
        m_v0 = st.number_input("Початкова швидкість (м/с)", value=820)
        m_bc = st.number_input("Балістичний коефіцієнт", value=0.350, format="%.3f")
        m_model = st.radio("Драг-модель", ["G7", "G1"], horizontal=True)
        m_weight = st.number_input("Вага кулі (гран)", value=175.0)
        m_sh = st.number_input("Висота прицілу (см)", value=5.0)
        m_zero = st.number_input("Дистанція нуля (м)", value=100)

    st.markdown('<div class="section-head">🌍 СЕРЕДОВИЩЕ</div>', unsafe_allow_html=True)
    m_temp = st.slider("Температура (°C)", -30, 50, 15)
    m_press = st.slider("Тиск (гПа)", 800, 1100, 1013)
    m_w_speed = st.slider("Вітер (м/с)", 0.0, 20.0, 3.0)
    m_w_hour = st.slider("Напрямок вітру (год)", 1, 12, 3)

with col_display:
    st.markdown('<div class="section-head">🎯 ОПЕРАТИВНІ ДАНІ</div>', unsafe_allow_html=True)
    m_dist = st.slider("Дистанція до цілі (м)", 0, 1500, 500, step=10)
    
    params = {
        'v0': m_v0, 'bc': m_bc, 'weight': m_weight, 'sh': m_sh, 
        'zero': m_zero, 'temp': m_temp, 'press': m_press, 
        'w_speed': m_w_speed, 'w_hour': m_w_hour, 'model': m_model
    }
    
    res = get_ballistics(params, m_dist)
    
    # HUD CARDS (З v47.0)
    r1, r2, r3 = st.columns(3)
    r1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    r2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт MIL</div><div class="hud-value">↔ {res["h_mil"]}</div></div>', unsafe_allow_html=True)
    r3.markdown(f'<div class="hud-card"><div class="hud-label">Час польоту</div><div class="hud-value">{res["tof"]} с</div></div>', unsafe_allow_html=True)
    
    r4, r5 = st.columns(2)
    
    # Логіка кольору для швидкості (v47.0)
    v_color = "#00FF00" if res['v_at_dist'] > 340 else "#FF4B4B"
    r4.markdown(f'<div class="hud-card"><div class="hud-label">Швидкість у цілі</div><div class="hud-value" style="color:{v_color}">{res["v_at_dist"]} м/с</div></div>', unsafe_allow_html=True)
    r5.markdown(f'<div class="hud-card"><div class="hud-label">Енергія</div><div class="hud-value">{res["energy"]} Дж</div></div>', unsafe_allow_html=True)

    st.divider()
    
    # ТАБЛИЦЯ ПОПРАВОК
    st.subheader("📋 Оперативна таблиця")
    distances = np.arange(0, 1001, 100)
    table_data = []
    for d in distances:
        r = get_ballistics(params, d)
        table_data.append({"Дист (м)": d, "Вертикаль (MIL)": r['v_mil'], "Вітер (MIL)": r['h_mil'], "м/с": r['v_at_dist'], "Дж": r['energy']})
    
    st.dataframe(pd.DataFrame(table_data), use_container_width=True)

    # ГРАФІК ТРАЄКТОРІЇ (Додано для наочності)
    st.subheader("📈 Графік падіння (MIL)")
    plot_dist = np.arange(0, 1201, 50)
    plot_data = [get_ballistics(params, d)['v_mil'] for d in plot_dist]
    st.line_chart(pd.DataFrame({"MIL": plot_data}, index=plot_dist))
