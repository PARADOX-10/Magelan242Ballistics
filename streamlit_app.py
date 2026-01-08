import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# Настройка страницы
st.set_page_config(page_title="Magelan242 Ballistics PRO", layout="wide")

# --- МАТЕМАТИЧЕСКОЕ ЯДРО ---
def run_simulation(p):
    # Базовая скорость с учетом термозависимости
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    
    # Плотность воздуха
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    
    # Коэффициент сопротивления
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    angle_rad = math.radians(p['angle'])

    for d in range(0, p['max_dist'] + 1, 1):
        # Расчет времени полета (аналитическое приближение)
        if d > 0:
            # t = (e^(k*d) - 1) / (k * v0)
            t = (math.exp(k_drag * d) - 1) / (k_drag * v0_corr)
        else:
            t = 0
            
        # Падение траектории
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        
        # Дистанция пристрелки (расчет для "нуля")
        t_zero = (math.exp(k_drag * p['zero_dist']) - 1) / (k_drag * v0_corr)
        drop_zero = 0.5 * g * (t_zero**2)
        
        # Итоговая вертикальная поправка (в метрах)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
       
        # Ветер и деривация
        wind_rad = math.radians(p['w_dir'] * 30)
        # Формула Дидсона для ветрового сноса: W = V_wind * (t - d/V0)
        wind_drift = (p['w_speed'] * math.sin(wind_rad)) * (t - (d/v0_corr)) if d > 0 else 0
        derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2 if d > 0 else 0
       
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy_curr = (weight_kg * v_curr**2) / 2
       
        # Конвертация в клики (1 клик = 0.1 MRAD = 1 см на 100 м)
        mrad_v = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        if d % 5 == 0 or d == p['max_dist']:
            results.append({
                "Дистанция": d,
                "Время (с)": round(t, 3),
                "Вертикаль (см)": round(y_m * 100, 2),
                "Клики (V)": round(abs(mrad_v / 0.1), 1),
                "Клики (H)": round(abs(mrad_h / 0.1), 1),
                "Скорость (м/с)": round(v_curr, 1),
                "Энергия (Дж)": int(energy_curr)
            })
    return pd.DataFrame(results), v0_corr

# --- ИНТЕРФЕЙС ---
st.title("🏹 Magelan242 Ballistics PRO")

# Ручной ввод характеристик
col_ammo, col_rifle, col_env = st.columns(3)

with col_ammo:
    st.subheader("🚀 Боеприпас")
    v0 = st.number_input("V0 скорость (м/с)", 100.0, 2000.0, 825.0)
    weight = st.number_input("Вес пули (гран)", 1.0, 1000.0, 168.0)
    bc = st.number_input("Коэффициент (BC)", 0.01, 2.0, 0.450, format="%.3f")
    model = st.selectbox("Драг-модель", ["G7", "G1"])
    t_coeff = st.number_input("Термозависимость (м/с на 1°C)", 0.0, 3.0, 0.2)

with col_rifle:
    st.subheader("🔭 Оружие")
    sh = st.number_input("Высота прицела (см)", 0.0, 30.0, 5.0)
    zero_dist = st.number_input("Дистанция пристрелки (м)", 1, 2000, 100)
    twist = st.number_input("Твист ствола (дюймы)", 5.0, 25.0, 10.0)
    click_val = st.number_input("Цена клика (MRAD)", 0.01, 1.0, 0.1)

with col_env:
    st.subheader("🌍 Среда")
    temp = st.number_input("Температура (°C)", -50.0, 60.0, 15.0)
    press = st.number_input("Давление (hPa)", 500, 1100, 1013)
    w_speed = st.number_input("Ветер (м/с)", 0.0, 50.0, 3.0)
    w_dir = st.slider("Направление ветра (час)", 1, 12, 3)
    max_d = st.number_input("Макс. дистанция (м)", 100, 5000, 1000)
    angle = st.number_input("Угол стрельбы (°)", -90, 90, 0)

# Расчет
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': max_d, 'sh': sh, 't_coeff': t_coeff}

try:
    df, v0_final = run_simulation(params)
    res = df.iloc[-1]

    st.divider()

    # Сводка результатов
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Поправка (V)", f"{res['Клики (V)']} кл.")
    m2.metric("Поправка (H)", f"{res['Клики (H)']} кл.")
    m3.metric("Время полета", f"{res['Время (с)']} с")
    m4.metric("Энергия у цели", f"{res['Энергия (Дж)']} Дж")

    # Таблица поправок
    st.subheader("📋 Таблица поправок")
    step = st.select_slider("Шаг таблицы (метры)", options=[1, 5, 10, 25, 50, 100], value=50)
    st.table(df[df['Дистанция'] % step == 0].style.format(precision=2))

    # Кнопка скачивания
    st.download_button("📥 Скачать CSV отчет", df.to_csv(index=False), "ballistics_report.csv")

except Exception as e:
    st.error(f"Ошибка: {e}")
