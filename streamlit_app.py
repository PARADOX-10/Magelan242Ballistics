import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan Apex v125", layout="centered")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #080a0c; }
    .main-card { 
        background: #12161b; padding: 20px; border-radius: 15px; 
        border-left: 6px solid #ff4b4b; margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .label { color: #8e949e; font-size: 13px; text-transform: uppercase; font-weight: bold; }
    .value { color: #ffffff; font-size: 34px; font-weight: 900; line-height: 1.1; }
    .sub-value { color: #ff4b4b; font-size: 16px; font-weight: bold; }
    .stSlider, .stNumberInput { margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        
        # 1. Термозалежність швидкості (V0 vs Temp)
        t_ref = 15.0
        self.v0 = p['v0'] * (1 + (p['temp'] - t_ref) * (p['p_sens'] / 100))
        
        # 2. Щільність повітря (Air Density)
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def calculate(self):
        dt = 0.005 
        pos = np.array([0.0, self.p['sh']/100, 0.0]) # x, y, z
        vel = np.array([self.v0 * math.cos(math.radians(self.p['angle'])), 
                        self.v0 * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        
        # Вектор вітру
        v_wind = np.array([
            self.p['ws'] * math.cos(math.radians(self.p['wh']*30)),
            0.0,
            self.p['ws'] * math.sin(math.radians(self.p['wh']*30))
        ])
        
        # 3. Балістичний опір (Drag Model)
        model_factor = 1.0 if self.p['drag_model'] == "G7" else 0.518
        drag_const = 0.5 * self.rho * (1 / (self.p['bc'] * model_factor)) * 0.00052
        
        path = []
        while pos[0] < self.p['dist']:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            
            # Вектор прискорення (Опір + Гравітація)
            a_drag = -drag_const * v_mag * v_rel
            a_grav = np.array([0, -self.g, 0])
            
            vel += dt * (a_drag + a_grav)
            pos += dt * vel
            t += dt
            path.append(pos.copy())

        # 4. Деривація (Spin Drift)
        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd_m = 1.25 * (sg + 1.2) * (t**1.83) * 0.01 
        
        # 5. Результуючий горизонтальний зсув
        total_z_m = pos[2] + sd_m
        
        # 6. Конвертація в MIL
        v_mil = abs(pos[1] * 100) / (self.p['dist'] / 10)
        h_mil = abs(total_z_m * 100) / (self.p['dist'] / 10)
        side = "ЛІВО" if total_z_m < 0 else "ПРАВО"
        
        v_final = np.linalg.norm(vel)
        energy_final = 0.5 * self.m_kg * (v_final**2)
        
        return {
            'v_mil': round(v_mil, 2), 'h_mil': round(h_mil, 2), 'side': side,
            'v_at': int(v_final), 'e_final': int(energy_final),
            'path': np.array(path), 'v0_eff': round(self.v0, 1), 'tof': round(t, 3)
        }

# --- ІНТЕРФЕЙС ---
st.title("🏹 Magelan Apex v125")

dist_op = st.slider("🎯 Дистанція (м)", 100, 1500, 800, step=10)
ws_op = st.slider("💨 Вітер (м/с)", 0, 25, 3)

with st.sidebar:
    st.header("🔫 Гвинтівка та Набій")
    drag_model = st.radio("Драг-модель", ["G7", "G1"])
    v0_in = st.number_input("V0 (м/с)", 893.0)
    bc_in = st.number_input("БК кулі", 0.292, format="%.3f")
    weight_in = st.number_input("Вага (гран)", 195.0)
    twist_in = st.number_input("Твіст 1:", 11.0)
    sh_in = st.number_input("Висота прицілу (см)", 5.0)
    click_in = st.selectbox("Клік (MIL)", [0.1, 0.05])
    p_sens_in = st.slider("Термозалежність %", 0.0, 3.0, 0.7)

with st.expander("☁️ Метео та Кут"):
    temp_in = st.slider("Температура (°C)", -30, 50, 15)
    press_in = st.number_input("Тиск (гПа)", 900, 1100, 1013)
    wh_in = st.slider("Вітер (год)", 0, 12, 3)
    angle_in = st.slider("Кут нахилу (°)", -45, 45, 0)

# ОБЧИСЛЕННЯ
engine = ApexEngine({
    'v0': v0_in, 'bc': bc_in, 'weight': weight_in, 'twist': twist_in, 'sh': sh_in,
    'p_sens': p_sens_in, 'drag_model': drag_model, 'dist': dist_op,
    'temp': temp_in, 'press': press_in, 'ws': ws_op, 'wh': wh_in, 'angle': angle_in
})
res = engine.calculate()

# --- HUD (ВИВІД) ---
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="main-card"><div class="label">ВГОРУ</div><div class="value">{res["v_mil"]} MIL</div><div class="sub-value">{int(round(res["v_mil"]/click_in))} КЛІКІВ</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="main-card"><div class="label">{res["side"]}</div><div class="value">{res["h_mil"]} MIL</div><div class="sub-value">{int(round(res["h_mil"]/click_in))} КЛІКІВ</div></div>', unsafe_allow_html=True)

e1, e2 = st.columns(2)
with e1:
    st.markdown(f'<div class="main-card" style="border-left-color: #ff9f1c;"><div class="label">Енергія цілі</div><div class="value">{res["e_final"]} J</div></div>', unsafe_allow_html=True)
with e2:
    st.markdown(f'<div class="main-card" style="border-left-color: #4b7bff;"><div class="label">Швидкість цілі</div><div class="value">{res["v_at"]} м/с</div></div>', unsafe_allow_html=True)

# --- ВІЗУАЛІЗАЦІЯ ---
st.subheader("📊 Графіки траєкторії")
path_data = res['path']

fig_v = go.Figure()
fig_v.add_trace(go.Scatter(x=path_data[:, 0], y=path_data[:, 1], name="Drop", line=dict(color='#ff4b4b', width=3)))
fig_v.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), template="plotly_dark", xaxis_title="Дальність (м)", yaxis_title="Висота (м)")
st.plotly_chart(fig_v, use_container_width=True)

fig_h = go.Figure()
fig_h.add_trace(go.Scatter(x=path_data[:, 0], y=path_data[:, 2], name="Drift", line=dict(color='#4b7bff', width=3)))
fig_h.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), template="plotly_dark", xaxis_title="Дальність (м)", yaxis_title="Знос (м)")
st.plotly_chart(fig_h, use_container_width=True)

st.caption(f"V0 (кор.): {res['v0_eff']} м/с | TOF: {res['tof']} с")
