import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="Magelan Apex v135", layout="centered")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #080a0c; }
    .main-card { 
        background: #12161b; padding: 20px; border-radius: 15px; 
        border-left: 6px solid #ff4b4b; margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .label { color: #8e949e; font-size: 13px; text-transform: uppercase; font-weight: bold; }
    .value { color: #ffffff; font-size: 34px; font-weight: 900; line-height: 1.1; }
    .sub-value { color: #ff4b4b; font-size: 16px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛЛИСТИЧЕСКОЕ ЯДРО ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        
    def calculate(self):
        # Атмосфера и начальная скорость
        t_ref = 15.0
        v0_eff = self.p['v0'] * (1 + (self.p['temp'] - t_ref) * (self.p['p_sens'] / 100))
        rho = (self.p['press'] * 100) / (287.05 * (self.p['temp'] + 273.15))
        
        dt = 0.005 
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([v0_eff * math.cos(math.radians(self.p['angle'])), 
                        v0_eff * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        
        # Компоненты ветра (включая боковую составляющую для AJ)
        wind_angle_rad = math.radians(self.p['wh'] * 30)
        v_wind = np.array([
            self.p['ws'] * math.cos(wind_angle_rad),
            0.0,
            self.p['ws'] * math.sin(wind_angle_rad)
        ])
        
        model_factor = 1.0 if self.p['drag_model'] == "G7" else 0.518
        drag_const = 0.5 * rho * (1 / (self.p['bc'] * model_factor)) * 0.00052
        
        path = []
        while pos[0] < self.p['dist']:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            a_drag = -drag_const * v_mag * v_rel
            vel += dt * (a_drag + np.array([0, -self.g, 0]))
            pos += dt * vel
            t += dt
            path.append(pos.copy())

        # --- СПЕЦ. ЭФФЕКТЫ ---
        # 1. Деривация (Spin Drift)
        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd_m = 1.25 * (sg + 1.2) * (t**1.83) * 0.01 
        
        # 2. Аэродинамический прыжок (Aerodynamic Jump)
        # Боковой ветер вызывает вертикальное смещение из-за прецессии
        wind_cross = self.p['ws'] * math.sin(wind_angle_rad)
        aj_moa = 0.0007 * (wind_cross * 3.28) # Коэффициент для типичной пули
        aj_m = (aj_moa * (self.p['dist'] / 100)) * 0.029 # Вертикальный сдвиг в метрах
        
        # Результирующие поправки
        total_y_m = pos[1] + aj_m 
        total_z_m = pos[2] + sd_m
        
        v_mil = abs(total_y_m * 100) / (self.p['dist'] / 10)
        h_mil = abs(total_z_m * 100) / (self.p['dist'] / 10)
        
        side = "ЛЕВО" if total_z_m < 0 else "ПРАВО"
        vert_dir = "ВВЕРХ" if total_y_m < 0 else "ВНИЗ" # Обычно всегда вверх (падение)

        return {
            'v_mil': round(v_mil, 2), 'h_mil': round(h_mil, 2), 
            'side': side, 'v_dir': vert_dir,
            'v_at': int(np.linalg.norm(vel)), 
            'e_final': int(0.5 * self.m_kg * np.linalg.norm(vel)**2),
            'path': np.array(path), 'v0_eff': round(v0_eff, 1), 'tof': round(t, 3)
        }

# --- ИНТЕРФЕЙС ---
st.title("🏹 Magelan Apex v135")

dist_op = st.slider("🎯 Дистанция (м)", 100, 1500, 800, step=10)
ws_op = st.slider("💨 Ветер (м/с)", 0.0, 25.0, 3.0, step=0.5)

with st.sidebar:
    st.header("🔫 Винтовка")
    drag_model = st.radio("Драг-модель", ["G7", "G1"])
    v0_in = st.number_input("V0 (м/с)", 893.0)
    bc_in = st.number_input("БК", 0.292, format="%.3f")
    weight_in = st.number_input("Вес (гран)", 195.0)
    twist_in = st.number_input("Твист 1:", 11.0)
    sh_in = st.number_input("Высота прицела (см)", 5.0)
    click_in = st.selectbox("Клик (MIL)", [0.1, 0.05])
    p_sens_in = st.slider("Термозависимость %", 0.0, 3.0, 0.7)

with st.expander("☁️ Метео и Направление ветра"):
    temp_in = st.slider("Температура (°C)", -30, 50, 15)
    press_in = st.number_input("Давление (гПа)", 900, 1100, 1013)
    wh_in = st.slider("Ветер дует С (часы)", 0, 12, 3)
    angle_in = st.slider("Угол цели (°)", -45, 45, 0)

engine = ApexEngine({
    'v0': v0_in, 'bc': bc_in, 'weight': weight_in, 'twist': twist_in, 'sh': sh_in,
    'p_sens': p_sens_in, 'drag_model': drag_model, 'dist': dist_op,
    'temp': temp_in, 'press': press_in, 'ws': ws_op, 'wh': wh_in, 'angle': angle_in
})
res = engine.calculate()

# --- HUD ---
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="main-card"><div class="label">{res["v_dir"]}</div><div class="value">{res["v_mil"]} MIL</div><div class="sub-value">{int(round(res["v_mil"]/click_in))} КЛИКОВ</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="main-card"><div class="label">{res["side"]}</div><div class="value">{res["h_mil"]} MIL</div><div class="sub-value">{int(round(res["h_mil"]/click_in))} КЛИКОВ</div></div>', unsafe_allow_html=True)

st.write(f"⚡ **Энергия:** {res['e_final']} Дж | **Скорость у цели:** {res['v_at']} м/с")

# График
fig = go.Figure()
fig.add_trace(go.Scatter(x=res['path'][:,0], y=res['path'][:,1], name="Drop", line=dict(color='red')))
fig.update_layout(height=300, template="plotly_dark", margin=dict(l=0,r=0,t=20,b=0), title="Вертикальная кривая")
st.plotly_chart(fig, use_container_width=True)
