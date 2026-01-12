import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Pro", layout="wide", initial_sidebar_state="collapsed")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        padding: 10px;
        border-radius: 12px;
        border: 1px solid #30363d;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        color: #00ff00 !important;
    }
    @media print {
        .stButton, .stTabs, .sidebar, [data-testid="stSidebar"] { display: none !important; }
        .main { background-color: white !important; color: black !important; }
    }
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
    
    wind_rad = math.radians(p['w_dir'] * 30)
    w_long = p['w_speed'] * math.cos(wind_rad)
    w_cross = p['w_speed'] * math.sin(wind_rad)

    MOA_PER_MRAD = 3.4377
    is_moa = "MOA" in p['turret_unit']
    click_val = 0.25 if is_moa else 0.1
    
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1

    for d in range(0, p['max_dist'] + 1, 5):
        v0_eff = v0_corr - w_long 
        t = d / (v0_eff * math.exp(-k_drag * d / 2)) if d > 0 else 0
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        t_zero = p['zero_dist'] / (v0_corr * math.exp(-k_drag * p['zero_dist'] / 2))
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        aero_jump_mrad = 0.025 * w_cross * t_dir
        aero_jump_cm = aero_jump_mrad * (d / 10) 
        y_m += (aero_jump_cm / 100)
        
        wind_drift = w_cross * (t - (d/v0_corr)) if d > 0 else 0
        derivation = -1 * 0.05 * (10 / p['twist']) * (d / 100)**2 * t_dir if d > 0 else 0
        
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy = (weight_kg * v_curr**2) / 2
        
        mrad_v_raw = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h_raw = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        val_v = mrad_v_raw * (MOA_PER_MRAD if is_moa else 1)
        val_h = mrad_h_raw * (MOA_PER_MRAD if is_moa else 1)
        
        c_v = abs(val_v / click_val)
        c_h = abs(val_h / click_val)

        dir_v = "⬆️" if y_m < 0 else "⬇️"
        dir_h = "➡️" if mrad_h_raw > 0 else "⬅️"

        results.append({
            "Дист.": d,
            "UP/DN": f"{dir_v} {c_v:.1f}",
            "L/R": f"{dir_h} {c_h:.1f}",
            "V, м/с": int(v_curr),
            "E, Дж": int(energy),
            "Падіння": y_m * 100
        })
    return pd.DataFrame(results), v0_corr

# --- ІНТЕРФЕЙС ---
st.title("🛡️ Magelan242 Ballistics Pro")

top_col1, top_col2 = st.columns([1, 1])
with top_col1:
    dist_input = st.number_input("🎯 Дистанція цілі (м)", 10, 3000, 1200)
with top_col2:
    turret_unit = st.selectbox("🔭 Сітка/Кліки", ["MRAD (0.1)", "MOA (1/4)"])

with st.expander("🚀 Параметри набою та зброї"):
    e_col1, e_col2, e_col3 = st.columns(3)
    v0 = e_col1.number_input("V0 (м/с)", 200, 1200, 961)
    bc = e_col2.number_input("BC", 0.01, 1.0, 0.395, format="%.3f")
    model = e_col3.selectbox("Drag Model", ["G1", "G7"])
    weight = e_col1.number_input("Вага (гран)", 1, 500, 200)
    zero_dist = e_col2.number_input("Пристрілка (м)", 1, 1000, 300)
    twist = e_col3.number_input("Твіст (дюйми)", 5.0, 20.0, 11.0)
    sh = e_col1.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)
    t_coeff = e_col2.number_input("Термозалежність (м/с на 1°C)", 0.0, 2.0, 0.1)
    twist_dir = e_col3.selectbox("Напрямок нарізів", ["Right (Правий)", "Left (Лівий)"])

