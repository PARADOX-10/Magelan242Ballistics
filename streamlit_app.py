import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# Налаштування інтерфейсу
st.set_page_config(page_title="Magelan242 Ballistics v15.0", layout="wide")

# --- МАТЕМАТИЧНЕ ЯДРО (Оптимізоване для 5000м) ---
def run_simulation(p):
    # Температурна корекція
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    
    # Модель атмосфери
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    
    # Коефіцієнт опору
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    angle_rad = math.radians(p['angle'])

    # Крок розрахунку - 1 метр для максимальної точності
    for d in range(0, p['max_dist'] + 1, 1):
        t = d / (v0_corr * math.exp(-k_drag * d / 2)) if d > 0 else 0
        
        # Падіння (вертикаль)
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        t_zero = p['zero_dist'] / (v0_corr * math.exp(-k_drag * p['zero_dist'] / 2))
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        # Вітер та Деривація
        wind_rad = math.radians(p['w_dir'] * 30)
        wind_drift = (p['w_speed'] * math.sin(wind_rad)) * (t - (d/v0_corr)) if d > 0 else 0
        derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2 if d > 0 else 0
        
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy = (weight_kg * v_curr**2) / 2
        
        # Додаємо дані лише для кроку, який вибере користувач у таблиці, 
        # або для графіків (кожен 10-й метр для швидкості рендерингу)
        if d % 10 == 0 or d == p['max_dist']:
            results.append({
                "Дистанція (м)": d,
                "Падіння (см)": round(y_m * 100, 2),
                "Знесення (см)": round((wind_drift + derivation) * 100, 2),
                "MRAD Верт": round((y_m * 100) / (d / 10), 3) if d > 0 else 0,
                "Швидкість (м/с)": round(v_curr, 1),
                "Енергія (Дж)": int(energy)
            })
            
    return pd.DataFrame(results), v0_corr

# --- БОКОВЕ МЕНЮ ---
st.sidebar.title("🛡️ Magelan242 Ballistics")
st.sidebar.info("Режим тестування")

tab_ammo, tab_rifle, tab_env = st.sidebar.tabs(["🚀 Набій", "🔭 Зброя", "🌍 Умови"])

with tab_ammo:
    v0 = st.number_input("Початкова швидкість (м/с)", 200.0, 1500.0, 961.0, step=1.0)
    weight = st.number_input("Вага кулі (гран)", 1.0, 1000.0, 200.0)
    input_energy = st.number_input("Енергія набою (Дж)", value=int((weight * 0.0000647989 * v0**2) / 2))
    bc = st.number_input("Бал. коефіцієнт (BC)", 0.01, 2.0, 0.395, format="%.3f")
    model = st.selectbox("Модель опору", ["G1", "G7"]) # G7 першим для далекої стрільби
    t_coeff = st.number_input("Термозалежність (м/с на 1°C)", 0.0, 2.0, 0.2)

with tab_rifle:
    sh = st.number_input("Висота прицілу (см)", 0.0, 30.0, 5.0)
    zero_dist = st.number_input("Пристрілка (м)", 1, 1000, 300)
    twist = st.number_input("Твіст ствола (дюйми)", 5.0, 20.0, 11.0)
    click_val = st.number_input("Ціна кліка (MRAD)", 0.001, 1.0, 0.1, format="%.3f")

with tab_env:
    temp = st.slider("Температура (°C)", -40, 60, 15)
    press = st.number_input("Тиск (hPa)", 500, 1100, 1013)
    w_speed = st.slider("Швидкість вітру (м/с)", 0.0, 30.0, 0.0)
    w_dir = st.slider("Напрямок (год)", 1, 12, 12)
    angle = st.slider("Кут стрільби (°)", -80, 80, 0)
    # Збільшена дистанція до 5000м з кроком 1м
    max_d = st.number_input("Макс. дистанція розрахунку (м)", 10, 5000, 1000, step=1)

# Розрахунок
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp, 
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': max_d, 'sh': sh, 't_coeff': t_coeff}

try:
    with st.spinner('Проводиться точний розрахунок...'):
        df, v0_final = run_simulation(params)

    # --- ІНТЕРФЕЙС ---
    st.header(f"🎯 Magelan242: Аналіз на {max_d}м")

    c1, c2, c3, c4 = st.columns(4)
    res = df.iloc[-1]
    c1.metric("V0 Коригована", f"{v0_final:.1f} м/с")
    c2.metric("Поправка MRAD", abs(res['MRAD Верт']))
    c3.metric("Кліки", f"{abs(res['MRAD Верт'] / click_val):.1f}")
    c4.metric("Енергія в цілі", f"{res['Енергія (Дж)']} Дж")

    # Графіки
    fig = make_subplots(rows=2, cols=1, subplot_titles=("Траєкторія (см)", "Енергія (Дж)"))
    fig.add_trace(go.Scatter(x=df['Дистанція (м)'], y=df['Падіння (см)'], name="Падіння", line=dict(color='lime')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Дистанція (м)'], y=df['Енергія (Дж)'], name="Енергія", fill='tozeroy', line=dict(color='red')), row=2, col=1)

    fig.update_layout(height=700, template="plotly_dark", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # Таблиця з можливістю вибору кроку
    st.subheader("📋 Таблиця поправок")
    step = st.selectbox("Крок таблиці (метрів):", [1, 5, 10, 25, 50, 100, 250, 500], index=5)
    
    # Фільтруємо таблицю згідно з обраним кроком
    display_df = df[df['Дистанція (м)'] % step == 0].copy()
    st.dataframe(display_df, use_container_width=True)

    st.download_button("📥 Завантажити повний звіт (CSV)", df.to_csv(index=False), "Magelan242_ELR_Report.csv")

except Exception as e:
    st.error(f"Помилка розрахунку: {e}. Перевірте введені дані.")
