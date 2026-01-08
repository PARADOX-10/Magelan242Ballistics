import streamlit as st
import numpy as np
import math
import plotly.graph_objects as go

# --- БАЛІСТИЧНЕ ЯДРО (Advanced) ---
class ProApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        self.v0 = p['v0'] * (1 + (p['temp'] - 15) * (p['p_sens'] / 100))
        
    def calculate(self):
        # [Тут логіка розрахунку AdvancedApexEngine з попередньої відповіді]
        # Для демонстрації сітки використаємо спрощені результати:
        dt = 0.001
        rho = (self.p['press'] * 100) / (287.05 * (self.p['temp'] + 273.15))
        
        # Розрахунок пристрілки (Zeroing)
        zero_angle = 0
        for _ in range(3):
            pos = np.array([0.0, -self.p['sh']/100, 0.0])
            vel = np.array([self.v0 * math.cos(math.radians(zero_angle)), self.v0 * math.sin(math.radians(zero_angle)), 0.0])
            t = 0
            while pos[0] < 100: # Пристрілка на 100м
                v_mag = np.linalg.norm(vel)
                accel = -(0.5 * rho * v_mag * 0.22 * 0.00052 / (self.p['bc'] * self.m_kg)) * vel + np.array([0, -self.g, 0])
                vel += accel * dt
                pos += vel * dt
            zero_angle -= (pos[1] / 100) * 3438 / 60

        # Основний розрахунок
        pos = np.array([0.0, -self.p['sh']/100, 0.0])
        vel = np.array([self.v0 * math.cos(math.radians(self.p['angle'] + zero_angle)), 
                        self.v0 * math.sin(math.radians(self.p['angle'] + zero_angle)), 0.0])
        
        wind_rad = math.radians(self.p['wh'] * 30)
        v_wind = np.array([0, 0, self.p['ws'] * math.sin(wind_rad)])
        
        t = 0
        while pos[0] < self.p['dist']:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            accel = -(0.5 * rho * v_mag * 0.22 * 0.00052 / (self.p['bc'] * self.m_kg)) * v_rel + np.array([0, -self.g, 0])
            vel += accel * dt
            pos += vel * dt
            t += dt

        v_mil = -(pos[1] * 10) / (self.p['dist'] / 100)
        h_mil = (pos[2] * 10) / (self.p['dist'] / 100)
        
        return {"v_mil": v_mil, "h_mil": h_mil, "v_at": int(np.linalg.norm(vel))}

# --- ВІЗУАЛІЗАЦІЯ СІТКИ ---
def draw_reticle(v_correction, h_correction):
    fig = go.Figure()

    # Малюємо основні лінії перехрестя
    fig.add_shape(type="line", x0=-10, y0=0, x1=10, y1=0, line=dict(color="white", width=1))
    fig.add_shape(type="line", x0=0, y0=-15, x1=0, y1=5, line=dict(color="white", width=1))

    # Малюємо мітки (hashes) MIL
    for i in range(-10, 11):
        if i == 0: continue
        # Горизонтальні мітки
        fig.add_shape(type="line", x0=i, y0=-0.2, x1=i, y1=0.2, line=dict(color="gray", width=1))
        # Вертикальні мітки
        fig.add_shape(type="line", x0=-0.2, y0=-i, x1=0.2, y1=-i, line=dict(color="gray", width=1))

    # ТОЧКА ВЛУЧАННЯ (Impact Point)
    fig.add_trace(go.Scatter(
        x=[h_correction], y=[-v_correction],
        mode="markers+text",
        marker=dict(color="red", size=12, symbol="x"),
        name="Влучання",
        text=[f"{v_correction:.2f} MIL"],
        textposition="top right"
    ))

    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(range=[-6, 6], title="Horizontal (MIL)", gridcolor="#333"),
        yaxis=dict(range=[-12, 2], title="Vertical (MIL)", gridcolor="#333"),
        width=500, height=600,
        showlegend=False,
        title="Прицільна сітка (MIL-Hash)"
    )
    return fig

# --- STREAMLIT UI ---
st.set_page_config(layout="wide")
st.title("🏹 Magelan Apex v135 Pro + Reticle")

with st.sidebar:
    st.header("🔧 Налаштування")
    dist = st.slider("Дистанція (м)", 100, 1500, 700)
    v0 = st.number_input("V0 (м/с)", value=820)
    ws = st.slider("Вітер (м/с)", 0, 15, 5)
    wh = st.slider("Вітер (год)", 0, 12, 3)

engine = ProApexEngine({
    'v0': v0, 'bc': 0.305, 'weight': 175, 'sh': 4.5, 'dist': dist,
    'ws': ws, 'wh': wh, 'temp': 15, 'press': 1013, 'p_sens': 1.0, 'angle': 0
})
res = engine.calculate()

col1, col2 = st.columns([2, 1])

with col1:
    st.plotly_chart(draw_reticle(res['v_mil'], res['h_mil']), use_container_width=True)

with col2:
    st.metric("Вертикальна поправка", f"{res['v_mil']:.2f} MIL")
    st.metric("Горизонтальна поправка", f"{res['h_mil']:.2f} MIL")
    st.write(f"**Швидкість у цілі:** {res['v_at']} м/с")
