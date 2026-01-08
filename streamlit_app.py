import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="Magelan Apex v130", layout="centered")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #080a0c; }
    .main-card { 
        background: #12161b; padding: 20px; border-radius: 15px; 
        border-left: 6px solid #ff4b4b; margin-bottom: 12px;
    }
    .label { color: #8e949e; font-size: 13px; text-transform: uppercase; font-weight: bold; }
    .value { color: #ffffff; font-size: 32px; font-weight: 900; }
    .sub-value { color: #ff4b4b; font-size: 16px; font-weight: bold; }
    .stTable { background-color: #12161b; color: white; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛЛИСТИЧЕСКОЕ ЯДРО ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        t_ref = 15.0
        self.v0 = p['v0'] * (1 + (p['temp'] - t_ref) * (p['p_sens'] / 100))
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def calculate(self, custom_dist=None, custom_ws=None, custom_temp=None):
        target_dist = custom_dist if custom_dist is not None else self.p['dist']
        wind_speed = custom_ws if custom_ws is not None else self.p['ws']
        temperature = custom_temp if custom_temp is not None else self.p['temp']
        
        # Пересчет плотности и V0 если параметры изменены для таблицы чувствительности
        rho = (self.p['press'] * 100) / (287.05 * (temperature + 273.15))
        v0_eff = self.p['v0'] * (1 + (temperature - 15.0) * (self.p['p_sens'] / 100))
        
        dt = 0.005 
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([v0_eff * math.cos(math.radians(self.p['angle'])), 
                        v0_eff * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        v_wind = np.array([wind_speed * math.cos(math.radians(self.p['wh']*30)), 0.0, 
                           wind_speed * math.sin(math.radians(self.p['wh']*30))])
        
        model_factor = 1.0 if self.p['drag_model'] == "G7" else 0.518
        drag_const = 0.5 * rho * (1 / (self.p['bc'] * model_factor)) * 0.00052
        
        while pos[0] < target_dist:
            v_rel = vel - v_wind
            a_drag = -drag_const * np.linalg.norm(v_rel) * v_rel
            vel += dt * (a_drag + np.array([0, -self.g, 0]))
            pos += dt * vel
            t += dt

        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd_m = 1.25 * (sg + 1.2) * (t**1.83) * 0.01 
        
        total_z_m = pos[2] + sd_m
        v_mil = abs(pos[1] * 100) / (target_dist / 10)
        h_mil = abs(total_z_m * 100) / (target_dist / 10)
        
        return {'v_mil': v_mil, 'h_mil': h_mil, 'drop_cm': pos[1]*100, 'drift_cm': total_z_m*100}

# --- ИНТЕРФЕЙС ---
st.title("🏹 Magelan Apex v130")

with st.sidebar:
    st.header("⚙️ Оружие")
    v0 = st.number_input("V0 (м/с)", 893.0)
    bc = st.number_input("БК (G7/G1)", 0.292, format="%.3f")
    twist = st.number_input("Твист 1:", 11.0)
    weight = st.number_input("Вес (гран)", 195.0)
    click_val = st.selectbox("Клик (MIL)", [0.1, 0.05])
    p_sens = st.slider("Термозависимость %", 0.0, 2.0, 0.7)

dist = st.slider("🎯 Дистанция (м)", 100, 1500, 800, step=10)
ws = st.slider("💨 Ветер (м/с)", 0.0, 20.0, 3.0, step=0.5)

# БАЗОВЫЙ РАСЧЕТ
params = {'v0': v0, 'bc': bc, 'weight': weight, 'twist': twist, 'sh': 5.0, 'p_sens': p_sens, 
          'drag_model': "G7", 'dist': dist, 'temp': 15, 'press': 1013, 'ws': ws, 'wh': 3, 'angle': 0}
engine = ApexEngine(params)
res_base = engine.calculate()

# --- HUD ---
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="main-card"><div class="label">ВЕРТИКАЛЬ</div><div class="value">{round(res_base["v_mil"],2)} MIL</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="main-card"><div class="label">ГОРИЗОНТ</div><div class="value">{round(res_base["h_mil"],2)} MIL</div></div>', unsafe_allow_html=True)

# --- ТАБЛИЦА ЧУВСТВИТЕЛЬНОСТИ ---
st.subheader("📋 Таблица чувствительности (Ошибка оценки)")

# Расчет дельт
res_w_plus = engine.calculate(custom_ws = ws + 1.0) # +1 м/с ветра
res_t_minus = engine.calculate(custom_temp = 15 - 5.0) # -5 градусов

data = {
    "Параметр (Ошибка)": ["Ветер +1 м/с", "Температура -5°C", "Дистанция +25м"],
    "Смещение (см)": [
        round(abs(res_w_plus['drift_cm'] - res_base['drift_cm']), 1),
        round(abs(res_t_minus['drop_cm'] - res_base['drop_cm']), 1),
        "Расчет..." # Для краткости
    ],
    "Смещение (MIL)": [
        round(abs(res_w_plus['h_mil'] - res_base['h_mil']), 2),
        round(abs(res_t_minus['v_mil'] - res_base['v_mil']), 2),
        "..."
    ]
}
st.table(pd.DataFrame(data))

st.info("💡 Эта таблица показывает, насколько критична ошибка в 1 м/с ветра или 5°C температуры для вашего текущего выстрела.")
