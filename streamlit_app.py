import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan Global v58.0", layout="centered")

# --- ТЕМА ---
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

night = st.session_state.night_mode
bg_color = "#0A0000" if night else "#0E1117"
text_color = "#FF0000" if night else "#FFFFFF"
accent_color = "#CC0000" if night else "#C62828"
card_bg = "#1A0000" if night else "#1E1E1E"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .mobile-hud {{ position: sticky; top: 0; z-index: 100; background-color: {bg_color}; padding: 10px 0; border-bottom: 2px solid {accent_color}; }}
    .hud-card {{ background-color: {card_bg}; border-radius: 10px; padding: 12px; text-align: center; border-left: 4px solid {accent_color}; margin-bottom: 5px; }}
    .hud-label {{ color: {"#660000" if night else "#888"}; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {text_color}; font-size: 32px; font-weight: 900; }}
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИКА ELR (v58.0) ---
def calculate_v58(p, d):
    # Атмосфера
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0']) if d > 0 else 0
    v_dist = p['v0'] * math.exp(-k * d)
    
    # 1. Гравітаційне падіння + Аеродинамічний стрибок
    w_rad = math.radians(p['w_hour'] * 30)
    wind_cross = p['w_speed'] * math.sin(w_rad)
    aj_mil = 0.012 * wind_cross * (d / 100) / 10
    if p['twist_dir'] == "Лівий (L)": aj_mil = -aj_mil
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    y_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    # 2. Ефект Коріоліса (Земля)
    omega = 7.292115e-5 # Кутова швидкість Землі
    lat_rad = math.radians(p['lat'])
    az_rad = math.radians(p['azimuth'])
    
    # Горизонтальний Коріоліс
    cor_h_m = 2 * omega * d * p['v0'] * math.sin(lat_rad) * tof / d if d > 0 else 0
    # Вертикальний Коріоліс (Ефект Етвеша)
    cor_v_m = 2 * omega * d * p['v0'] * math.cos(lat_rad) * math.sin(az_rad) * tof / d if d > 0 else 0
    
    # 3. Деривація та Вітер
    sd_m = 1.25 * (p['twist'] / 10 + 1.2) * (tof**1.83)
    if p['twist_dir'] == "Лівий (L)": sd_m = -sd_m
    wind_drift_m = wind_cross * (tof - (d/p['v0']))

    # Підсумок MIL
    v_mil_total = abs((y_m + cor_v_m) * 100 / (d / 10) / 0.1) + aj_mil if d > 0 else 0
    h_mil_total = (wind_drift_m + sd_m + cor_h_m) * 100 / (d / 10) / 0.1 if d > 0 else 0
    
    return {"v": round(abs(v_mil_total), 1), "h": round(abs(h_mil_total), 1), "h_side": "L" if h_mil_total < 0 else "R", "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---
st.button("🌙 NIGHT MODE", on_click=lambda: st.session_state.update({'night_mode': not st.session_state.night_mode}))

st.markdown('<div class="mobile-hud">', unsafe_allow_html=True)
m_dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 2000, 1000, step=10)
res_col1, res_col2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("🌍 ГЕОПОЗИЦІЯ (КОРІОЛІС)", expanded=True):
    m_lat = st.number_input("Широта (0-90°)", value=50)
    m_az = st.slider("Азимут стрільби (0=Пн, 90=Сх)", 0, 360, 90)

with st.expander("🔫 ЗБРОЯ ТА НАБІЙ"):
    m_twist_dir = st.radio("Нарізи", ["Правий (R)", "Лівий (L)"], horizontal=True)
    m_v0 = st.number_input("V0 (м/с)", value=860)
    m_bc = st.number_input("БК (G7)", value=0.350, format="%.3f")
    m_twist = st.number_input("Твіст 1:", value=10.0)
    st.divider()
    m_w_s = st.slider("Вітер (м/с)", 0, 15, 3)
    m_w_h = st.slider("Година", 1, 12, 3)

# Розрахунок
params = {'v0': m_v0, 'bc': m_bc, 'model': 'G7', 'temp': 15, 'press': 1013, 'sh': 5.0, 'zero': 100, 'w_speed': m_w_s, 'w_hour': m_w_h, 'twist': m_twist, 'twist_dir': m_twist_dir, 'lat': m_lat, 'azimuth': m_az}
res = calculate_v58(params, m_dist)

# HUD
res_col1.markdown(f'<div class="hud-card"><div class="hud-label">Vertical MIL</div><div class="hud-value">↑ {res["v"]}</div></div>', unsafe_allow_html=True)
res_col2.markdown(f'<div class="hud-card"><div class="hud-label">Horizontal ({res["h_side"]})</div><div class="hud-value">↔ {res["h"]}</div></div>', unsafe_allow_html=True)

st.caption(f"Time of Flight: {res['tof']} s | Coriolis & Eötvös Included")
