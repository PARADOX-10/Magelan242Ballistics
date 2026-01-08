import streamlit as st
import pandas as pd
import numpy as np
import math

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan 300WM 1:11", layout="centered")

# --- ОНОВЛЕНІ ПРЕСЕТИ З ВАШИМ ТВІСТОМ ---
PRESETS = {
    ".223 Rem (69gr)": {"cal": 0.224, "weight": 69.0, "len": 0.98, "bc": 0.155, "v0": 850},
    ".300 Win Mag (195gr)": {
        "cal": 0.308, 
        "weight": 195.0, 
        "len": 1.450, 
        "bc_g7": 0.292, 
        "bc_g1": 0.584, 
        "v0": 893.0,
        "twist": 11.0 # ВАШ ТВІСТ
    },
    ".308 Win (175gr SMK)": {"cal": 0.308, "weight": 175.0, "len": 1.24, "bc_g7": 0.243, "bc_g1": 0.495, "v0": 790, "twist": 11.0},
    "6.5 Creedmoor (140gr ELD)": {"cal": 0.264, "weight": 140.0, "len": 1.38, "bc_g7": 0.315, "bc_g1": 0.620, "v0": 820, "twist": 8.0}
    ".338 LM (250gr)": {"cal": 0.338, "weight": 250.0, "len": 1.62, "bc": 0.335, "v0": 900}
}

# --- ЛОГІКА ТЕМИ ---
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

night = st.session_state.night_mode
bg_color, text_color, accent_color, card_bg = ("#0A0000", "#FF0000", "#CC0000", "#1A0000") if night else ("#0E1117", "#FFFFFF", "#C62828", "#1E1E1E")

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .mobile-hud {{ position: sticky; top: 0; z-index: 100; background-color: {bg_color}; padding: 10px 0; border-bottom: 2px solid {accent_color}; }}
    .hud-card {{ background-color: {card_bg}; border-radius: 10px; padding: 12px; text-align: center; border-left: 4px solid {accent_color}; margin-bottom: 5px; }}
    .hud-label {{ color: {"#660000" if night else "#888"}; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {text_color}; font-size: 32px; font-weight: 900; }}
    .stButton>button {{ width: 100%; background-color: {card_bg}; color: {text_color}; border: 1px solid {accent_color}; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def calculate_ballistics(p, d):
    if d <= 0: return {"v_mil": 0, "h_mil": 0, "h_side": "R", "v_at": p['v0'], "mach": 0, "sg": 0, "tof": 0}
    
    # 1. Атмосфера
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    rho = ((p['press'] - (p['hum']/100)*e_sat) * 100 / (287.05 * (p['temp'] + 273.15)))
    
    # 2. Опір (Drag)
    bc_adj = p['bc'] * (1.225 / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # 3. Вертикаль
    w_rad = math.radians(p['w_hour'] * 30)
    wind_cross = p['w_speed'] * math.sin(w_rad)
    aj_mil = 0.012 * wind_cross * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    omega = 7.2921e-5
    cor_v = 2 * omega * d * p['v0'] * math.cos(math.radians(p['lat'])) * math.sin(math.radians(p['az'])) * tof / d
    v_mil = abs((drop_m + cor_v) * 100 / (d/10) / 0.1) + aj_mil

    # 4. Горизонт (Вітер + Деривація + Коріоліс)
    sd_m = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(math.radians(p['lat'])) * tof / d
    h_mil = (wind_cross * (tof - d/p['v0']) + sd_m + cor_h) * 100 / (d/10) / 0.1

    # 5. Стабільність Міллера (враховує ваш 1:11)
    m_lb, m_cal = p['weight'] / 7000, p['cal']
    sg = (30 * m_lb) / ( (p['tw_v']/m_cal)**2 * m_cal**3 * (p['len']/m_cal) * (1 + (p['len']/m_cal)**2) ) * (p['v0']/2800)**(1/3)

    return {"v": round(abs(v_mil), 2), "h": round(abs(h_mil), 2), "side": "L" if h_mil < 0 else "R", "v_at": int(v_at), "mach": round(mach, 2), "sg": round(sg, 2), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.button("🌙 ТАКТИЧНИЙ РЕЖИМ", on_click=lambda: st.session_state.update({'night_mode': not st.session_state.night_mode}))

preset_name = st.selectbox("ОБЕРІТЬ НАБІЙ:", list(PRESETS.keys()))
defaults = PRESETS[preset_name]

st.markdown('<div class="mobile-hud">', unsafe_allow_html=True)
m_dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 1800, 800, step=5)
hud_c1, hud_c2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("🔫 ПАРАМЕТРИ НАБОЮ ТА ЗБРОЇ", expanded=True):
    m_model = st.radio("Драг-модель", ["G7", "G1"], horizontal=True)
    c1, c2 = st.columns(2)
    m_v0 = c1.number_input("Швидкість V0 (м/с)", value=float(defaults['v0']))
    current_bc = defaults['bc_g7'] if m_model == "G7" else defaults['bc_g1']
    m_bc = c2.number_input(f"БК ({m_model})", value=float(current_bc), format="%.3f")
    
    m_cal = c1.number_input("Калібр (дюйм)", value=float(defaults['cal']), format="%.3f")
    m_weight = c2.number_input("Вага (гран)", value=float(defaults['weight']))
    m_len = c1.number_input("Довжина кулі (дюйм)", value=float(defaults['len']))
    m_tw_v = c2.number_input("Твіст 1:", value=float(defaults['twist']))
    m_tw_d = st.radio("Напрямок нарізів", ["R", "L"], horizontal=True)
    m_sh = st.number_input("Висота оптики (см)", value=5.0)
    m_zero = st.number_input("Нуль (м)", value=100)

with st.expander("🌍 СЕРЕДОВИЩЕ ТА ВІТЕР"):
    col_a1, col_a2 = st.columns(2)
    m_temp = col_a1.slider("Темп (°C)", -30, 50, 15)
    m_hum = col_a2.slider("Волога (%)", 0, 100, 50)
    m_press = st.number_input("Тиск (гПа)", value=1013)
    st.divider()
    m_ws = st.slider("Вітер (м/с)", 0, 20, 3)
    m_wh = st.slider("Напрямок (год)", 1, 12, 3)
    m_lat = st.number_input("Широта стрільби", value=50)
    m_az = st.slider("Азимут (0-Пн, 90-Сх)", 0, 360, 90)

# РОЗРАХУНОК
params = {'temp': m_temp, 'press': m_press, 'hum': m_hum, 'v0': m_v0, 'bc': m_bc, 'model': m_model, 'cal': m_cal, 'weight': m_weight, 'len': m_len, 'tw_v': m_tw_v, 'tw_d': m_tw_d, 'sh': m_sh, 'zero': m_zero, 'lat': m_lat, 'az': m_az, 'w_speed': m_ws, 'w_hour': m_wh}
res = calculate_ballistics(params, m_dist)

# ОНОВЛЕННЯ HUD
hud_c1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v"]}</div></div>', unsafe_allow_html=True)
hud_c2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт {res["side"]} MIL</div><div class="hud-value">↔ {res["h"]}</div></div>', unsafe_allow_html=True)

# СТАТУС
if res['sg'] < 1.4:
    st.error(f"⚠️ Стабільність низька (Sg: {res['sg']})! Куля може 'кулятися' на холоді.")
else:
    st.success(f"✅ Стабільність ок (Sg: {res['sg']})")

st.write(f"**Інфо:** Mach {res['mach']} | ToF: {res['tof']} с | V у цілі: {res['v_at']} м/с")
