import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan242 Terminal HUD", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    .header-box { background: linear-gradient(90deg, #1a1a1a 0%, #C62828 100%); padding: 15px; border-radius: 5px; margin-bottom: 20px; border-right: 5px solid white; text-align: right; }
    .hud-card { background-color: #1E1E1E; border-top: 4px solid #C62828; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .hud-label { color: #888; font-size: 11px; text-transform: uppercase; font-weight: bold; }
    .hud-value { color: #FFF; font-size: 28px; font-weight: 900; }
    .stat-box { background-color: #262730; padding: 10px; border-radius: 5px; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def calculate_all(p, d, angle_deg, target_speed_kmh):
    angle_rad = math.radians(angle_deg)
    cos_val = math.cos(angle_rad)
    
    # Атмосфера
    v0_eff = p['v0'] * (1 + (p['temp'] - 15) * 0.002)
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    # Швидкість та час
    tof = (math.exp(k * d) - 1) / (k * v0_eff) if d > 0 else 0
    v_dist = v0_eff * math.exp(-k * d)
    
    # Енергія (E = m * v^2 / 2)
    # вага в гранах -> кг (1 гран = 0.0000647989 кг)
    energy_j = (p['weight'] * 0.0000647989 * v_dist**2) / 2
    
    # Поправки
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_eff)
    drop = 0.5 * 9.806 * (tof**2) * cos_val
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    v_mil = abs((y_m * 100) / (d / 10) / 0.1) if d > 0 else 0
    
    # Вітер та упредження
    w_rad = math.radians(p['wind_hour'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad) * (tof - (d/v0_eff)))
    h_mil_wind = (wind_drift * 100) / (d / 10) / 0.1 if d > 0 else 0
    v_target_ms = target_speed_kmh / 3.6
    lead_mil = (v_target_ms * tof * 100) / (d / 10) / 0.1 if d > 0 else 0
    
    return {
        "v_mil": round(v_mil, 1), 
        "h_mil_wind": round(abs(h_mil_wind), 1), 
        "lead_mil": round(lead_mil, 1), 
        "tof": round(tof, 3),
        "v_at_dist": int(v_dist),
        "energy": int(energy_j)
    }

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-box"><h1>MAGELAN242 | ТЕРМІНАЛЬНИЙ МОНІТОР</h1></div>', unsafe_allow_html=True)

col_ammo, col_env, col_hud = st.columns([1, 1, 1.5])

with col_ammo:
    st.subheader("🧪 Дані набою")
    m_weight = st.number_input("Вага кулі (гран)", 10.0, 1000.0, 200.0)
    m_v0 = st.number_input("V0 (м/с)", 100, 1500, 850)
    m_bc = st.number_input("БК (Ballistic Coef)", 0.010, 1.500, 0.350, format="%.3f")
    m_model = st.radio("Модель", ["G7", "G1"], horizontal=True)
    m_sh = st.number_input("Висота прицілу (см)", 0.0, 20.0, 5.0)
    m_zero = st.number_input("Нуль (м)", 10, 1000, 100)

with col_env:
    st.subheader("🌍 Умови")
    m_dist = st.slider("Дистанція (м)", 0, 2000, 800, step=10)
    m_angle = st.slider("Кут (°)", -60, 60, 0)
    m_w_speed = st.slider("Вітер (м/с)", 0.0, 20.0, 3.0)
    m_w_hour = st.select_slider("Година вітру", options=list(range(1, 13)), value=3)
    m_target_speed = st.slider("Ціль (км/год)", 0.0, 40.0, 0.0)
    
    with st.expander("Атмосфера"):
        m_temp = st.number_input("Темп (°C)", -50, 60, 15)
        m_press = st.number_input("Тиск (гПа)", 700, 1150, 1013)

# ОБЧИСЛЕННЯ
params = {'v0': m_v0, 'bc': m_bc, 'weight': m_weight, 'model': m_model, 'sh': m_sh, 'zero': m_zero, 'temp': m_temp, 'press': m_press, 'w_speed': m_w_speed, 'wind_hour': m_w_hour}
res = calculate_all(params, m_dist, m_angle, m_target_speed)

with col_hud:
    st.subheader("🎯 Вогневе рішення")
    
    # Головні поправки
    h1, h2 = st.columns(2)
    h1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
    h2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт MIL</div><div class="hud-value">↔ {res["h_mil_wind"]}</div></div>', unsafe_allow_html=True)
    
    # Термінальні дані
    st.markdown("---")
    st.subheader("💥 Стан кулі біля цілі")
    e1, e2, e3 = st.columns(3)
    
    is_supersonic = res['v_at_dist'] > 340
    color = "#00FF00" if is_supersonic else "#FF4B4B"
    
    e1.markdown(f'<div class="stat-box"><div class="hud-label">Швидкість</div><div style="color:{color}; font-size:22px; font-weight:bold;">{res["v_at_dist"]} м/с</div></div>', unsafe_allow_html=True)
    e2.markdown(f'<div class="stat-box"><div class="hud-label">Енергія</div><div style="font-size:22px; font-weight:bold;">{res["energy"]} Дж</div></div>', unsafe_allow_html=True)
    e3.markdown(f'<div class="stat-box"><div class="hud-label">Час польоту</div><div style="font-size:22px; font-weight:bold;">{res["tof"]} с</div></div>', unsafe_allow_html=True)
    
    if m_target_speed > 0:
        st.warning(f"Упредження на рух: {res['lead_mil']} MIL")

# ГРАФІК ЕНЕРГІЇ ТА ШВИДКОСТІ
st.divider()
d_range = np.arange(0, 1501, 50)
df_data = [calculate_all(params, d, m_angle, m_target_speed) for d in d_range]
df = pd.DataFrame(df_data)
df['dist'] = d_range

st.subheader("📊 Динаміка втрати енергії та швидкості")
st.line_chart(df.set_index('dist')[['energy', 'v_at_dist']])
