import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan Precision v61.0", layout="centered")

# --- ГЛУБОКАЯ МАТЕМАТИКА ---
def get_air_density(temp, press, hum):
    e_sat = 6.112 * math.exp((17.67 * temp) / (temp + 243.5))
    p_v = (hum / 100) * e_sat
    p_d = press - p_v
    rho = (p_d * 100 / (287.05 * (temp + 273.15))) + (p_v * 100 / (461.495 * (temp + 273.15)))
    return rho

def calculate_precision(p, d):
    if d <= 0: return {"v_mil": 0, "h_mil": 0, "h_dir": "R", "v_at": p['v0'], "mach": 0, "sg": 0}
    
    rho = get_air_density(p['temp'], p['press'], p['hum'])
    rho_std = 1.225
    bc_adj = p['bc'] * (rho_std / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # 1. Вертикаль (Гравитация + Аэро прыжок + Этвеш)
    w_rad = math.radians(p['w_hour'] * 30)
    wind_cross = p['w_speed'] * math.sin(w_rad)
    aj_mil = 0.012 * wind_cross * (d / 100) / 10 * (1 if p['twist_dir'] == "R" else -1)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    omega = 7.2921e-5
    lat_r = math.radians(p['lat'])
    az_r = math.radians(p['az'])
    cor_v = 2 * omega * d * p['v0'] * math.cos(lat_r) * math.sin(az_r) * tof / d
    
    v_mil = abs((drop_m + cor_v) * 100 / (d/10) / 0.1) + aj_mil

    # 2. Горизонт (Ветер + Деривация + Кориолис)
    sd_m = 1.25 * (p['twist'] / 10 + 1.2) * (tof**1.83) * (1 if p['twist_dir'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d
    h_mil = (wind_cross * (tof - d/p['v0']) + sd_m + cor_h) * 100 / (d/10) / 0.1

    # Стабильность
    m_lb, m_cal = p['weight'] / 7000, p['cal']
    sg = (30 * m_lb) / ( (p['twist']/m_cal)**2 * m_cal**3 * (p['len']/m_cal) * (1 + (p['len']/m_cal)**2) ) * (p['v0']/2800)**(1/3)

    return {"v_mil": round(v_mil, 2), "h_mil": round(abs(h_mil), 2), "h_dir": "L" if h_mil < 0 else "R", "v_at": int(v_at), "mach": round(mach, 2), "sg": round(sg, 2)}

# --- ИНТЕРФЕЙС ---
st.title("🎯 Magelan Absolute Precision")

# Фиксированный HUD
st.markdown('<div style="position: sticky; top: 0; background: #0E1117; z-index: 100; padding: 10px; border-bottom: 2px solid red;">', unsafe_allow_html=True)
m_dist = st.slider("ДИСТАНЦИЯ (м)", 0, 2000, 800, step=5)
st.markdown('</div>', unsafe_allow_html=True)

# Боковая панель или экспандеры для настроек
with st.expander("🌍 АТМОСФЕРА И МЕСТОПОЛОЖЕНИЕ", expanded=True):
    col1, col2 = st.columns(2)
    m_temp = col1.number_input("Темп (°C)", value=15.0)
    m_press = col2.number_input("Давление (гПа)", value=1013.0)
    m_hum = st.slider("Влажность (%)", 0, 100, 50)
    m_lat = st.number_input("Широта (град)", value=50.0)
    m_az = st.slider("Азимут стрельбы (град)", 0, 360, 90)

with st.expander("🔫 ВИНТОВКА И ПАТРОН"):
    m_v0 = st.number_input("V0 (м/с)", value=820.0)
    m_bc = st.number_input("БК (G7)", value=0.243, format="%.3f")
    m_twist = st.number_input("Твист (1:X дюймов)", value=10.0)
    m_twist_dir = st.radio("Нарезка", ["R", "L"], horizontal=True)
    m_cal = st.number_input("Калибр (дюйм)", value=0.308)
    m_len = st.number_input("Длина пули (дюйм)", value=1.25)
    m_weight = st.number_input("Вес (гран)", value=175.0)
    m_sh = st.number_input("Высота прицела (см)", value=5.0)
    m_zero = st.number_input("Пристрелка (м)", value=100)

with st.expander("💨 ВЕТЕР"):
    m_ws = st.slider("Скорость (м/с)", 0, 15, 4)
    m_wh = st.slider("Направление (час)", 1, 12, 3)

# ОБЩИЙ РАСЧЕТ
p = {'temp': m_temp, 'press': m_press, 'hum': m_hum, 'lat': m_lat, 'az': m_az, 'v0': m_v0, 'bc': m_bc, 'model': "G7", 'twist': m_twist, 'twist_dir': m_twist_dir, 'cal': m_cal, 'len': m_len, 'weight': m_weight, 'sh': m_sh, 'zero': m_zero, 'w_speed': m_ws, 'w_hour': m_wh}
res = calculate_precision(p, m_dist)

# ВЫВОД РЕЗУЛЬТАТОВ
st.divider()
res_c1, res_c2 = st.columns(2)
res_c1.metric("ВЕРТИКАЛЬ", f"↑ {res['v_mil']} MIL")
res_c2.metric("ГОРИЗОНТ", f"{res['h_dir']} {res['h_mil']} MIL")

# ТАБЛИЦА ЧУВСТВИТЕЛЬНОСТИ
st.subheader("⚠️ Анализ чувствительности (Цена ошибки)")
st.caption(f"Изменение поправки на {m_dist}м при ошибке в данных:")

s_data = []
# Температура +5 градусов
p_t = p.copy(); p_t['temp'] += 5
r_t = calculate_precision(p_t, m_dist)
s_data.append({"Параметр": "Температура (+5°C)", "Изменение ↑": round(r_t['v_mil'] - res['v_mil'], 2), "Изменение ↔": 0})

# Ветер +1 м/с
p_w = p.copy(); p_w['w_speed'] += 1
r_w = calculate_precision(p_w, m_dist)
s_data.append({"Параметр": "Ветер (+1 м/с)", "Изменение ↑": 0, "Изменение ↔": round(r_w['h_mil'] - res['h_mil'], 2)})

# Давление -10 гПа
p_p = p.copy(); p_p['press'] -= 10
r_p = calculate_precision(p_p, m_dist)
s_data.append({"Параметр": "Давление (-10 гПа)", "Изменение ↑": round(r_p['v_mil'] - res['v_mil'], 2), "Изменение ↔": 0})

st.table(pd.DataFrame(s_data))

st.info(f"Стабильность (Sg): {res['sg']} | Mach: {res['mach']} | V цели: {res['v_at']} м/с")
