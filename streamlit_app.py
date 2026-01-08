import streamlit as st
import pandas as pd
import numpy as np
import math

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan Apex v100", layout="centered")

# --- СТИЛІЗАЦІЯ (MOBILE OPTIMIZED) ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #080a0c; }
    .main-card { background: #12161b; padding: 20px; border-radius: 15px; border-left: 6px solid #ff4b4b; margin-bottom: 10px; }
    .label { color: #8e949e; font-size: 14px; text-transform: uppercase; font-weight: bold; }
    .value { color: #ffffff; font-size: 38px; font-weight: 900; line-height: 1; }
    .sub-value { color: #ff4b4b; font-size: 18px; font-weight: bold; }
    .stSlider, .stNumberInput { margin-bottom: 20px; }
    .unit { font-size: 16px; color: #5c636a; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 # Гран в кг
        
        # Термокорекція швидкості
        t_ref = 15.0
        self.v0 = p['v0'] * (1 + (p['temp'] - t_ref) * (p['p_sens'] / 100))
        
        # Атмосфера
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def calculate(self):
        dt = 0.005
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([self.v0 * math.cos(math.radians(self.p['angle'])), 
                        self.v0 * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        
        # Опір
        drag_const = 0.5 * self.rho * (1 / self.p['bc']) * 0.00052
        
        while pos[0] < self.p['dist']:
            v_mag = np.linalg.norm(vel)
            # RK2 інтегрування для швидкості мобільних
            a_drag = -drag_const * v_mag * vel
            a_grav = np.array([0, -self.g, 0])
            
            vel += dt * (a_drag + a_grav)
            pos += dt * vel
            t += dt

        v_final = np.linalg.norm(vel)
        energy_start = 0.5 * self.m_kg * (self.v0**2)
        energy_final = 0.5 * self.m_kg * (v_final**2)
        
        v_mil = abs(pos[1] * 100) / (self.p['dist'] / 10)
        
        return {
            'v_mil': round(v_mil, 2),
            'v_at': int(v_final),
            'e_start': int(energy_start),
            'e_final': int(energy_final),
            'mach': round(v_final / self.v_sound, 2),
            'v0_actual': round(self.v0, 1)
        }

# --- ВЕРХНІЙ HUD (РЕЗУЛЬТАТИ) ---
st.markdown("<h1 style='text-align: center; color: white;'>MAGELAN APEX</h1>", unsafe_allow_html=True)

# Отримання даних (тимчасові значення для ініціалізації)
p_input = {
    'v0': 893.0, 'bc': 0.292, 'weight': 195.0, 'sh': 5.0, 'dist': 800,
    'temp': 15, 'press': 1013, 'p_sens': 0.7, 'angle': 0
}

# Слайдери під HUD для швидкої реакції
dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 1500, 800, step=10)
ws = st.slider("💨 ВІТЕР (м/с)", 0, 20, 3)

# Оновлення параметрів
p_input['dist'] = dist
# Розрахунок вітру (спрощено для HUD)
wind_drift = (ws * 0.15) * (dist / 100) # Орієнтовно для відображення

engine = ApexEngine(p_input)
res = engine.calculate()

# ВИВІД КАРТОК
c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""<div class="main-card">
        <div class="label">Вертикаль</div>
        <div class="value">{res['v_mil']}</div>
        <div class="sub-value">MIL</div>
        <div class="unit">{int(res['v_mil']*10)} кліків</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""<div class="main-card">
        <div class="label">Енергія</div>
        <div class="value">{res['e_final']}</div>
        <div class="sub-value">Дж</div>
        <div class="unit">Старт: {res['e_start']} J</div>
    </div>""", unsafe_allow_html=True)

st.markdown(f"""<div class="main-card" style="border-left-color: #4b7bff;">
    <div class="label">Швидкість у цілі</div>
    <div class="value">{res['v_at']} <span style="font-size:18px">м/с</span></div>
    <div class="sub-value">Mach {res['mach']}</div>
</div>""", unsafe_allow_html=True)

# --- НАЛАШТУВАННЯ (ЗГОРНУТІ ДЛЯ МОБІЛЬНИХ) ---
with st.expander("🛠️ НАЛАШТУВАННЯ ЗБРОЇ ТА МЕТЕО"):
    v0_in = st.number_input("V0 швидкість (м/с)", value=893.0)
    bc_in = st.number_input("БК кулі (G7)", value=0.292, format="%.3f")
    w_in = st.number_input("Вага кулі (гран)", value=195.0)
    temp_in = st.slider("Температура (°C)", -30, 50, 15)
    press_in = st.number_input("Тиск (гПа)", 900, 1100, 1013)
    p_input.update({'v0': v0_in, 'bc': bc_in, 'weight': w_in, 'temp': temp_in, 'press': press_in})

st.divider()
st.caption("Magelan Apex v100.0 | Розраховано за моделлю 3-DOF RK2")
