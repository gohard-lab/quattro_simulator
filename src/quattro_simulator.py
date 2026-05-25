import streamlit as st
import matplotlib.pyplot as plt
import json
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

from tracker_web import log_app_usage

# 💡 한글 폰트 깨짐 방지 설정
# plt.rc('font', family='Malgun Gothic')
# plt.rcParams['axes.unicode_minus'] = False

# 1. 폰트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(current_dir, "NanumGothic.ttf")

# 2. ★ 핵심 추가: Matplotlib 시스템 메모리에 이 폰트를 강제로 밀어 넣습니다!
fm.fontManager.addfont(font_path)

# 3. 주입된 폰트의 이름을 가져와서 기본 폰트로 확정
font_name = fm.FontProperties(fname=font_path).get_name()
plt.rc('font', family=font_name)
plt.rcParams['axes.unicode_minus'] = False



# --- 1. 기본 데이터 및 앱 환경 세팅 ---
st.set_page_config(page_title="접지력 시뮬레이터", layout="centered")
st.title("🚗 콰트로 vs 후륜: 눈길 생존 시뮬레이터")

# 페이지 열림 로그 (Streamlit 세션 상태를 이용해 한 번만 기록)
if 'page_opened_logged' not in st.session_state:
    log_app_usage("quattro_simulator", "app_opened", details=json.dumps({"page": "main"}))
    st.session_state['page_opened_logged'] = True

# 💡 고정된 기준 데이터 설정 (그래프 스케일 유지용)
f1_score = 4.5  # (F1 레이스카 실제 한계치: 슬릭 타이어 + 무자비한 다운포스 모두 포함)
fixed_max_scale = 5.0  # 그래프의 고정 최대치를 처음부터 F1 스케일에 맞춰 거대하게 고정

# --- 2. 사용자 입력 UI (사이드바) ---
st.sidebar.header("주행 조건 설정")
# 💡 실시간 조작값(live_)과 버튼 클릭 확정값을 분리합니다.
live_drivetrain = st.sidebar.selectbox("구동 방식", ["후륜구동(RWD)", "사륜구동(AWD/Quattro)"])

# 💡 대중적이고 현실적인 타이어 라인업으로 세분화
live_tire_type = st.sidebar.selectbox(
    "타이어 종류", 
    [
        "익스트림 서머 (넥센 SUR4G, 한국 RS4 등)", 
        "UHP 서머 (미쉐린 PS4S, 피렐리 P Zero, 한국 evo2 등)", 
        "프리미엄 사계절 (미쉐린 MXM4, 금호 마제스티 TA91 등)", 
        "윈터 타이어 (브리지스톤 블리작, 한국 아이셉트 등)"
    ]
)
live_road_cond = st.sidebar.selectbox("노면 상태", ["마른 아스팔트", "빗길", "눈길"])

st.sidebar.markdown("---")
st.sidebar.subheader("🏁 에어로 다이나믹 효과")
# 에어로 효과는 버튼 클릭과 무관하게 누르는 즉시 실시간 반영됩니다.
# 💡 일반 고성능 양산차들의 평균적인 고속 다운포스 이득인 +0.15G를 적용합니다.
apply_aero = st.sidebar.checkbox("🌪️ 에어로 효과 활성화 (+0.15G)")

# 💡 시뮬레이션 실행 버튼: 누르는 순간의 값을 세션에 고정
if st.sidebar.button("결과 시뮬레이션"):
    st.session_state['simulated'] = True
    st.session_state['drivetrain'] = live_drivetrain
    st.session_state['tire_type'] = live_tire_type
    st.session_state['road_cond'] = live_road_cond
    log_app_usage("quattro_simulator", "simulate_clicked", details=json.dumps({"action": "button_clicked"}))


