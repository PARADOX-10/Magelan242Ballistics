import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan242 Moving Target", layout="wide")

# --- МАТЕМАТИЧНЕ ЯДРО ---
def calculate_all_v51(p, dist, target_speed_kmh, target_angle_deg):
    if dist <= 0: return {"v_mil": 0, "h_mil": 0, "lead_mil": 0, "v_at": p['v0'], "e": 0, "tof": 0}
    
    # Балістика
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    tof = (math.exp(k * dist) - 1) / (k * p['v0'])
    v_dist = p['v0'] * math.exp(-k * dist)
    
    # Вертикаль
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = 0.5 * 9.806 * (tof**2)
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (dist / p['zero']) + p['sh']/100)
    v_mil = abs((y_m * 100) / (dist / 10) / 0.1)
    
    # Вітер (горизонт)
    w_rad = math.radians(p['w_hour'] * 30)
    wind_drift = p['w_speed'] * math.sin(w_rad) * (tof - (dist/p['v0']))
    h_mil_wind = (wind_drift * 100) / (dist / 10) / 0.1
    
    # Упередження (Moving Target Lead)
    # Швидкість цілі в м/с
    v_target_ms = target_speed_kmh / 3.6
    # Ефективна поперечна швидкість (V * sin(angle))
    v_cross = v_target_ms * math.sin(math.radians(target_angle_deg))
    # Зміщення цілі за час польоту кулі
    lead_m = v_cross * tof
    lead_mil = (lead_m * 100) / (dist / 10) / 0.1
    
    return {
        "v_mil": round(v_mil, 1),
        "h_mil_wind": round(h_mil_wind, 1),
        "lead_total_mil": round(abs(h_mil_wind + lead_mil), 1),
        "pure_lead": round(abs(lead_mil), 1),
        "v_at": int(v_dist),
        "e": int((p['weight'] * 0.0000648 * v_dist**2) / 2),
        "tof": round(tof, 3)
    }

# --- ІНТЕРФЕЙС ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #1a1a1a 0%, #C62828 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: right; border-right: 5px solid white; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 26px; font-weight: 900; }
    .lead-box { border: 2px solid #00FF00 !important; background-color: #0a1f0a !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>MAGELAN242 | DYNAMIC TARGET SYSTEM</h1></div>', unsafe_allow_html=True)

c_ammo, c_target, c_res = st.columns([1, 1, 1.2])

with c_ammo:
    st.subheader("🛠 Налаштування")
    v0 = st.number_input("V0 (м/с)", 820)
    bc = st.number_input("БК (G7)", 0.450, format="%.3f")
    weight = st.number_input("Вага (гран)", 175.0)
    dist = st.slider("Дистанція (м)", 0, 1500, 500)
    
    with st.expander("Атмосфера та зброя"):
        temp = st.number_input("Темп (°C)", 15)
        press = st.number_input("Тиск (гПа)", 1013)
        sh = st.number_input("Висота прицілу (см)", 5.0)
        zero = st.number_input("Нуль (м)", 100)

with c_target:
    st.subheader("🏃 Рух цілі")
    t_speed = st.number_input("Швидкість цілі (км/год)", 0.0, 40.0, 5.0)
    t_angle = st.slider("Кут руху цілі (°)", 0, 90, 90, help="90° - рух перпендикулярно стрільцю, 0° - на або від стрільця")
    
    st.divider()
    st.subheader("💨 Вітер")
    w_s = st.slider("Швидкість вітру (м/с)", 0.0, 15.0, 3.0)
    w_h = st.slider("Напрямок (год)", 1, 12, 3)

# ОБЧИСЛЕННЯ
p = {'v0': v0, 'bc': bc, 'weight': weight, 'temp': temp, 'press': press, 'sh': sh, 'zero': zero, 'w_speed': w_s, 'w_hour': w_h, 'model': 'G7'}
res = calculate_all_v51(p, dist, t_speed, t_angle)

with c_res:
    st.subheader("🎯 Результат")
    st.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль (Падіння)</div><div class="hud-value">↑ {res["v_mil"]} MIL</div></div>', unsafe_allow_html=True)
    
    # Виділяємо упередження зеленим
    st.markdown(f'<div class="hud-card lead-box"><div class="hud-label" style="color:#00FF00">Сумарне упередження (MIL)</div><div class="hud-value" style="color:#00FF00">↔ {res["lead_total_mil"]}</div></div>', unsafe_allow_html=True)
    
    st.caption(f"В т.ч. чисте упередження на рух: {res['pure_lead']} MIL")
    
    st.divider()
    c_e, c_v = st.columns(2)
    c_e.metric("Енергія", f"{res['e']} Дж")
    c_v.metric("V у цілі", f"{res['v_at']} м/с")
    st.write(f"⏱ Час польоту: **{res['tof']} с**")

st.divider()
st.subheader("📊 Таблиця винесення (MIL)")
# Швидка таблиця для різних швидкостей цілі
speeds = [0, 5, 10, 15, 20]
t_data = []
for s in speeds:
    r = calculate_all_v51(p, dist, s, t_angle)
    t_data.append({"Швидкість цілі (км/год)": s, "Сумарне винесення (↔)": r['lead_total_mil'], "Час польоту (с)": r['tof']})
st.table(pd.DataFrame(t_data))
