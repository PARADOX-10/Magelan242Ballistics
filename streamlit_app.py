import streamlit as st
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Apex Pro v135", layout="wide")

class BallisticCalculator:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        self.v0 = p['v0'] * (1 + (p['temp'] - 15) * (p['p_sens'] / 100))
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.omega_earth = 7.292115e-5 

    def get_drag_g7(self, velocity):
        """Динамічна модель опору G7"""
        mach = velocity / (331.3 + 0.606 * self.p['temp'])
        if mach > 1.0:
            return 0.22 + (0.05 * (mach - 1))
        return 0.22 + (0.15 * (1 - mach))

    def solve_trajectory(self, target_dist, extra_angle_moa=0):
        dt = 0.002 # Крок інтеграції
        pos = np.array([0.0, -self.p['sh']/100, 0.0]) # Ствол нижче прицілу
        
        # Кут вильоту
        total_angle = math.radians(self.p['angle'] + (extra_angle_moa / 60))
        vel = np.array([
            self.v0 * math.cos(total_angle),
            self.v0 * math.sin(total_angle),
            0.0
        ])
        
        # Вітер (боковий компонент)
        wind_rad = math.radians(self.p['wh'] * 30)
        v_wind = np.array([0.0, 0.0, self.p['ws'] * math.sin(wind_rad)])
        
        t = 0.0
        while pos[0] < target_dist and t < 5.0:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            
            # Розрахунок прискорення опору
            cd = self.get_drag_g7(v_mag)
            accel_drag = -(0.5 * self.rho * v_mag * cd * 0.00052 / (self.p['bc'] * self.m_kg)) * v_rel
            
            # Ефект Коріоліса (горизонтальне відхилення)
            lat_rad = math.radians(self.p['lat'])
            coriolis_z = 2 * vel[0] * self.omega_earth * math.sin(lat_rad)
            
            accel_total = accel_drag + np.array([0, -self.g, coriolis_z])
            
            vel += accel_total * dt
            pos += vel * dt
            t += dt
            
        return pos, t, vel

    def get_results(self):
        # 1. Знаходимо кут пристрілки (щоб на 100м було 0)
        zero_angle = 0
        for _ in range(3):
            pos, _, _ = self.solve_trajectory(100, zero_angle)
            drop_moa = (pos[1] / 100) * (180/math.pi) * 60
            zero_angle -= drop_moa

        # 2. Рахуємо реальну дистанцію
        final_pos, tof, final_vel = self.solve_trajectory(self.p['dist'], zero_angle)
        
        # 3. Spin Drift (Деривація)
        sd_m = (1.25 * (1.5 + 1.2) * (tof**1.83)) * 0.0254
        
        # Конвертація в MIL (1 MIL = 10см на 100м)
        v_mil = -(final_pos[1] * 100) / (self.p['dist'] / 100)
        h_mil = ((final_pos[2] + sd_m) * 100) / (self.p['dist'] / 100)
        
        return {
            "v_mil": round(v_mil, 2),
            "h_mil": round(h_mil, 2),
            "v_at": int(np.linalg.norm(final_vel)),
            "tof": round(tof, 3)
        }

# --- ФУНКЦІЯ МАЛЮВАННЯ СІТКИ ---
def draw_reticle(v_mil, h_mil):
    fig = go.Figure()
    
    # Головні лінії перехрестя
    fig.add_shape(type="line", x0=-10, y0=0, x1=10, y1=0, line=dict(color="rgba(255,255,255,0.8)", width=2))
    fig.add_shape(type="line", x0=0, y0=-20, x1=0, y1=5, line=dict(color="rgba(255,255,255,0.8)", width=2))
    
    # MIL мітки
    for i in range(1, 16):
        # Вертикальні мітки (падіння)
        fig.add_shape(type="line", x0=-0.2, y0=-i, x1=0.2, y1=-i, line=dict(color="white", width=1))
        # Горизонтальні мітки (вітер)
        if i <= 10:
            fig.add_shape(type="line", x0=i, y0=-0.2, x1=i, y1=0.2, line=dict(color="white", width=1))
            fig.add_shape(type="line", x0=-i, y0=-0.2, x1=-i, y1=0.2, line=dict(color="white", width=1))

    # ТОЧКА ВЛУЧАННЯ
    fig.add_trace(go.Scatter(
        x=[h_mil], y=[-v_mil],
        mode="markers",
        marker=dict(color="#FF4B4B", size=15, symbol="cross", line=dict(width=2, color="white")),
        name="Impact"
    ))

    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(range=[-6, 6], showgrid=False, zeroline=False, title="MIL Horizontal"),
        yaxis=dict(range=[-14, 2], showgrid=False, zeroline=False, title="MIL Vertical"),
        margin=dict(l=20, r=20, t=20, b=20),
        height=700,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117"
    )
    return fig

# --- UI STREAMLIT ---
st.title("🏹 Magelan Apex Pro v135")
st.markdown("---")

c_input, c_vis = st.columns([1, 2])

with c_input:
    st.subheader("📝 Параметри")
    dist = st.number_input("Дистанція цілі (м)", value=800, step=50)
    v0 = st.number_input("Початкова швидкість (м/с)", value=820)
    bc = st.number_input("БК G7", value=0.305, format="%.3f")
    
    with st.expander("🌍 Метео та Геометрія"):
        ws = st.slider("Вітер (м/с)", 0.0, 20.0, 4.0)
        wh = st.slider("Напрямок вітру (год)", 0, 12, 3)
        temp = st.slider("Температура (°C)", -20, 45, 15)
        sh = st.number_input("Висота прицілу (см)", value=4.5)
        lat = st.slider("Широта (для Коріоліса)", 0, 90, 48)

    calc = BallisticCalculator({
        'v0': v0, 'bc': bc, 'weight': 175, 'sh': sh, 'dist': dist,
        'ws': ws, 'wh': wh, 'temp': temp, 'press': 1013, 'p_sens': 1.0, 
        'angle': 0, 'lat': lat
    })
    res = calc.get_results()

    st.success(f"**Вертикаль:** {res['v_mil']} MIL")
    st.success(f"**Горизонталь:** {res['h_mil']} MIL")
    st.info(f"Швидкість у цілі: {res['v_at']} м/с | Час: {res['tof']} с")

with c_vis:
    st.plotly_chart(draw_reticle(res['v_mil'], res['h_mil']), use_container_width=True)
