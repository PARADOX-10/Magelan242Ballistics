import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan Apex v130", layout="centered")

# --- СТИЛІЗАЦІЯ ---
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

# --- БАЛІСТИЧНЕ ЯДРО ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        
    def calculate(self, custom_dist=None, custom_ws=None, custom_temp=None):
        target_dist = custom_dist if custom_dist is not None else self.p['dist']
        wind_speed = custom_ws if custom_ws is not None else self.p['ws']
        temp = custom_temp if custom_temp is not None else self.p['temp']
        
        # Термозалежність V0
        v0_eff = self.p['v0'] * (1 + (temp - 15.0) * (self.p['p_sens'] / 100))
        # Щільність повітря
        rho = (self.p['press'] * 100) / (287.05 * (temp + 273.15))
        v_sound = 331.3 * math.sqrt(1 + temp / 273.15)
        
        dt = 0.005 
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([v0_eff * math.cos(math.radians(self.p['angle'])), 
                        v0_eff * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        v_wind = np.array([wind_speed * math.cos(math.radians(self.p['wh']*30)), 
                           0.0, wind_speed * math.sin(math.radians(self.p['wh']*30))])
        
        model_factor = 1.0 if self.p['drag_model'] == "G7" else 0.518
        drag_const = 0.5 * rho * (1 / (self.p['bc'] * model_factor)) * 0.00052
        
        path = []
        while pos[0] < target_dist:
            v_rel = vel - v_wind
            a_drag = -drag_const * np.linalg.norm(v_rel) * v_rel
            vel += dt * (a_drag + np.array([0, -self.g, 0]))
            pos += dt * vel
            t += dt
            path.append(pos.copy())

        # Деривація
        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd_m = 1.25 * (sg + 1.2) * (t**1.83) * 0.01 
        
        total_z_m = pos[2] + sd_m
        v_mil = abs(pos[1] * 100) / (target_dist / 10)
        h_mil = abs(total_z_m * 100) / (target_dist / 10)
        side = "ЛІВО" if total_z_m < 0 else "ПРАВО"
        
        v_final = np.linalg.norm(vel)
        return {
            'v_mil': v_mil, 'h_mil': h_mil, 'side': side, 'v_at': int(v_final),
            'e_final': int(0.5 * self.m_kg * (v_final**2)), 'path': np.array(path),
            'v0_eff': round(v0_eff, 1), 'tof': round(t, 3), 'drop_cm': pos[1]*100, 'drift_cm': total_z_m*100
        }

# --- ІНТЕРФЕЙС ---
st.title("🏹 Magelan Apex v130")

dist_op = st.slider("🎯 Дистанція (м)", 100, 1500, 800, step=10)
ws_op = st.slider("💨 Вітер (м/с)", 0.0, 25.0, 3.0, step=0.5)

with st.sidebar:
    st.header("🔫 Набій та Зброя")
    drag_model = st.radio("Драг-модель", ["G7", "G1"])
    v0_in = st.number_input("Початкова швидкість (м/с)", 893.0)
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
    angle_in = st.slider("Кут цілі (°)", -45, 45, 0)

engine = ApexEngine({
    'v0': v0_in, 'bc': bc_in, 'weight': weight_in, 'twist': twist_in, 'sh': sh_in,
    'p_sens': p_sens_in, 'drag_model': drag_model, 'dist': dist_op,
    'temp': temp_in, 'press': press_in, 'ws': ws_op, 'wh': wh_in, 'angle': angle_in
})
res = engine.calculate()

# --- HUD ---
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="main-card"><div class="label">ВГОРУ</div><div class="value">{round(res["v_mil"],2)} MIL</div><div class="sub-value">{int(round(res["v_mil"]/click_in))} КЛІКІВ</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="main-card"><div class="label">{res["side"]}</div><div class="value">{round(res["h_mil"],2)} MIL</div><div class="sub-value">{int(round(res["h_mil"]/click_in))} КЛІКІВ</div></div>', unsafe_allow_html=True)

# --- ТАБЛИЦЯ ЧУВСТВИТЕЛЬНОСТІ ---
st.subheader("📋 Таблиця чутливості (Похибка оцінки)")
res_w_plus = engine.calculate(custom_ws = ws_op + 1.0)
res_t_minus = engine.calculate(custom_temp = temp_in - 5.0)

sens_data = {
    "Параметр (Похибка)": ["Вітер +1 м/с", "Температура -5°C"],
    "Смещение (см)": [round(abs(res_w_plus['drift_cm'] - res['drift_cm']), 1), round(abs(res_t_minus['drop_cm'] - res['drop_cm']), 1)],
    "Смещение (MIL)": [round(abs(res_w_plus['h_mil'] - res['h_mil']), 2), round(abs(res_t_minus['v_mil'] - res['v_mil']), 2)]
}
st.table(pd.DataFrame(sens_data))

# --- ГРАФІКИ ---
path_data = res['path']
fig_v = go.Figure()
fig_v.add_trace(go.Scatter(x=path_data[:, 0], y=path_data[:, 1], name="Падіння", line=dict(color='#ff4b4b', width=3)))
fig_v.update_layout(height=300, template="plotly_dark", title="Вертикальна траєкторія (м)")
st.plotly_chart(fig_v, use_container_width=True)

st.caption(f"Енергія: {res['e_final']} J | V0 (кор.): {res['v0_eff']} м/с | TOF: {res['tof']} с")
