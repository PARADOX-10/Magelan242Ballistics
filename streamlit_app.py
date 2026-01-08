import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan242 v15.0", layout="wide")

# --- МАТЕМАТИЧНА МОДЕЛЬ ---
def get_ballistics(v0, bc, weight, sh, zero, dist, temp, press, w_speed, w_hour, model):
    # Корекція швидкості звуку та щільності повітря
    rho = (press * 100) / (287.05 * (temp + 273.15))
    k = 0.5 * rho * (1/bc) * 0.00052 * (0.91 if model == "G7" else 1.0)
    
    # Розрахунок польоту
    tof = (math.exp(k * dist) - 1) / (k * v0) if dist > 0 else 0
    v_dist = v0 * math.exp(-k * dist)
    energy = (weight * 0.0000648 * v_dist**2) / 2
    
    # Траєкторія
    t_z = (math.exp(k * zero) - 1) / (k * v0)
    drop = 0.5 * 9.806 * (tof**2)
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + sh/100) * (dist / zero) + sh/100)
    
    # Поправки MIL
    v_mil = abs((y_m * 100) / (dist / 10) / 0.1) if dist > 0 else 0
    
    # Вітер
    w_rad = math.radians(w_hour * 30)
    wind_drift = (w_speed * math.sin(w_rad) * (tof - (dist/v0)))
    h_mil = abs((wind_drift * 100) / (dist / 10) / 0.1) if dist > 0 else 0
    
    return {"v_mil": round(v_mil, 1), "h_mil": round(h_mil, 1), "v_at_dist": int(v_dist), "energy": int(energy), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.title("🎯 Magelan242 Ballistic HUD v15.0")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("⚙️ Налаштування")
    
    with st.expander("Набій та зброя", expanded=True):
        m_v0 = st.number_input("Початкова швидкість (м/с)", value=820)
        m_bc = st.number_input("Балістичний коефіцієнт", value=0.350, format="%.3f")
        m_model = st.radio("Драг-модель", ["G7", "G1"], horizontal=True)
        m_weight = st.number_input("Вага кулі (гран)", value=175.0)
        m_sh = st.number_input("Висота прицілу (см)", value=5.0)
        m_zero = st.number_input("Дистанція нуля (м)", value=100)

    with st.expander("Середовище", expanded=True):
        m_temp = st.slider("Температура (°C)", -30, 50, 15)
        m_press = st.slider("Тиск (гПа)", 800, 1100, 1013)
        m_w_speed = st.slider("Вітер (м/с)", 0.0, 20.0, 3.0)
        m_w_hour = st.slider("Напрямок вітру (год)", 1, 12, 3)

with col2:
    st.header("📊 Результати")
    m_dist = st.slider("Дистанція до цілі (м)", 0, 1500, 500, step=10)
    
    # Обчислення
    res = get_ballistics(m_v0, m_bc, m_weight, m_sh, m_zero, m_dist, m_temp, m_press, m_w_speed, m_w_hour, m_model)
    
    # Вивід карток
    c1, c2, c3 = st.columns(3)
    c1.metric("Вертикаль (MIL)", f"↑ {res['v_mil']}")
    c2.metric("Горизонт (MIL)", f"↔ {res['h_mil']}")
    c3.metric("Час польоту", f"{res['tof']} с")
    
    c4, c5 = st.columns(2)
    c4.metric("Швидкість у цілі", f"{res['v_at_dist']} м/с")
    c5.metric("Енергія", f"{res['energy']} Дж")

    st.divider()
    
    # Таблиця
    st.subheader("Таблиця поправок")
    distances = np.arange(0, 1001, 100)
    table_data = []
    for d in distances:
        r = get_ballistics(m_v0, m_bc, m_weight, m_sh, m_zero, d, m_temp, m_press, m_w_speed, m_w_hour, m_model)
        table_data.append([d, r['v_mil'], r['h_mil'], r['v_at_dist'], r['energy']])
    
    df = pd.DataFrame(table_data, columns=["Дистанція", "Вертикаль (MIL)", "Вітер (MIL)", "Швидкість (м/с)", "Енергія (Дж)"])
    st.table(df)
