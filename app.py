import glob
import os
import platform
import warnings
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# =====================================================================
# 1. Streamlit 테마 설정 및 스타일링 (다크 테마 & 에메랄드 네온 조합)
# =====================================================================
st.set_page_config(
    page_title="서울시 따릉이 대여 수요 예측 시스템",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
    }
    
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
    }
    
    /* Neon Glow Emerald Card styling */
    .kpi-card {
        background: rgba(16, 185, 129, 0.05);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(16, 185, 129, 0.1);
        text-align: center;
        margin-bottom: 20px;
    }
    
    .kpi-title {
        color: #94A3B8;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .kpi-value {
        color: #10B981;
        font-size: 3.2rem;
        font-weight: 800;
        text-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
    }
    
    .kpi-unit {
        font-size: 1.2rem;
        color: #34D399;
        margin-left: 5px;
    }
    
    /* Info box card styling */
    .info-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(71, 85, 105, 0.3);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
    }
    
    .info-title {
        color: #F8FAFC;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .info-content {
        color: #94A3B8;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    
    /* Headers styling */
    h1, h2, h3 {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #34D399 0%, #10B981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 2. 데이터 처리 및 모델 캐싱 함수 정의
# =====================================================================
@st.cache_resource
def get_model_and_data():
    RENTAL_FILE_INTG = "./source_data/processed/서울_2023-2025_공공자전거_이용정보_통합.csv"
    WEATHER_FILE = "./source_data/processed/서울기상정보/2023-2025_서울_일별_기상정보_통합.csv"
    
    if not os.path.exists(RENTAL_FILE_INTG) or not os.path.exists(WEATHER_FILE):
        return None, None, None, None, "데이터 파일이 존재하지 않습니다."

    # 데이터 로드
    rental_daily = pd.read_csv(RENTAL_FILE_INTG, encoding="cp949", parse_dates=["날짜"])
    if 'Unnamed: 0' in rental_daily.columns:
        rental_daily.drop(['Unnamed: 0'], axis=1, inplace=True)
        
    weather_raw = pd.read_csv(WEATHER_FILE, encoding="utf-8")
    
    # 기상 데이터 컬럼 표준화
    WEATHER_KEYWORDS = [
        ("일시", "날짜"),
        ("평균기온", "평균기온"),
        ("최고기온", "최고기온"),
        ("최저기온", "최저기온"),
        ("강수량", "강수량"),
        ("최대풍속", "최대풍속"),
        ("최저풍속", "최저풍속"),
        ("평균풍속", "평균풍속"),
        ("최저습도", "최저습도"),
        ("최고습고", "최저습도"),
        ("평균습도", "평균습도"),
        ("일조", "일조"),
        ("일사", "일사"),
        ("적설", "적설량"),
    ]
    
    def find_col(df, keyword):
        key = keyword.replace(" ", "")
        for col in df.columns:
            if key in str(col).replace(" ", ""):
                return col
        return None

    rename_map = {}
    used_targets = set()
    for keyword, target in WEATHER_KEYWORDS:
        if target in used_targets:
            continue
        col = find_col(weather_raw, keyword)
        if col is not None and col not in rename_map:
            rename_map[col] = target
            used_targets.add(target)
            
    weather_std = weather_raw[list(rename_map.keys())].rename(columns=rename_map)
    weather_std["날짜"] = pd.to_datetime(weather_std["날짜"], errors="coerce")
    if "강수량" in weather_std.columns:
        weather_std["강수량"] = weather_std["강수량"].fillna(0)

    # 데이터 병합
    df = pd.merge(rental_daily, weather_std, on="날짜", how="inner")

    # 결측치 보간
    zero_fill_cols = ["강수량", "일조", "일사", "적설량"]
    for col in zero_fill_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
            
    interpolate_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in zero_fill_cols + ["이용건수"]
    ]
    if interpolate_cols:
        df[interpolate_cols] = df[interpolate_cols].interpolate(method="linear", limit_direction="both")
        
    fill_cols = [c for c in df.columns if c not in ["날짜", "이용건수"]]
    for col in fill_cols:
        if df[col].isna().any():
            df[col] = df[col].ffill().bfill()
            
    df = df.dropna().reset_index(drop=True)
    df = df[df["이용건수"] > 0].reset_index(drop=True)

    # 파생 변수 추가
    df["월"] = df["날짜"].dt.month
    df["요일"] = df["날짜"].dt.weekday
    df["is_weekend"] = df["요일"].isin([5, 6]).astype(int)
    df["day_of_year"] = df["날짜"].dt.dayofyear
    df["week_of_year"] = df["날짜"].dt.isocalendar().week.astype(int)

    # 공휴일
    holiday_dates = pd.to_datetime([
        "2023-01-01", "2023-01-21", "2023-01-22", "2023-01-23", "2023-01-24",
        "2023-03-01", "2023-05-05", "2023-05-27", "2023-06-06", "2023-08-15",
        "2023-09-28", "2023-09-29", "2023-09-30", "2023-10-02", "2023-10-03",
        "2023-10-09", "2023-12-25",
        "2024-01-01", "2024-02-09", "2024-02-10", "2024-02-11", "2024-03-01",
        "2024-05-05", "2024-05-06", "2024-05-15", "2024-06-06", "2024-08-15",
        "2024-09-16", "2024-09-17", "2024-09-18", "2024-10-03", "2024-10-09",
        "2024-12-25",
        "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-01",
        "2025-05-05", "2025-05-06", "2025-05-13", "2025-06-06", "2025-08-15",
        "2025-09-06", "2025-09-07", "2025-09-08", "2025-10-03", "2025-10-09",
        "2025-12-25",
    ])
    df["is_holiday"] = df["날짜"].isin(holiday_dates).astype(int)

    features = [
        "평균기온", "최고기온", "최저기온", "강수량", "최대풍속", "평균풍속",
        "일조", "일사", "적설량", "월", "요일", "is_weekend", "day_of_year",
        "week_of_year", "is_holiday"
    ]
    
    X = df[features]
    y = df["이용건수"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    return model, features, df, holiday_dates, None


# 데이터 및 모델 추출
model, features, df_history, holiday_dates, error_msg = get_model_and_data()

# 에러 처리
if error_msg:
    st.error(f"❌ 데이터 로딩 및 모델 학습 실패: {error_msg}")
    st.info("기존 ML 학습 스크립트를 먼저 실행하여 서울 공공자전거 통합 데이터를 구성해 주십시오.")
    st.stop()


# =====================================================================
# 3. 사이드바 제어 패널 (Weather & Date Inputs)
# =====================================================================
st.sidebar.markdown("### ⛅ 기상 및 시뮬레이션 설정")

# 1) 날짜 관련 정보
sim_date = st.sidebar.date_input("🗓️ 예측 대상 날짜", value=pd.Timestamp.now().date())
sim_date_ts = pd.to_datetime(sim_date)

# 2) 기온 시뮬레이션
mean_temp = st.sidebar.slider("🌡️ 평균 기온 (°C)", -20.0, 40.0, 15.0, 0.1)
min_temp = st.sidebar.slider("🥶 최저 기온 (°C)", -25.0, 30.0, mean_temp - 5.0, 0.1)
max_temp = st.sidebar.slider("🥵 최고 기온 (°C)", -10.0, 45.0, mean_temp + 5.0, 0.1)

# 3) 강수 및 기타 기상 변수
rain = st.sidebar.slider("☔ 일강수량 (mm)", 0.0, 150.0, 0.0, 0.5)
wind_avg = st.sidebar.slider("💨 평균 풍속 (m/s)", 0.0, 10.0, 2.5, 0.1)
wind_max = st.sidebar.slider("🌪️ 최대 풍속 (m/s)", 0.0, 15.0, wind_avg + 2.0, 0.1)
sun_hours = st.sidebar.slider("☀️ 합계 일조시간 (hr)", 0.0, 14.0, 6.0, 0.1)
solar_rad = st.sidebar.slider("⚡ 합계 일사량 (MJ/m²)", 0.0, 32.0, 14.0, 0.1)
snow = st.sidebar.slider("❄️ 적설량 (cm)", 0.0, 30.0, 0.0, 0.1)


# =====================================================================
# 4. 실시간 예측 연산 및 파생변수 자동 매핑
# =====================================================================
month = sim_date_ts.month
day_of_week = sim_date_ts.weekday()
is_weekend_val = 1 if day_of_week in [5, 6] else 0
day_of_year_val = sim_date_ts.dayofyear
week_of_year_val = int(sim_date_ts.isocalendar()[1])
is_holiday_val = 1 if sim_date_ts in holiday_dates else 0

# 입력 데이터를 DataFrame 형태로 맵핑
input_data = pd.DataFrame([{
    "평균기온": mean_temp,
    "최고기온": max_temp,
    "최저기온": min_temp,
    "강수량": rain,
    "최대풍속": wind_max,
    "평균풍속": wind_avg,
    "일조": sun_hours,
    "일사": solar_rad,
    "적설량": snow,
    "월": month,
    "요일": day_of_week,
    "is_weekend": is_weekend_val,
    "day_of_year": day_of_year_val,
    "week_of_year": week_of_year_val,
    "is_holiday": is_holiday_val
}])[features]

# 랜덤포레스트 수요 예측 실행
predicted_demand = int(model.predict(input_data)[0])


# =====================================================================
# 5. 메인 대시보드 화면 렌더링
# =====================================================================
st.title("🚲 서울 따릉이 일별 대여 수요 실시간 예측 대시보드")
st.markdown("---")

col1, col2 = st.columns([1, 1.5], gap="large")

# ----------------- Col 1: 예측 KPI 및 날씨 정보 가이드 -----------------
with col1:
    st.subheader("🎯 대여 수요 예측 결과")
    
    # Glow KPI Card
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">선택한 날씨 조건 기반 예상 수요</div>
        <div class="kpi-value">{predicted_demand:,}<span class="kpi-unit">대</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 평균 대여량 대비 비교
    historical_avg = int(df_history["이용건수"].mean())
    diff = predicted_demand - historical_avg
    diff_percent = (diff / historical_avg) * 100
    
    if diff >= 0:
        st.markdown(f"📈 과거 일평균 대여량(**{historical_avg:,}대**) 대비 약 **{diff_percent:.1f}% 증가**할 것으로 예상됩니다.")
    else:
        st.markdown(f"📉 과거 일평균 대여량(**{historical_avg:,}대**) 대비 약 **{abs(diff_percent):.1f}% 감소**할 것으로 예상됩니다.")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 날씨 & 날짜 정보 요약 가이드
    st.subheader("💡 대여 수요 요인 분석 가이드")
    
    # 가이드 1: 주말 / 평일
    weekend_desc = "주말(토/일)로 여가 및 공원 나들이 목적의 대여 증가 요인이 존재합니다." if is_weekend_val else "평일로 직장인 출퇴근 및 등하교용 생활 밀착형 대여가 주를 이룰 것입니다."
    st.markdown(f"""
    <div class="info-card">
        <div class="info-title">📅 주중/주말 여부 : {"주말" if is_weekend_val else "평일"}</div>
        <div class="info-content">{weekend_desc}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 가이드 2: 공휴일
    if is_holiday_val:
        st.markdown(f"""
        <div class="info-card" style="border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.05);">
            <div class="info-title" style="color: #F87171;">🎉 공휴일 여부 : 공휴일 지정일</div>
            <div class="info-content">공휴일입니다! 야외 활동 대여량은 폭증하지만, 일반 출퇴근 대여는 급감하는 경향을 보입니다.</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 가이드 3: 비/눈 정보
    if rain > 0:
        st.markdown(f"""
        <div class="info-card" style="border-color: rgba(59, 130, 246, 0.4); background: rgba(59, 130, 246, 0.05);">
            <div class="info-title" style="color: #60A5FA;">☔ 강우 주의보 : {rain} mm</div>
            <div class="info-content">비가 예보되어 노면이 미끄러워집니다. 자전거 대여 건수가 평소 대비 급락할 확률이 높습니다.</div>
        </div>
        """, unsafe_allow_html=True)
    if snow > 0:
        st.markdown(f"""
        <div class="info-card" style="border-color: rgba(255, 255, 255, 0.4); background: rgba(255, 255, 255, 0.05);">
            <div class="info-title" style="color: #F8FAFC;">❄️ 적설 주의보 : {snow} cm</div>
            <div class="info-content">눈이 쌓여 빙판길이 우려됩니다. 안전상의 이유로 대여 수요가 급감합니다.</div>
        </div>
        """, unsafe_allow_html=True)


# ----------------- Col 2: 시뮬레이션 및 모델 리포트 -----------------
with col2:
    st.subheader("📊 시각적 예측 시뮬레이션")
    
    tab1, tab2, tab3 = st.tabs(["🌡️ 기온별 수요 변화", "🔑 중요 피처 기여도", "📋 ML 모델 평가표"])
    
    # Tab 1: 기온 변화에 따른 예측 수요선
    with tab1:
        st.markdown("##### 기온 변동에 따른 대여량 민감도 시뮬레이션 (기타 조건 고정)")
        
        # 기온 변화 시뮬레이션 데이터 준비
        temp_range = np.linspace(-15, 38, 54)
        sim_df = pd.DataFrame([input_data.iloc[0].copy() for _ in temp_range])
        sim_df["평균기온"] = temp_range
        sim_df["최고기온"] = temp_range + 5.0
        sim_df["최저기온"] = temp_range - 5.0
        
        sim_predictions = model.predict(sim_df[features])
        
        # Plotly 또는 Matplotlib 시각화
        fig, ax = plt.subplots(figsize=(8, 4), facecolor="#0E1117")
        ax.set_facecolor("#1E293B")
        
        # 한국어 폰트 설정 우회 (글자 깨짐 방지)
        system = platform.system()
        if system == "Windows":
            plt.rcParams["font.family"] = "Malgun Gothic"
        elif system == "Darwin":
            plt.rcParams["font.family"] = "AppleGothic"
        
        ax.plot(temp_range, sim_predictions, color="#10B981", linewidth=3, label="예상 대여량")
        ax.scatter([mean_temp], [predicted_demand], color="#EF4444", s=150, zorder=5, label="현재 설정 기온")
        
        ax.set_title("기온에 따른 수요 곡선 시뮬레이션", color="#F8FAFC", fontsize=12, pad=10)
        ax.set_xlabel("평균 기온 (°C)", color="#94A3B8")
        ax.set_ylabel("예상 대여량 (대)", color="#94A3B8")
        ax.tick_params(colors="#94A3B8")
        ax.grid(True, color="#334155", linestyle="--", alpha=0.5)
        ax.legend(facecolor="#0E1117", edgecolor="#334155", labelcolor="#F8FAFC")
        
        st.pyplot(fig)
        
    # Tab 2: Feature Importance
    with tab2:
        st.markdown("##### 랜덤포레스트 모델의 기상 요인별 중요도 기여 수준")
        
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        fig, ax = plt.subplots(figsize=(8, 4.2), facecolor="#0E1117")
        ax.set_facecolor("#1E293B")
        
        # 한글 폰트 설정
        if system == "Windows":
            plt.rcParams["font.family"] = "Malgun Gothic"
        elif system == "Darwin":
            plt.rcParams["font.family"] = "AppleGothic"
            
        sns.barplot(
            x=[importances[i] for i in indices],
            y=[features[i] for i in indices],
            ax=ax,
            palette="viridis",
            hue=[features[i] for i in indices],
            legend=False
        )
        
        ax.set_title("피처(Feature) 중요도 분석 리포트", color="#F8FAFC", fontsize=12, pad=10)
        ax.set_xlabel("기여 가중치 비율", color="#94A3B8")
        ax.tick_params(colors="#94A3B8")
        ax.grid(True, color="#334155", linestyle="--", alpha=0.3, axis="x")
        
        st.pyplot(fig)
        
    # Tab 3: Model Performance
    with tab3:
        st.markdown("##### 기학습된 머신러닝 알고리즘 모델 성능 지표 리포트")
        comparison_path = "output_data/model_comparison.csv"
        
        if os.path.exists(comparison_path):
            performance_df = pd.read_csv(comparison_path)
            st.dataframe(performance_df.style.format({
                "R2": "{:.4f}",
                "MSE": "{:,.0f}",
                "RMSE": "{:,.1f}",
                "MAE": "{:,.1f}"
            }))
            st.caption("※ Scikit-Learn을 통해 훈련된 알고리즘의 R2(결정계수) 기준 정렬 스탯입니다.")
        else:
            st.info("모델 분석 표인 `output_data/model_comparison.csv` 파일이 부재합니다. Jupyter 스크립트를 최초 1회 전체 돌려 주십시오.")
