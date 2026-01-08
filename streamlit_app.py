import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

st.set_page_config(page_title="Magelan Ballistics Ultimate", layout="wide")

# --- МАТЕМАТИЧНЕ ЯДРО ---
def run_simulation(p):
    # Константи
    g = 9.80665
    dt = 0.002 # Крок інтегрування для високої точності
    
    # Початкові умови
    t, x, y, z = 0, 0, 0, 0
    v0_eff = p['v0'] + (p['temp'] - 15) * 0.2 # Термозалежність
    
    # Вектори швидкості з урахуванням кута місця цілі (Cos Angle)
    vx = v0_eff * math.cos(math.radians(p['angle']))
    vy = v0_eff * math.sin(math.radians(p['angle']))
    vz = 0
    
    # Атмосфера
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    while x < p['target_dist']:
        v_abs = math.sqrt(vx**2 + vy**2 + vz**2)
        
        # Сили опору
        ax = -k * v_abs * vx
        ay = -k * v_abs * vy - g
        az = -k * v_abs * vz
        
        # Оновлення координат (метод Ейлера)
        vx += ax * dt
        vy += ay * dt
        vz += az * dt
        x += vx * dt
        y += vy * dt
        z += vz * dt
        t += dt

    # Деривація (Spin Drift)
    spin_drift = 1.25 * (1.5 + 1.2) * (t**1.83) * 0.01 # в метрах
    
    # Вертикальне падіння відносно лінії прицілювання
    drop_m = y - (p['sh'] / 100)
    v_mil = abs(drop_m * 100) / (p['target_dist'] / 10)
    h_mil = (abs(z + spin_drift) * 100) / (p['target_dist'] / 10)
    
    return {'v_mil': round(v_mil, 2), 'h_mil': round(h_mil, 2), 'tof': round(t, 3), 'v_at': int(v_abs)}

# --- ІНТЕРФЕЙС ---
st.title("🏹 Magelan Ballistics Ultimate v78.0")

with st.sidebar:
    st.header("⚙️ Основні параметри")
    v0 = st.number_input("Початкова швидкість V0 (м/с)", value=893.0)
    bc_input = st.number_input("БК (G7)", value=0.292, format="%.3f")
    sh = st.number_input("Висота прицілу (см)", value=5.0)
    
    st.divider()
    st.header("🎯 Калібрування БК")
    st.info("Якщо реальне влучання відрізняється, введіть дані нижче:")
    cal_dist = st.number_input("Дистанція прострілу (м)", value=800)
    real_drop_mil = st.number_input("Реальна поправка (MIL)", value=0.0, format="%.2f")
    
    if st.button("Обчислити істинний БК"):
        best_bc = bc_input
        min_diff = 999
        for test_bc in np.arange(0.100, 0.500, 0.001):
            test_res = run_simulation({'v0':v0, 'bc':test_bc, 'sh':sh, 'temp':15, 'press':1013, 'target_dist':cal_dist, 'angle':0, 'model':"G7"})
            diff = abs(test_res['v_mil'] - real_drop_mil)
            if diff < min_diff:
                min_diff = diff
                best_bc = test_bc
        st.success(f"Ваш істинний БК: {best_bc:.3f}")
        bc_input = best_bc

# --- ГОЛОВНА ПАНЕЛЬ ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🌍 Умови пострілу")
    dist = st.slider("Відстань (м)", 100, 1500, 800, step=10)
    angle = st.slider("Кут місця цілі (°)", -45, 45, 0)
    temp = st.slider("Температура (°C)", -20, 45, 15)
    press = st.number_input("Тиск (гПа)", value=1013)
    
    st.subheader("💨 Вітер")
    ws = st.slider("Швидкість (м/с)", 0, 15, 3)
    wh = st.slider("Напрямок (год)", 0, 12, 3)

# Розрахунок результату
res = run_simulation({
    'v0': v0, 'bc': bc_input, 'sh': sh, 'temp': temp, 
    'press': press, 'target_dist': dist, 'angle': angle, 
    'model': "G7", 'w_speed': ws, 'w_hour': wh
})

with col2:
    st.subheader("🎯 Поправки")
    c1, c2 = st.columns(2)
    c1.markdown(f'<div style="background:#1A0000; padding:20px; border-radius:10px; border-left:5px solid red;">'
                f'<p style="color:gray; margin:0;">ВЕРТИКАЛЬ</p>'
                f'<h1 style="margin:0;">{res["v_mil"]} MIL</h1>'
                f'<p style="color:red; margin:0;">{int(res["v_mil"]*10)} кліків</p></div>', unsafe_allow_html=True)
    
    c2.markdown(f'<div style="background:#1A0000; padding:20px; border-radius:10px; border-left:5px solid red;">'
                f'<p style="color:gray; margin:0;">ГОРИЗОНТ</p>'
                f'<h1 style="margin:0;">{res["h_mil"]} MIL</h1>'
                f'<p style="color:red; margin:0;">{int(res["h_mil"]*10)} кліків</p></div>', unsafe_allow_html=True)

    st.divider()
    st.write(f"⏱ **Час польоту:** {res['tof']} с")
    st.write(f"💨 **Швидкість біля цілі:** {res['v_at']} м/с")

    # Візуалізація падіння (Holdover)
    
    st.caption("Позиція на сітці Mil-Dot для пострілу виносом.")
