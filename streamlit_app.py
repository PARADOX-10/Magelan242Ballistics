import streamlit as st
import pandas as pd
import math

# Налаштування для мобільних пристроїв
st.set_page_config(page_title="Magelan242", layout="centered")

# CSS для ВЕЛИКИХ кнопок та полів
st.markdown("""
    <style>
    /* Робимо поля введення великими */
    .stNumberInput input {
        font-size: 24px !important;
        height: 60px !important;
        text-align: center !important;
    }
    /* Стиль для великих кнопок поправок */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-size: 20px !important;
        font-weight: bold;
        border-radius: 15px;
        background-color: #262730;
    }
    /* Великі метрики */
    [data-testid="stMetricValue"] {
        font-size: 40px !important;
        color: #00FF00 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def calc_ballistics(d, w_s, w_d, v0, bc, temp, zero, sh):
    # Спрощена швидка модель для мобільного
    k = 0.5 * 1.225 * (1/bc) * 0.00052 * 0.91
    t = (math.exp(k * d) - 1) / (k * v0) if d > 0 else 0
    y_m = -(0.5 * 9.8 * t**2 - (0.5 * 9.8 * ((math.exp(k * zero) - 1) / (k * v0))**2 + sh/100) * (d / zero) + sh/100)
    w_rad = math.radians(w_d * 30)
    drift = (w_s * math.sin(w_rad)) * (t - (d/v0))
    
    cv = round(abs(((y_m * 100) / (d / 10)) / 0.1), 1) if d > 0 else 0
    ch = round(abs((drift * 1000) / d), 1) if d > 0 else 0
    return cv, ch

# Ініціалізація значень у сесії
if 'dist' not in st.session_state: st.session_state.dist = 300

# --- ГОЛОВНИЙ БЛОК ---
st.title("🏹 Magelan242")

# 1. ДИСТАНЦІЯ (Головний елемент)
st.subheader("Дистанція (м)")
col_d1, col_d2, col_d3 = st.columns([1, 2, 1])

if col_d1.button("−50"): st.session_state.dist -= 50
if col_d3.button("+50"): st.session_state.dist += 50
st.session_state.dist = col_d2.number_input("", value=st.session_state.dist, step=10, label_visibility="collapsed")

# 2. ВІТЕР
st.subheader("Вітер")
c_w1, c_w2 = st.columns(2)
w_speed = c_w1.number_input("м/с", 0.0, 20.0, 2.0, step=0.5)
w_hour = c_w2.number_input("Год", 1, 12, 3, step=1)

# 3. РЕЗУЛЬТАТ (Максимально помітно)
st.divider()
v0_fix, bc_fix, zero_fix, sh_fix = 825, 0.450, 100, 5.0
cv, ch = calc_ballistics(st.session_state.dist, w_speed, w_hour, v0_fix, bc_fix, 15, zero_fix, sh_fix)

res_v, res_h = st.columns(2)
res_v.metric("ВЕРТИКАЛЬ", f"{cv}")
res_h.metric("ВІТЕР", f"{ch}")
st.caption("Кліки (1 клік = 0.1 MRAD)")

# 4. ШВИДКІ НАЛАШТУВАННЯ (Згорнуті)
with st.expander("⚙️ Параметри гвинтівки"):
    v0 = st.number_input("V0 швидкість", 100, 1200, 825)
    bc_in = st.number_input("BC кулі", 0.1, 1.0, 0.450)
    zero_in = st.number_input("Нуль (м)", 10, 500, 100)

# 5. ШВИДКА ТАБЛИЦЯ (на клік)
if st.button("📊 Показати таблицю ±100м"):
    base = (st.session_state.dist // 100) * 100
    rows = []
    for d in range(base - 100, base + 201, 50):
        if d <= 0: continue
        v, h = calc_ballistics(d, w_speed, w_hour, v0, bc_in, 15, zero_in, sh_fix)
        rows.append({"М": d, "V": v, "H": h})
    st.table(pd.DataFrame(rows))
