# -*- coding: utf-8 -*-
"""
제주도 카페 검색 지도 웹앱
- 데이터: 소상공인시장진흥공단 상가(상권)정보 (제주상권.csv)
- 카페(상권업종 소분류 '카페', '독서실/스터디 카페')만 추출하여 지도에 시각화
"""

import pandas as pd
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

CSV_PATH = "제주상권.csv"

st.set_page_config(page_title="제주 카페 지도", page_icon="☕", layout="wide")


# ----------------------------------------------------------------------------
# 데이터 로드
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="데이터를 불러오는 중...")
def load_cafes(path: str) -> pd.DataFrame:
    usecols = [
        "상호명", "지점명",
        "상권업종중분류명", "상권업종소분류명",
        "시군구명", "행정동명", "법정동명",
        "지번주소", "도로명주소", "건물명",
        "경도", "위도",
    ]
    df = pd.read_csv(path, encoding="cp949", usecols=usecols, low_memory=False)

    # 카페만 필터 (독서실/스터디 카페 제외)
    df = df[df["상권업종소분류명"] == "카페"].copy()

    # 위/경도 결측 및 이상치 제거 (제주도 대략 범위)
    df = df.dropna(subset=["위도", "경도"])
    df = df[
        df["위도"].between(33.0, 34.1) & df["경도"].between(126.0, 127.1)
    ]

    # 주소: 도로명 우선, 없으면 지번
    road = df["도로명주소"].astype(str).str.strip()
    df["주소"] = road.where(road.ne("") & road.ne("nan"), df["지번주소"])
    df["상호명"] = df["상호명"].fillna("(상호 미상)")
    df = df.reset_index(drop=True)
    return df


df = load_cafes(CSV_PATH)

# ----------------------------------------------------------------------------
# 사이드바 - 검색 / 필터
# ----------------------------------------------------------------------------
st.sidebar.header("🔎 검색 & 필터")

keyword = st.sidebar.text_input("카페 이름 검색", placeholder="예: 스타벅스, 감귤...")

sigungu_opts = ["전체"] + sorted(df["시군구명"].dropna().unique().tolist())
sigungu = st.sidebar.selectbox("시군구", sigungu_opts)

# 시군구 선택에 따라 행정동 옵션 갱신
dong_pool = df if sigungu == "전체" else df[df["시군구명"] == sigungu]
dong_opts = ["전체"] + sorted(dong_pool["행정동명"].dropna().unique().tolist())
dong = st.sidebar.selectbox("행정동", dong_opts)

max_markers = st.sidebar.slider(
    "지도 표시 최대 개수", min_value=100, max_value=3500, value=1000, step=100,
    help="너무 많으면 지도가 느려질 수 있어요.",
)

# ----------------------------------------------------------------------------
# 필터 적용
# ----------------------------------------------------------------------------
fdf = df
if keyword.strip():
    fdf = fdf[fdf["상호명"].astype(str).str.contains(keyword.strip(), case=False, na=False)]
if sigungu != "전체":
    fdf = fdf[fdf["시군구명"] == sigungu]
if dong != "전체":
    fdf = fdf[fdf["행정동명"] == dong]

# ----------------------------------------------------------------------------
# 헤더 & 지표
# ----------------------------------------------------------------------------
st.title("☕ 제주도 카페 검색 지도")
st.caption("소상공인시장진흥공단 상가(상권)정보 기반 · 제주 카페 데이터")

c1, c2, c3 = st.columns(3)
c1.metric("전체 카페 수", f"{len(df):,}")
c2.metric("검색 결과", f"{len(fdf):,}")
c3.metric("지도 표시", f"{min(len(fdf), max_markers):,}")

# ----------------------------------------------------------------------------
# 지도
# ----------------------------------------------------------------------------
if len(fdf) == 0:
    st.warning("검색 조건에 맞는 카페가 없습니다. 필터를 변경해 보세요.")
else:
    map_df = fdf.head(max_markers)

    center = [map_df["위도"].mean(), map_df["경도"].mean()]
    zoom = 11 if (sigungu == "전체" and dong == "전체") else 13

    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")
    cluster = MarkerCluster().add_to(m)

    for row in map_df.itertuples(index=False):
        name = getattr(row, "상호명")
        addr = getattr(row, "주소")
        popup_html = (
            f"<b>{name}</b><br>"
            f"<span style='color:#666'>☕ 카페</span><br>"
            f"{addr}"
        )
        folium.Marker(
            location=[getattr(row, "위도"), getattr(row, "경도")],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=name,
            icon=folium.Icon(color="green", icon="coffee", prefix="fa"),
        ).add_to(cluster)

    st_folium(m, use_container_width=True, height=560, returned_objects=[])

# ----------------------------------------------------------------------------
# 결과 테이블
# ----------------------------------------------------------------------------
with st.expander(f"📋 검색 결과 목록 ({len(fdf):,}개)", expanded=False):
    st.dataframe(
        fdf[["상호명", "시군구명", "행정동명", "주소"]].reset_index(drop=True),
        use_container_width=True,
        height=400,
    )

    csv_bytes = (
        fdf[["상호명", "시군구명", "행정동명", "주소", "위도", "경도"]]
        .to_csv(index=False)
        .encode("utf-8-sig")
    )
    st.download_button(
        "결과 CSV 다운로드", data=csv_bytes,
        file_name="제주카페_검색결과.csv", mime="text/csv",
    )
