import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

st.set_page_config(page_title="Magelan Analytics", layout="wide")

# --- РОЗШИРЕНЕ ЯДРО ---
def get_full_data(p):
    steps = np.arange(0, p['max_d'] + 1, 10)
    data = []
    
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop_z = 0.5 * 9.806 * (t_z**2)

    for d in steps:
        tof = (math.exp(k * d) - 1) / (k * p['v0']) if d > 0 else 0
        v_dist = p['v0'] * math.exp(-k * d)
        mach = v_dist / v_sound
        energy = (p['weight'] * 0.0000648 * v_dist**2) / 2
        
        # Траєкторія в см
        drop = 0.5 * 9.806 * (tof**2)
        y_cm = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100) * 100
        
        # Поправка в MIL
        v_mil = abs(y_cm / (d / 10)) if d > 0 else 0
        
        # Вітер (3 м/с для графіку)
        wind_m = 3.0 * (tof - (d/p['v0']))
        w_mil = abs((wind_m * 100) / (d / 10)) if d > 0 else 0
        
        data.append({
            "Dist": d, "V": int(v_dist), "Mach": round(mach, 2),
            "Energy": int(energy), "Drop_cm": round(y_cm, 1),
            "MIL": round(v_mil, 1), "Wind_MIL": round(w_mil, 1),
            "ToF": round(tof, 3)
        })
    return pd.DataFrame(data)

# --- ІНТЕРФЕЙС ---
st.title("📊 Magelan Ballistic Analytics")

with st.sidebar:
    st.header("🔧 Вхідні дані")
    p = {
        'v0': st.number_input("V0 (м/с)", 800),
        'bc': st.number_input("БК (G7)", 0.243, format="%.3f"),
        'weight': st.number_input("Вага (гран)", 175),
        'zero': st.number_input("Нуль (м)", 100),
        'sh': st.number_input("Висота оптики (см)", 5.0),
        'temp': st.slider("Температура (°C)", -30, 50, 15),
        'press': st.number_input("Тиск (гПа)", 1013),
        'max_d': st.number_input("Макс. дистанція (м)", 1500),
        'model': 'G7'
    }

df = get_full_data(p)

# --- ГРАФІКИ ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Траєкторія (падіння в см)")
    fig_drop = go.Figure()
    fig_drop.add_trace(go.Scatter(x=df['Dist'], y=df['Drop_cm'], mode='lines', name='Drop', line=dict(color='red')))
    fig_drop.update_layout(xaxis_title="Дистанція (м)", yaxis_title="Зміщення (см)", template="plotly_dark")
    st.plotly_chart(fig_drop, use_container_width=True)

with col2:
    st.subheader("⚡ Швидкість та Число Маха")
    fig_v = go.Figure()
    fig_v.add_trace(go.Scatter(x=df['Dist'], y=df['V'], mode='lines', name='Velocity'))
    # Лінія звукового бар'єру
    fig_v.add_hline(y=340, line_dash="dash", line_color="orange", annotation_text="Звуковий бар'єр")
    fig_v.update_layout(xaxis_title="Дистанція (м)", yaxis_title="V (м/с)", template="plotly_dark")
    st.plotly_chart(fig_v, use_container_width=True)

# --- РОЗШИРЕНА ТАБЛИЦЯ ---
st.subheader("📋 Детальна балістична таблиця")
st.dataframe(df.style.highlight_max(axis=0, subset=['Energy']).highlight_min(subset=['V']), use_container_width=True)

# --- ЕНЕРГЕТИЧНИЙ АНАЛІЗ ---
st.subheader("🔋 Енергетичний графік")
fig_e = go.Figure()
fig_e.add_trace(go.Scatter(x=df['Dist'], y=df['Energy'], fill='tozeroy', name='Energy (J)'))
fig_e.update_layout(xaxis_title="Дистанція (м)", yaxis_title="Джоулі", template="plotly_dark")
st.plotly_chart(fig_e, use_container_width=True)
