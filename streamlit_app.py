import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan Omniscient v62.0", layout="centered")

# --- СЛОВНИК АВТОМАТИЧНИХ ПАРАМЕТРІВ ---
PRESETS = {
    ".223 Rem": {"cal": 0.224, "weight": 69.0, "len": 0.98, "bc": 0.301, "v0": 850},
    ".308 Win": {"cal": 0.308, "weight": 175.0, "len": 1.24, "bc": 0.495, "v0": 790},
    "6.5 CM": {"cal": 0.264, "weight": 140.0, "len": 1.38, "bc": 0.625, "v0": 820},
    ".300 WM": {"cal": 0.308, "weight": 200.0, "len": 1.45, "bc": 0.585, "v0": 890},
    ".338 LM": {"cal": 0.338, "weight": 250.0, "len": 1.62, "bc": 0.660, "v0": 900},
}

# --- ЯДРО РОЗРАХУНКІВ ---
def get_precision_data(p, d):
    # 1. Атмосфера
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    p_v = (p['hum'] / 100) * e_sat
    rho = ((p['press'] - p_v) * 100 / (287.05 * (p['temp'] + 273.15))) + (p_v * 100 / (461.495 * (p['temp'] + 273.15)))
    
    # 2. Балістика
    k = 0.5 * rho * (1/(p['bc'] * (1.225 / rho))) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    tof = (math.exp(k * d) - 1) / (k * p['v0']) if d > 0 else 0
    v_at = p['v0'] * math.exp(-k * d)
    
    # 3. Ефекти
    w_rad = math.radians(p['w_hour'] * 30)
    wind_cross = p['w_speed'] * math.sin(w_rad)
    
    # Аеродинамічний стрибок
    aj = 0.012 * wind_cross * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    # Коріоліс
    omega = 7.2921e-5
    lat_r, az_r = math.radians(p['lat']), math.radians(p['az'])
    cor_v = 2 * omega * d * p['v0'] * math.cos(lat_r) * math.sin(az_r) * tof / d if d > 0 else 0
    cor_h = 2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d if d > 0 else 0
    
    # Деривація
    sd = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    
    # Гравітація
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    v_mil = abs((drop + cor_v) * 100 / (d/10) / 0.1) + aj if d > 0 else 0
    h_mil = (wind_cross * (tof - d/p['v0']) + sd + cor_h) * 100 / (d/10) / 0.1 if d > 0 else 0
    
    # Стабільність (Miller)
    m_lb = p['weight'] / 7000
    sg = (30 * m_lb) / ( (p['tw_v']/p['cal'])**2 * p['cal']**3 * (p['len']/p['cal']) * (1 + (p['len']/p['cal'])**2) ) * (p['v0']/2800)**(1/3)
    
    return {"v": round(v_mil, 2), "h": round(abs(h_mil), 2), "side": "L" if h_mil < 0 else "R", "v_at": int(v_at), "sg": round(sg, 2)}

# --- ІНТЕРФЕЙС ---
st.markdown("<h2 style='color: #C62828;'>🚀 OMNISCIENT PRECISION v62</h2>", unsafe_allow_html=True)

# 1. SMART PRESETS
st.subheader("📦 Розумні пресети")
preset_name = st.selectbox("Оберіть калібр для автоналаштування:", ["Ручне введення"] + list(PRESETS.keys()))
defaults = PRESETS.get(preset_name, {"cal": 0.308, "weight": 175.0, "len": 1.25, "bc": 0.450, "v0": 820})

# 2. HUD
st.markdown('<div style="position: sticky; top: 0; background: #0E1117; z-index: 100; border-bottom: 2px solid #C62828; padding: 10px 0;">', unsafe_allow_html=True)
dist = st.slider("ЦІЛЬ (МЕТРИ)", 0, 2000, 850, step=5)
st.markdown('</div>', unsafe_allow_html=True)

# 3. НАЛАШТУВАННЯ (З автопідстановкою)
with st.expander("🔫 ЗБРОЯ ТА ПАТРОН (Ручне корегування)", expanded=True):
    col1, col2 = st.columns(2)
    v0 = col1.number_input("Швидкість V0 (м/с)", value=float(defaults['v0']))
    bc = col2.number_input("БК (G7)", value=float(defaults['bc']), format="%.3f")
    
    cal = col1.number_input("Калібр (дюйми)", value=float(defaults['cal']), format="%.3f")
    weight = col2.number_input("Вага кулі (гран)", value=float(defaults['weight']))
    
    length = col1.number_input("Довжина кулі (дюйми)", value=float(defaults['len']))
    twist = col2.number_input("Твіст 1:X (дюйми)", value=10.0)
    
    tw_dir = st.radio("Напрямок нарізів", ["R", "L"], horizontal=True)
    sh = st.number_input("Висота прицілу (см)", value=5.0)
    zero = st.number_input("Пристрілка (м)", value=100)

with st.expander("🌍 МЕТЕО ТА ГЕОГРАФІЯ"):
    temp = st.slider("Температура (°C)", -30, 50, 15)
    press = st.number_input("Тиск (гПа)", value=1013)
    hum = st.slider("Вологість (%)", 0, 100, 50)
    st.divider()
    lat = st.number_input("Широта (0-90)", value=50)
    az = st.slider("Азимут стрільби (0-360)", 0, 360, 90)

with st.expander("💨 ВІТЕР"):
    ws = st.slider("Швидкість (м/с)", 0, 20, 4)
    wh = st.slider("Напрямок (години)", 1, 12, 3)

# РОЗРАХУНОК
p = {'temp': temp, 'press': press, 'hum': hum, 'v0': v0, 'bc': bc, 'cal': cal, 'weight': weight, 'len': length, 'tw_v': twist, 'tw_d': tw_dir, 'sh': sh, 'zero': zero, 'lat': lat, 'az': az, 'w_speed': ws, 'w_hour': wh, 'model': 'G7'}
res = get_precision_data(p, dist)

# ВИВІД
st.divider()
c1, c2 = st.columns(2)
c1.metric("ВЕРТИКАЛЬ (MIL)", f"↑ {res['v']}")
c2.metric("ГОРИЗОНТ (MIL)", f"{res['side']} {res['h']}")

st.info(f"🌀 Стабільність (Sg): {res['sg']} | 💨 Швидкість у цілі: {res['v_at']} м/с")

# АНАЛІЗ ЦІНИ ПОМИЛКИ
st.subheader("📉 Аналіз чутливості")
p_error = p.copy(); p_error['w_speed'] += 1
res_err = get_precision_data(p_error, dist)
st.write(f"Помилка у вітрі на 1 м/с змістить кулю на **{round(res_err['h'] - res['h'], 2)} MIL**")
