import streamlit as st
import json
import os
import random
import requests
from datetime import datetime, timedelta

# ----------------------------
# 기본 설정
# ----------------------------
st.set_page_config(page_title="오늘 뭐 먹지", page_icon="🍱")

HISTORY_FILE = "history.json"
RECENT_DAYS = 7  # 최근 며칠간 먹은 메뉴는 추천에서 제외할지

MENU_DB = {
    "한식": ["김치찌개", "된장찌개", "비빔밥", "제육볶음", "불고기", "갈비탕", "순두부찌개", "냉면", "삼겹살", "닭갈비"],
    "중식": ["짜장면", "짬뽕", "마라탕", "탕수육", "마파두부", "양꼬치"],
    "일식": ["초밥", "라멘", "돈카츠", "우동", "규동", "오니기리"],
    "양식": ["파스타", "피자", "리조또", "스테이크", "샌드위치", "햄버거"],
    "분식": ["떡볶이", "김밥", "라볶이", "순대", "튀김"],
}

# 카카오 API 키는 코드에 직접 적지 않고 secrets로 관리
# .streamlit/secrets.toml 파일에 KAKAO_API_KEY = "본인키" 형태로 저장
KAKAO_API_KEY = st.secrets.get("KAKAO_API_KEY", "")


# ----------------------------
# 최근 메뉴 기록 불러오기 / 저장하기
# ----------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_recent_menus(history, days=RECENT_DAYS):
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for item in history:
        item_date = datetime.fromisoformat(item["date"])
        if item_date >= cutoff:
            recent.append(item["menu"])
    return recent


def add_history(menu):
    history = load_history()
    history.append({"menu": menu, "date": datetime.now().isoformat()})
    save_history(history)


def remove_history_entry(index):
    history = load_history()
    if 0 <= index < len(history):
        history.pop(index)
        save_history(history)


# ----------------------------
# 추천 로직
# ----------------------------
def recommend_menu(categories, exclude_menus, n=3):
    candidates = []
    for cat in categories:
        candidates.extend(MENU_DB.get(cat, []))

    filtered = [m for m in candidates if m not in exclude_menus]

    if len(filtered) < n:
        filtered = candidates

    if not filtered:
        return []

    n = min(n, len(filtered))
    return random.sample(filtered, n)


# ----------------------------
# 카카오맵 맛집 검색
# ----------------------------
def search_restaurants(location, menu, size=3):
    if not KAKAO_API_KEY:
        return None  # 키 없으면 검색 자체를 스킵

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": f"{location} {menu}", "size": size}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        return data.get("documents", [])
    except Exception:
        return []


# ----------------------------
# 화면(UI)
# ----------------------------
st.title("🍱 오늘 뭐 먹지")
st.caption("최근에 먹은 메뉴는 빼고, 안 먹어본 메뉴 + 근처 맛집까지 추천해드려요.")

location = st.text_input("어느 지역에서 드세요? (예: 강남역, 판교역)", value="")

categories = st.multiselect(
    "어떤 종류 음식을 원하세요?",
    options=list(MENU_DB.keys()),
    default=list(MENU_DB.keys()),
)

if st.button("메뉴 추천 받기", type="primary"):
    history = load_history()
    recent_menus = get_recent_menus(history)
    results = recommend_menu(categories, recent_menus)

    if not results:
        st.warning("선택한 종류에 메뉴가 없어요. 다른 종류를 선택해보세요!")
    else:
        st.session_state["last_recommendation"] = results

if "last_recommendation" in st.session_state:
    st.subheader("오늘의 추천 메뉴")
    for menu in st.session_state["last_recommendation"]:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"- **{menu}**")
        with col2:
            if st.button("이거 먹었어요", key=f"eat_{menu}"):
                add_history(menu)
                st.success(f"'{menu}' 기록 완료! 다음 추천에서는 제외돼요.")

        # 카카오맵 맛집 검색 결과 표시
        if location:
            if not KAKAO_API_KEY:
                st.caption("(카카오 API 키가 설정되면 여기에 근처 맛집이 표시돼요)")
            else:
                places = search_restaurants(location, menu)
                if places:
                    with st.expander(f"'{location}' 근처 {menu} 맛집 보기"):
                        for p in places:
                            st.write(f"**{p['place_name']}** — {p['road_address_name'] or p['address_name']}")
                            if p.get("place_url"):
                                st.write(p["place_url"])
                elif places == []:
                    st.caption("근처에서 맛집을 찾지 못했어요.")

if location == "" and "last_recommendation" in st.session_state:
    st.info("지역을 입력하면 근처 맛집도 같이 보여드려요.")

st.divider()
st.subheader("최근 먹은 메뉴 기록")
history = load_history()
cutoff = datetime.now() - timedelta(days=RECENT_DAYS)

recent_entries = [
    (i, item) for i, item in enumerate(history)
    if datetime.fromisoformat(item["date"]) >= cutoff
]

if recent_entries:
    for original_index, item in recent_entries:
        col1, col2 = st.columns([4, 1])
        with col1:
            date_str = datetime.fromisoformat(item["date"]).strftime("%m/%d")
            st.write(f"{item['menu']} ({date_str})")
        with col2:
            if st.button("삭제", key=f"del_{original_index}"):
                remove_history_entry(original_index)
                st.rerun()
else:
    st.write("아직 기록된 메뉴가 없어요.")
