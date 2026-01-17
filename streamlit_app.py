import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 Ballistics Pro", layout="wide", initial_sidebar_state="collapsed")

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return None

# --- СТИЛІЗАЦІЯ (CSS) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { display: flex; align-items: center; gap: 20px; padding-bottom: 20px; border-bottom: 2px solid #00ff41; margin-bottom: 20px; }
        .header-title { font-size: 1.8rem; font-weight: 700; text-transform: uppercase; line-height: 1.2; }
        .header-sub { font-size: 0.5em; color: #00ff41; display: block; }
        .stTabs [data-baseweb="tab"] { height: 50px; background-color: #161b22; border-radius: 8px; color: #8b949e; flex-grow: 1; margin: 2px; }
        .stTabs [aria-selected="true"] { border: 1px solid #00ff41 !important; color: #00ff41 !important; }
        .hud-card { background: rgba(20, 25, 30, 0.8); border-left: 4px solid #00ff41; border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 5px; }
        .hud-value { color: #fff; font-size: 2rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- ФІЗИЧНЕ ЯДРО (NUMERICAL SOLVER) ---
def run_simulation(p):
    g = 9.80665
    
    # 1. АВТО-КОРЕКЦІЯ ВІД ВАГИ (Фізична взаємозалежність)
    # Еталонна вага для введених V0 та BC (наприклад, 175 гран)
    ref_weight = 175.0 
    # v_new = v_ref * sqrt(m_ref / m_new) - закон збереження енергії
    v_dynamic = p['v0'] * math.sqrt(ref_weight / p['weight_gr'])
    # BC_new = BC_ref * (m_new / m_ref) - корекція поперечного навантаження
    bc_dynamic = p['bc'] * (p['weight_gr'] / ref_weight)
    
    # Корекція швидкості на температуру пороху
    v0_final = v_dynamic + (p['temp'] - 15) * p['t_coeff']
    
    # Атмосферні константи
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    c_speed = 331.3 * math.sqrt(tk / 273.15) # Швидкість звуку
    rho_rel = rho / 1.225
    
    weight_kg = p['weight_gr'] * 0.0000647989
    i_factor = 1.0 / bc_dynamic
    
    # Обнулення: розрахунок кута підйому ствола для zero_dist
    t_approx = p['zero_dist'] / v0_final
    drop_at_zero = 0.5 * g * (t_approx**2)
    angle_launch = math.atan((drop_at_zero + p['sh']/100) / p['zero_dist'])
    
    # Початковий вектор (враховуючи кут місця цілі)
    total_angle = angle_launch + math.radians(p['angle'])
    dt = 0.002 # Крок інтегрування 2мс
    t, dist, y = 0.0, 0.0, -p['sh'] / 100
    vx = v0_final * math.cos(total_angle)
    vy = v0_final * math.sin(total_angle)
    
    # Вітер та Деривація
    wind_rad = math.radians(p['w_dir'] * 30)
    w_cross = p['w_speed'] * math.sin(wind_rad)
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    
    results = []
    step_to_save = 0
    
    while dist <= p['max_dist'] + 5:
        v_total = math.sqrt(vx**2 + vy**2)
        mach = v_total / c_speed
        
        # Функція опору залежно від Mach
        if p['model'] == "G7":
            cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
        else:
            cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
            
        # Прискорення опору a = F/m
        accel_drag = (0.5 * rho_rel * v_total**2 * cd * i_factor) * 0.00105 
        
        ax = -(accel_drag * (vx / v_total))
        ay = -(accel_drag * (vy / v_total)) - g
        
        # Оновлення координат (Метод Ейлера)
        vx += ax * dt
        vy += ay * dt
        dist += vx * dt
        y += vy * dt
        t += dt
        
        if dist >= step_to_save:
            # Вітрове знесення (Didion) та Спін-дрифт
            wind_drift = w_cross * (t - (dist / v0_final))
            derivation = -1 * 0.05 * (10 / p['twist']) * (dist / 100)**2 * t_dir
            
            # Розрахунок кутових поправок
            mrad_v = (y * 100) / (dist / 10) if dist > 0 else 0
            mrad_h = ((wind_drift + derivation) * 100) / (dist / 10) if dist > 0 else 0
            
            is_moa = "MOA" in p['turret_unit']
            click_val = 0.25 if is_moa else 0.1
            val_v = mrad_v * (3.4377 if is_moa else 1)
            val_h = mrad_h * (3.4377 if is_moa else 1)
            
            results.append({
                "Дист.": int(dist),
                "UP/DN": f"{'⬆️' if val_v > 0 else '⬇️'} {abs(val_v/click_val):.1f}",
                "L/R": f"{'➡️' if val_h > 0 else '⬅️'} {abs(val_h/click_val):.1f}",
                "V, м/с": int(v_total),
                "Mach": round(mach, 2),
                "E, Дж": int((weight_kg * v_total**2) / 2),
                "Падіння": y * 100
            })
            step_to_save += 10 # Крок збереження даних для таблиці/графіка
            
    return pd.DataFrame(results), v0_final, bc_dynamic

# --- ІНТЕРФЕЙС ПРОГРАМИ ---
logo_b64 = get_img_as_base64("logo.png")
logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="responsive-logo">' if logo_b64 else '🎯'

st.markdown(f"""
    <div class="header-container">
        <div style="font-size: 2.5rem;">{logo_html}</div>
        <div class="header-title">Magelan242 Ballistics<span class="header-sub">Numerical Solver v2.5 (Weight-Aware)</span></div>
    </div>
""", unsafe_allow_html=True)

# Основні налаштування дистанції
with st.container():
    c1, c2 = st.columns([2, 1])
    with c1: dist_input = st.number_input("ДИСТАНЦІЯ ЦІЛІ (м)", 50, 3000, 800, step=50)
    with c2: turret_unit = st.selectbox("СІТКА/КЛІКИ", ["MRAD (0.1)", "MOA (1/4)"])

st.markdown("---")

tab_env, tab_gun, tab_vis = st.tabs(["🌪️ АТМОСФЕРА", "🔫 КОМПЛЕКС", "📈 РЕЗУЛЬТАТИ"])

with tab_env:
    ec1, ec2 = st.columns(2)
    with ec1:
        w_speed = st.number_input("Вітер (м/с)", 0.0, 25.0, 3.0, step=0.5)
        w_dir = st.number_input("Напрям (год)", 1, 12, 3, help="3 год - боковий справа")
        angle = st.number_input("Кут цілі (°)", -60, 60, 0)
    with ec2:
        temp = st.number_input("Темп. повітря (°C)", -40, 50, 15)
        press = st.number_input("Тиск hPa (абс.)", 700, 1100, 1013)

with tab_gun:
    gc1, gc2 = st.columns(2)
    with gc1:
        v0 = st.number_input("V0 еталон (м/с)", 300, 1300, 820, help="Швидкість для ваги 175 гран")
        bc = st.number_input("BC еталон", 0.1, 1.2, 0.505, format="%.3f")
        model = st.radio("Драг-модель", ["G1", "G7"], horizontal=True)
        weight = st.number_input("ВАГА КУЛІ (гран)", 40, 400, 175, help="Зміна ваги змінить V0 та BC!")
    with gc2:
        zero_dist = st.number_input("Нуль (м)", 50, 1000, 100)
        sh = st.number_input("Вис. прицілу (см)", 2.0, 15.0, 5.0)
        twist = st.number_input("Твіст (дюйм)", 6.0, 16.0, 10.0)
        twist_dir = st.radio("Напрям нарізів", ["Right (Правий)", "Left (Лівий)"], horizontal=True)
        t_coeff = st.number_input("Термозалежність %", 0.0, 3.0, 0.1)

# РОЗРАХУНОК ПАРАМЕТРІВ
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': dist_input, 'sh': sh, 
          't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

df, v0_calc, bc_calc = run_simulation(params)
res = df.iloc[-1]

# HUD ВИВІД
st.markdown("<br>", unsafe_allow_html=True)
r1, r2, r3, r4 = st.columns(4)
r1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ</div><div class="hud-value" style="color:#ffcc00">{res["UP/DN"]}</div><div class="hud-sub">Кліків</div></div>', unsafe_allow_html=True)
r2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТ</div><div class="hud-value" style="color:#ffcc00">{res["L/R"]}</div><div class="hud-sub">Вітер+Дер.</div></div>', unsafe_allow_html=True)
r3.markdown(f'<div class="hud-card"><div class="hud-label">ШВИДКІСТЬ</div><div class="hud-value" style="color:#00f3ff">{res["V, м/с"]}</div><div class="hud-sub">м/с (M {res["Mach"]})</div></div>', unsafe_allow_html=True)
r4.markdown(f'<div class="hud-card"><div class="hud-label">ЕНЕРГІЯ</div><div class="hud-value" style="color:#ff3333">{res["E, Дж"]}</div><div class="hud-sub">Джоулів</div></div>', unsafe_allow_html=True)

# ВІЗУАЛІЗАЦІЯ
with tab_vis:
    st.caption(f"Розрахункові показники для ваги {weight}gr: V0 = {int(v0_calc)} м/с, BC = {bc_calc:.3f}")
    
    # Графік траєкторії
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Дист.'], y=df['Падіння'], mode='lines', name='Траєкторія', line=dict(color='#00ff41', width=3), fill='tozeroy', fillcolor='rgba(0,255,65,0.05)'))
    
    # Позначення трансзвуку (Mach < 1.2)
    transonic = df[df['Mach'] <= 1.2]
    if not transonic.empty:
        m_dist = transonic.iloc[0]['Дист.']
        fig.add_vline(x=m_dist, line_dash="dash", line_color="red")
        fig.add_annotation(x=m_dist, y=0, text="TRANS-SONIC", showarrow=True, arrowhead=1, font=dict(color="red"))

    fig.update_layout(template="plotly_dark", height=380, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="Метри", yaxis_title="См (Drop)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
    
    # Таблиця поправок
    step = st.select_slider("Крок таблиці (м)", [25, 50, 100], 100)
    st.dataframe(df[df['Дист.'] % step == 0], use_container_width=True, hide_index=True)
