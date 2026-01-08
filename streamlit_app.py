import streamlit as st
import pandas as pd
import math

# Налаштування для мобільних пристроїв
st.set_page_config(page_title="Magelan242 PRO", layout="centered")

# CSS для зручності керування пальцями
st.markdown("""
    <style>
    .stNumberInput input { font-size: 22px !important; height: 55px !important; }
    button[kind="secondary"] { height: 50px !important; font-weight: bold !important; }
    .stMetric { background: #1a1c24; border-radius: 12px; padding: 15px; border: 1px solid #333; }
    [data-testid="stExpander"] { background: #0e1117; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def full_ballistic_calc(p):
    # Корекція швидкості на температуру
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    
    # Щільність повітря (Тиск + Температура)
    tk = p['temp'] + 273.15
    rho = (p['press'] * 100) / (287.05 * tk)
    
    # Коефіцієнт опору (модель G7 за замовчуванням)
    k = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k *= 0.91

    # Розрахунок часу польоту
    d = p['dist']
    t = (math.exp(k * d) - 1) / (k * v0_corr) if d > 0 else 0
    
    # Падіння (Drop)
    drop = 0.5 * 9.806 * (t**2) * math.cos(math.radians(p['angle']))
    
    # Розрахунок нуля
    t_z = (math.exp(k * p['zero']) - 1) / (k * v0_corr)
    drop_z = 0.5 * 9.806 * (t_z**2)
    
    # Відносна висота (Вертикальне відхилення)
    y_m = -(drop - (drop_z + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    # Вітер та Деривація
    w_rad = math.radians(p['w_dir'] * 30)
    wind_drift = (p['w_speed'] * math.sin(w_rad)) * (t - (d/v0_corr))
    derivation = 0.05 * (p['twist'] / 10) * (d / 100)**2
    
    # Конвертація в кліки користувача
    # 1 MRAD на дистанції D = D/1000 метрів або D/10 см.
    mrad_v = (y_m * 100) / (d / 10) if d > 0 else 0
    mrad_h = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0
    
    clicks_v = round(abs(mrad_v / p['click']), 1)
    clicks_h = round(abs(mrad_h / p['click']), 1)
    
    return clicks_v, clicks_h, round(t, 3), int(v0_corr * math.exp(-k * d))

# --- ІНТЕРФЕЙС ---
st.title("🎯 Magelan242 PRO")

# ГОЛОВНІ ПАРАМЕТРИ (Завжди видимі)
col_d1, col_d2 = st.columns([2, 1])
dist = col_d1.number_input("ДИСТАНЦІЯ (м)", 0, 5000, 300, step=10)
angle = col_d2.number_input("КУТ (°)", -90, 90, 0, step=5)

col_w1, col_w2 = st.columns(2)
w_s = col_w1.number_input("ВІТЕР (м/с)", 0.0, 40.0, 2.0, step=0.5)
w_d = col_w2.number_input("ГОДИНА (1-12)", 1, 12, 3, step=1)

# БЛОКИ РЕДАГУВАННЯ (Згруповані)
with st.expander("🚀 БОЄПРИПАС (V0, BC, Вага)"):
    v0 = st.number_input("Початкова швидкість (м/с)", 100, 1500, 825)
    bc = st.number_input("Балістичний коефіцієнт (BC)", 0.01, 1.5, 0.450, format="%.3f")
    model = st.selectbox("Драг-модель", ["G7", "G1"])
    t_coeff = st.number_input("Термозалежність пороху (м/с на 1°C)", 0.0, 3.0, 0.2)

with st.expander("🔭 ЗБРОЯ (Приціл, Твіст, Кліки)"):
    sh = st.number_input("Висота прицілу (см)", 0.0, 25.0, 5.0)
    zero = st.number_input("Дистанція пристрілки (м)", 10, 1000, 100)
    twist = st.number_input("Твіст ствола (дюйми)", 5.0, 20.0, 10.0)
    click_val = st.number_input("Ціна кліка (MRAD)", 0.01, 1.0, 0.1, format="%.2f")

with st.expander("🌍 АТМОСФЕРА (Тиск, Темп.)"):
    temp = st.number_input("Температура повітря (°C)", -50, 60, 15)
    press = st.number_input("Тиск (hPa/mbar)", 500, 1100, 1013)

# Збір всіх параметрів
p = {
    'dist': dist, 'angle': angle, 'w_speed': w_s, 'w_dir': w_d,
    'v0': v0, 'bc': bc, 'model': model, 't_coeff': t_coeff,
    'sh': sh, 'zero': zero, 'twist': twist, 'click': click_val,
    'temp': temp, 'press': press
}

# РОЗРАХУНОК ТА ВИВІД
cv, ch, time, v_final = full_ballistic_calc(p)

st.divider()
res_v, res_h = st.columns(2)
res_v.metric("КЛІКИ V", f"{cv}")
res_h.metric("КЛІКИ H", f"{ch}")

c_t, c_v = st.columns(2)
c_t.write(f"⏱ **Час:** {time} с")
c_v.write(f"💨 **V у цілі:** {v_final} м/с")

if st.button("📊 ГЕНЕРУВАТИ ТАБЛИЦЮ"):
    rows = []
    for d_step in range((dist//100)*100 - 100, (dist//100)*100 + 401, 50):
        if d_step <= 0: continue
        p['dist'] = d_step
        v, h, _, _ = full_ballistic_calc(p)
        rows.append({"Метри": d_step, "Кліки V": v, "Кліки H": h})
    st.table(pd.DataFrame(rows))
