import streamlit as st
import pandas as pd
import numpy as np
import math

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Omniscient v62.5", layout="centered")

# --- СТИЛІЗАЦІЯ (НІЧНИЙ ТА МОБІЛЬНИЙ РЕЖИМИ) ---
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

def toggle_mode():
    st.session_state.night_mode = not st.session_state.night_mode

night = st.session_state.night_mode
bg_color = "#0A0000" if night else "#0E1117"
text_color = "#FF0000" if night else "#FFFFFF"
accent_color = "#CC0000" if night else "#C62828"
card_bg = "#1A0000" if night else "#1E1E1E"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .mobile-hud {{ 
        position: sticky; top: 0; z-index: 100; 
        background-color: {bg_color}; padding: 10px 0; 
        border-bottom: 2px solid {accent_color}; 
    }}
    .hud-card {{ 
        background-color: {card_bg}; border-radius: 10px; 
        padding: 12px; text-align: center; 
        border-left: 4px solid {accent_color}; margin-bottom: 5px; 
    }}
    .hud-label {{ color: {"#660000" if night else "#888"}; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {text_color}; font-size: 32px; font-weight: 900; }}
    input, label, .stSlider, .stSelectbox {{ color: {text_color} !important; }}
    .stButton>button {{ width: 100%; background-color: {card_bg}; color: {text_color}; border: 1px solid {accent_color}; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЗА ПРЕСЕТІВ ---
PRESETS = {
    "Ручне введення": {"cal": 0.308, "weight": 175.0, "len": 1.25, "bc": 0.243, "v0": 820},
    ".223 Rem (69gr)": {"cal": 0.224, "weight": 69.0, "len": 0.98, "bc": 0.155, "v0": 850},
    ".308 Win (175gr)": {"cal": 0.308, "weight": 175.0, "len": 1.24, "bc": 0.243, "v0": 790},
    ".300 WM": {"cal": 0.300, "weight": 195.0, "len": 1.45, "bc": 0.294, "v0": 893},
    "6.5 Creedmoor": {"cal": 0.264, "weight": 140.0, "len": 1.38, "bc": 0.315, "v0": 820},
    ".338 LM (250gr)": {"cal": 0.338, "weight": 250.0, "len": 1.62, "bc": 0.335, "v0": 900}
}

# --- ЯДРО РОЗРАХУНКІВ ---
def calculate_all(p, d):
    if d <= 0: return {"v_mil": 0, "h_mil": 0, "h_dir": "R", "v_at": p['v0'], "mach": 0, "sg": 0, "tof": 0}
    
    # 1. Щільність повітря (ICAO + Вологість)
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    p_v = (p['hum'] / 100) * e_sat
    rho = ((p['press'] - p_v) * 100 / (287.05 * (p['temp'] + 273.15))) + (p_v * 100 / (461.495 * (p['temp'] + 273.15)))
    
    # 2. Балістичний коефіцієнт та опір
    bc_adj = p['bc'] * (1.225 / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # 3. Вертикальні фактори (Гравітація + Етвеш + Аеро-стрибок)
    w_rad = math.radians(p['w_hour'] * 30)
    wind_cross = p['w_speed'] * math.sin(w_rad)
    aj_mil = 0.012 * wind_cross * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    omega = 7.2921e-5
    lat_r, az_r = math.radians(p['lat']), math.radians(p['az'])
    cor_v = 2 * omega * d * p['v0'] * math.cos(lat_r) * math.sin(az_r) * tof / d
    
    v_mil = abs((drop_m + cor_v) * 100 / (d/10) / 0.1) + aj_mil

    # 4. Горизонтальні фактори (Вітер + Деривація + Коріоліс)
    sd_m = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d
    h_mil = (wind_cross * (tof - d/p['v0']) + sd_m + cor_h) * 100 / (d/10) / 0.1

    # 5. Стабільність Міллера (Sg)
    m_lb, m_cal = p['weight'] / 7000, p['cal']
    sg = (30 * m_lb) / ( (p['tw_v']/m_cal)**2 * m_cal**3 * (p['len']/m_cal) * (1 + (p['len']/m_cal)**2) ) * (p['v0']/2800)**(1/3)

    return {"v_mil": round(abs(v_mil), 2), "h_mil": round(abs(h_mil), 2), "h_dir": "L" if h_mil < 0 else "R", "v_at": int(v_at), "mach": round(mach, 2), "sg": round(sg, 2), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.button("🌙 ТАКТИЧНИЙ НІЧНИЙ РЕЖИМ", on_click=toggle_mode)

# Вибір пресета
preset_choice = st.selectbox("Оберіть пресет набою:", list(PRESETS.keys()))
defaults = PRESETS[preset_choice]

# Фіксований HUD
st.markdown('<div class="mobile-hud">', unsafe_allow_html=True)
m_dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 2000, 800, step=5)
res_c1, res_c2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

# Налаштування
with st.expander("🔫 ЗБРОЯ ТА ПАТРОН", expanded=True):
    m_model = st.radio("Драг-модель", ["G7", "G1"], horizontal=True)
    c1, c2 = st.columns(2)
    m_v0 = c1.number_input("V0 (м/с)", value=float(defaults['v0']))
    # Корекція БК для G1 якщо обрано
    bc_val = defaults['bc'] if m_model == "G7" else defaults['bc'] * 1.9
    m_bc = c2.number_input(f"БК {m_model}", value=float(bc_val), format="%.3f")
    
    m_cal = c1.number_input("Калібр (дюйм)", value=float(defaults['cal']), format="%.3f")
    m_weight = c2.number_input("Вага (гран)", value=float(defaults['weight']))
    
    m_len = c1.number_input("Довжина кулі (дюйм)", value=float(defaults['len']))
    m_tw_v = c2.number_input("Твіст 1:X", value=10.0)
    
    m_tw_d = st.radio("Напрямок нарізів", ["R", "L"], horizontal=True)
    m_sh = st.number_input("Висота оптики (см)", value=5.0)
    m_zero = st.number_input("Пристрілка (м)", value=100)

with st.expander("🌍 МЕТЕО ТА ГЕОПОЗИЦІЯ"):
    m_temp = st.slider("Температура (°C)", -30, 50, 15)
    m_press = st.number_input("Тиск (гПа)", value=1013)
    m_hum = st.slider("Вологість (%)", 0, 100, 50)
    st.divider()
    m_lat = st.number_input("Широта (0-90)", value=50)
    m_az = st.slider("Азимут стрільби (0-360)", 0, 360, 90)

with st.expander("💨 ВІТЕР"):
    m_ws = st.slider("Швидкість (м/с)", 0, 20, 4)
    m_wh = st.slider("Година (12 - в обличчя)", 1, 12, 3)

# РОЗРАХУНОК
params = {
    'temp': m_temp, 'press': m_press, 'hum': m_hum, 'lat': m_lat, 'az': m_az, 
    'v0': m_v0, 'bc': m_bc, 'model': m_model, 'cal': m_cal, 'weight': m_weight, 
    'len': m_len, 'tw_v': m_tw_v, 'tw_d': m_tw_d, 'sh': m_sh, 'zero': m_zero, 
    'w_speed': m_ws, 'w_hour': m_wh
}
res = calculate_all(params, m_dist)

# ОНОВЛЕННЯ HUD
res_c1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ MIL</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
res_c2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТ {res["h_dir"]} MIL</div><div class="hud-value">↔ {res["h_mil"]}</div></div>', unsafe_allow_html=True)

# СТАТУС
st.info(f"🚀 Mach: {res['mach']} | Sg: {res['sg']} | ToF: {res['tof']} c")

# АНАЛІЗ ЧУТЛИВОСТІ
st.subheader("📉 Ціна помилки (Sensitivity)")
p_err = params.copy(); p_err['w_speed'] += 1
res_err = calculate_all(p_err, m_dist)
st.write(f"При зміні вітру на +1 м/с поправка зміниться на **{round(res_err['h_mil'] - res['h_mil'], 2)} MIL**")