with st.expander("🌍 Навколишнє середовище"):
    env_col1, env_col2, env_col3 = st.columns(3)
    temp = env_col1.slider("Температура (°C)", -30, 50, 15)
    press = env_col2.number_input("Тиск (hPa)", 500, 1100, 1013)
    w_speed = env_col2.slider("💨 Вітер (м/с)", 0.0, 25.0, 0.0)
    w_dir = env_col3.slider("Напрям вітру (год)", 1, 12, 3)
    angle = env_col1.slider("Кут нахилу (°)", -60, 60, 0)

params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': dist_input, 'sh': sh, 
          't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

try:
    df, v0_final = run_simulation(params)
    res = df.iloc[-1]
    
    st.markdown("---")
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    res_col1.metric("UP/DN", res['UP/DN'], delta=f"{int(res['Падіння'])} см")
    res_col2.metric("L/R", res['L/R'])
    res_col3.metric("V", f"{res['V, м/с']} м/с")
    res_col4.metric("E", f"{res['E, Дж']} Дж")

    tab_table, tab_chart = st.tabs(["📋 Таблиця", "📊 Графік"])
    with tab_table:
        p_step = st.select_slider("Крок таблиці (м)", options=[10, 25, 50, 100], value=50)
        display_df = df[df['Дист.'] % p_step == 0].copy()
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Дист.": st.column_config.NumberColumn("Дист", format="%d м"),
                "UP/DN": st.column_config.TextColumn("Верт.", help="Поправка по вертикалі"),
                "L/R": st.column_config.TextColumn("Гориз.", help="Поправка по горизонталі"),
                "V, м/с": st.column_config.NumberColumn("V", format="%d"),
                "E, Дж": st.column_config.NumberColumn("E", format="%d"),
                "Падіння": st.column_config.NumberColumn("Пад.", format="%d см"),
            }
        )
        st.markdown("---")
        st.subheader("📚 Враховані балістичні фактори:")
        st.markdown("""
        * **Атмосфера:** Щільність повітря, Температура пороху.
        * **Аеродинаміка:** Опір (Drag), BC, G1/G7.
        * **Вітер:** Знесення (Lag Method), Вертикальний вплив.
        * **Гіроскоп:** Деривація, Аеро стрибок.
        * **Геометрія:** Гравітація, Кут місця, Висота прицілу.
        """)

    with tab_chart:
        # --- РОЗРАХУНОК ДУГИ 0-0 ---
        y_data = df['Падіння'].values
        x_data = df['Дист.'].values
        
        # Вирівнювання (Tilt)
        y_start = y_data[0]
        y_shifted = y_data - y_start
        y_end_shifted = y_shifted[-1]
        slope = -y_end_shifted / x_data[-1] if x_data[-1] > 0 else 0
        y_arc = y_shifted + slope * x_data

        # --- РОЗРАХУНОК МАКСИМАЛЬНОЇ ВИСОТИ ---
        max_h_val = np.max(y_arc)
        max_h_idx = np.argmax(y_arc)
        dist_at_max = x_data[max_h_idx]
        
        # Вивід інформації про висоту
        st.info(f"🏔️ **Максимальний підйом кулі:** {max_h_val:.1f} см на дистанції {dist_at_max} м")

        fig = make_subplots(rows=1, cols=1)
        
        # Лінія траєкторії
        fig.add_trace(go.Scatter(
            x=x_data, 
            y=y_arc, 
            name="Траєкторія", 
            line=dict(color='#00ff00', width=3),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 0, 0.1)'
        ))

        # Маркер максимальної висоти
        fig.add_trace(go.Scatter(
            x=[dist_at_max],
            y=[max_h_val],
            mode='markers+text',
            name='Макс. висота',
            text=[f"{max_h_val:.0f} см"],
            textposition="top center",
            textfont=dict(color="yellow", size=14),
            marker=dict(color='yellow', size=10, symbol='diamond')
        ))
        
        fig.update_layout(
            template="plotly_dark", 
            height=350, 
            margin=dict(l=10, r=10, t=30, b=10),
            title="Траєкторія польоту (Max Ordinate)",
            yaxis_title="Висота (см)",
            xaxis_title="Дистанція (м)",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Помилка: {e}")