# --- 3. 물리 계산 로직 및 출력 ---
# 🚨 버튼을 한 번이라도 눌렀을 때만 아래 전체 로직과 화면이 출력됩니다.
if st.session_state.get('simulated', False):
    drivetrain = st.session_state['drivetrain']
    tire_type = st.session_state['tire_type']
    road_cond = st.session_state['road_cond']

    # 💡 세분화된 타이어별 마찰 계수 데이터베이스
    friction_map = {
        "익스트림 서머 (넥센 SUR4G, 한국 RS4 등)": {"마른 아스팔트": 1.2, "빗길": 0.6, "눈길": 0.1},
        "UHP 서머 (미쉐린 PS4S, 피렐리 P Zero, 한국 evo2 등)": {"마른 아스팔트": 1.1, "빗길": 0.8, "눈길": 0.15},
        "프리미엄 사계절 (미쉐린 MXM4, 금호 마제스티 TA91 등)": {"마른 아스팔트": 0.9, "빗길": 0.7, "눈길": 0.3},
        "윈터 타이어 (브리지스톤 블리작, 한국 아이셉트 등)": {"마른 아스팔트": 0.8, "빗길": 0.6, "눈길": 0.6}
    }

    base_mu = friction_map[tire_type][road_cond]
    drivetrain_bonus = 1.5 if drivetrain == "사륜구동(AWD/Quattro)" else 1.0
    traction_score = base_mu * drivetrain_bonus

    # 1. 현재 노면의 일반 기준 (해당 노면의 사계절 타이어 기준)
    current_standard_score = friction_map["프리미엄 사계절 (미쉐린 MXM4, 금호 마제스티 TA91 등)"][road_cond] * 1.0

    # 2. 현재 노면의 최악 조건 찾기 (상대 비교용)
    if road_cond == "눈길" or road_cond == "빗길":
        current_worst_score = friction_map["익스트림 서머 (넥센 SUR4G, 한국 RS4 등)"][road_cond] * 1.0
        worst_label = f"최악 (서머+{road_cond})"
    else:
        current_worst_score = friction_map["윈터 타이어 (브리지스톤 블리작, 한국 아이셉트 등)"][road_cond] * 1.0
        worst_label = f"최하 (윈터+{road_cond})"

    # 3. 절대 안전 기준점 (고정값: 마른 아스팔트 + 사계절 = 0.9)
    absolute_safe_line = 0.9

    # 💡 에어로 효과 적용 (체크박스 누르면 바로 실시간 계산되어 반영)
    base_f1_score = 1.7  # F1의 순수 타이어 접지력 (다운포스 없을 때)
    
    if apply_aero:
        traction_score += 0.15          # 내 차의 소박한 에어로 (+0.15G)
        f1_score = base_f1_score + 2.8  # 🚀 F1의 무자비한 다운포스 (+2.8G) 폭발!
    else:
        f1_score = base_f1_score        # 에어로를 끄면 F1도 순수 타이어 빨만 남음
        

    # --- 4. 시각화 및 결과 출력 ---
    
    # 타이어 마찰력(G) 계급표 UI
    st.markdown("""
    ### 🏁 물리적 타이어 마찰력(접지력) 계급표
    * **0.90 (일반 기준):** 평범한 승용차 + 사계절 타이어 (일상 주행)
    * **1.00 ~ 1.10:** 고성능 스포츠카 순정 서머 타이어 (예: 미쉐린 PS4S, 피렐리 P Zero)
    * **1.20 (공도 최고):** 트랙용 하이그립 타이어 (예: 넥센 SUR4G, 한국 RS4)
      > 💡 **1.20G의 의미:** 내 차 무게의 1.2배에 달하는 거대한 힘으로 차를 옆에서 밀어붙여도, 타이어가 미끄러지지 않고 버틴다는 뜻!
    * **4.00 ~ 5.00 (끝판왕):** F1 / 르망 24시 레이스카 
      > 🏎️ **넘사벽인 이유:** 순수 타이어 접지력(1.7G)에, 달릴 때 공기가 차체를 바닥으로 무자비하게 짓누르는 **'다운포스'**가 더해져 물리법칙을 파괴하는 수치가 나옵니다.
    ---
    """)

    # 결과 점수 subheader (현재 노면 기준점과 비교)
    st.subheader(f"💡 현재 조건 마찰력: {traction_score:.2f} (해당 노면 일반 승용차: {current_standard_score:.2f})")

    # 멘트 로직
    if road_cond == "눈길" and "서머" in tire_type:
        if drivetrain == "사륜구동(AWD/Quattro)":
            st.error("⚠️ 마찰력이 사실상 빙판길 수준입니다. 하지만 콰트로가 0.1%의 미세한 접지력을 쥐어짜며 차를 당겨냅니다. (와리가리 5번 주의!)")
        else:
            st.error("☠️ 제자리에서 바퀴만 헛돕니다. 중앙분리대와 키스하기 직전입니다. 차를 버리고 걸어가세요.")
    elif traction_score >= absolute_safe_line:
        st.success("🏁 일상 마른 노면 주행을 뛰어넘는 완벽한 그립입니다! 과감하게 엑셀을 밟으세요.")
    elif traction_score >= current_standard_score:
        st.warning("☔ 마찰력이 다소 떨어집니다. 콰트로라도 물리법칙을 무시할 순 없으니 감속하세요.")
    else:
        st.error("❄️ 매우 위험한 상태입니다. 극도로 주의하세요.")


    # --- 5. 고정 스케일 그래프 출력 ---
    fig, ax = plt.subplots(figsize=(8, 4))

    # Y축 항목과 수치 매칭 (노면에 따라 이름과 점수가 실시간 반영됨)
    categories = [worst_label, f"일반 기준 (사계절+{road_cond})", f"현재 세팅 ({drivetrain})", "끝판왕 (F1 레이스카)"]
    scores = [current_worst_score, current_standard_score, traction_score, f1_score]

    # 현재 세팅 점수에 따라 막대 색상 변경
    if traction_score >= absolute_safe_line:
        current_color = '#1f77b4' # 파랑 (완전 안전)
    elif traction_score >= current_standard_score:
        current_color = '#ff7f0e' # 주황 (주의)
    else:
        current_color = '#d62728' # 빨강 (위험)

    # F1은 끝판왕 전용 보라색(#9467bd)
    colors = ['#555555', '#888888', current_color, '#9467bd'] 

    ax.barh(categories, scores, color=colors)

    # X축 최대치를 처음부터 끝판왕(5.0)까지 고정
    ax.set_xlim(0, fixed_max_scale) 

    # 절대 변하지 않는 안전 기준선(0.9)을 빨간 점선으로 고정 출력
    ax.axvline(absolute_safe_line, color='red', linestyle='--', alpha=0.7, label=f'절대 안전 기준선 ({absolute_safe_line})')
    ax.legend(loc='lower right')

    # 화면에 그래프 출력
    st.pyplot(fig)

    # 에어로 효과 알림 (사용자 피드백용)
    if apply_aero:
        st.toast("🌪️ 초고속 주행으로 인한 에어로 효과(+0.15G)가 실시간 적용되었습니다!")
        
    # 조건 변경 시마다 로그 기록
    usage_details = {
        "drivetrain": drivetrain,
        "tire": tire_type,
        "road": road_cond,
        "traction_score": traction_score,
        "aero_applied": apply_aero
    }
    log_app_usage("quattro_simulator", "conditions_changed", details=json.dumps(usage_details))

else:
    # 앱 초기 실행 시 보여줄 안내 문구
    st.info("👈 좌측에서 주행 조건을 설정한 뒤, '결과 시뮬레이션' 버튼을 눌러주세요!")