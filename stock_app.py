import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from pykrx import stock

from api.auth import get_access_token


# =========================================================
# 1. 구글 시트 ID 설정
# =========================================================

SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SHEET_ID}/export?format=csv"
)


# =========================================================
# 2. 페이지 설정
# =========================================================

st.set_page_config(
    page_title="주식 동행",
    layout="wide"
)


# =========================================================
# 날짜 고정 설정
# =========================================================

BASE_DATE = "20260703"
END_DATE = "20260731"


# =========================================================
# 한국투자 OpenAPI 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

# Streamlit 파일이 프로젝트 루트에 있는 경우
ENV_PATH = BASE_DIR / "config" / ".env"

# Streamlit 파일이 하위 폴더에 있는 경우를 대비
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR.parent / "config" / ".env"

load_dotenv(ENV_PATH)

APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")

KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
CURRENT_PRICE_URL = (
    "/uapi/domestic-stock/v1/quotations/inquire-price"
)
CURRENT_PRICE_TR_ID = "FHKST01010100"


# =========================================================
# 숫자 변환
# =========================================================

def safe_int(value):
    try:
        return int(
            str(value)
            .replace(",", "")
            .strip()
            or 0
        )
    except (TypeError, ValueError):
        return 0


def safe_float(value):
    try:
        return float(
            str(value)
            .replace(",", "")
            .strip()
            or 0
        )
    except (TypeError, ValueError):
        return 0.0


# =========================================================
# 구글 시트 불러오기
# =========================================================

@st.cache_data(ttl=300)
def load_stock_list():
    """
    구글 시트 참가자 및 종목 목록 조회
    """

    df = pd.read_csv(SHEET_URL)

    df.columns = df.columns.str.strip()

    df = df.dropna(
        subset=["종목코드", "참가자"]
    )

    return df


# =========================================================
# 기준일 종가 전체 조회
# =========================================================

@st.cache_data
def get_base_price_map(target_date):
    """
    기준일의 코스피·코스닥 전체 종가를 한 번에 조회한다.

    기준일이 휴장일이면 최대 10일 전까지 확인하여
    가장 가까운 직전 거래일 종가를 사용한다.
    """

    target_datetime = datetime.strptime(
        target_date,
        "%Y%m%d"
    )

    for offset in range(10):

        search_date = (
            target_datetime
            - timedelta(days=offset)
        ).strftime("%Y%m%d")

        daily_map = {}

        for market in ["KOSPI", "KOSDAQ"]:

            try:
                market_df = (
                    stock.get_market_ohlcv_by_ticker(
                        search_date,
                        market=market
                    )
                )

                if (
                    market_df is None
                    or market_df.empty
                ):
                    continue

                for ticker, row in market_df.iterrows():

                    close_price = row.get(
                        "종가",
                        0
                    )

                    if (
                        pd.notna(close_price)
                        and close_price > 0
                    ):
                        daily_map[
                            str(ticker).zfill(6)
                        ] = int(close_price)

            except Exception:
                continue

        if daily_map:
            return daily_map

    return {}


# =========================================================
# 한국투자 현재가 조회
# =========================================================

@st.cache_data(ttl=60)
def get_kis_realtime_price(
    ticker,
    access_token
):
    """
    한국투자 OpenAPI 주식현재가 시세 조회

    반환값
    - 현재가
    - 전일 대비 등락률
    """

    if not APP_KEY or not APP_SECRET:
        raise RuntimeError(
            "APP_KEY 또는 APP_SECRET이 없습니다. "
            "config/.env 파일을 확인하세요."
        )

    headers = {
        "content-type":
            "application/json; charset=utf-8",
        "authorization":
            f"Bearer {access_token}",
        "appkey":
            APP_KEY,
        "appsecret":
            APP_SECRET,
        "tr_id":
            CURRENT_PRICE_TR_ID,
        "custtype":
            "P",
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": ticker,
    }

    last_error = None

    # 일시적인 호출 제한이나 통신 오류에 대비하여 재시도
    for attempt in range(3):

        try:
            response = requests.get(
                KIS_BASE_URL
                + CURRENT_PRICE_URL,
                headers=headers,
                params=params,
                timeout=10,
            )

            if response.status_code == 401:
                raise RuntimeError(
                    "한국투자 접근토큰 인증에 "
                    "실패했습니다."
                )

            if response.status_code == 429:
                time.sleep(
                    0.4 * (attempt + 1)
                )
                continue

            response.raise_for_status()

            result = response.json()

            if result.get("rt_cd") != "0":

                message_code = result.get(
                    "msg_cd",
                    ""
                )

                message = result.get(
                    "msg1",
                    "현재가 조회 실패"
                )

                last_error = RuntimeError(
                    f"{ticker} 현재가 조회 실패: "
                    f"{message_code} / {message}"
                )

                # 초당 호출 제한 응답이면 잠시 후 재시도
                if (
                    "초당" in message
                    or "EGW00201" in message_code
                ):
                    time.sleep(
                        0.4 * (attempt + 1)
                    )
                    continue

                raise last_error

            output = result.get(
                "output",
                {}
            )

            current_price = safe_int(
                output.get("stck_prpr")
            )

            day_rate = safe_float(
                output.get("prdy_ctrt")
            )

            if current_price <= 0:
                return None, 0.0

            return current_price, day_rate

        except requests.RequestException as error:
            last_error = error
            time.sleep(
                0.3 * (attempt + 1)
            )

    if last_error:
        raise RuntimeError(
            f"{ticker} 현재가 통신 오류: "
            f"{last_error}"
        )

    return None, 0.0


# =========================================================
# 종목명 자동 조회
# =========================================================

@st.cache_data
def get_stock_name_auto(ticker):
    try:
        name = stock.get_market_ticker_name(
            ticker
        )

        return (
            name
            if name
            else "종목정보없음"
        )

    except Exception:
        return "코드오류"


# =========================================================
# 종목별 데이터 조회
# =========================================================

def fetch_single_ticker_data(
    ticker,
    base_price_map,
    access_token
):
    """
    한 종목의 기준가, 현재가, 당일 등락률,
    자동 종목명을 조합한다.
    """

    try:
        base_p = base_price_map.get(
            ticker
        )

        curr_p, day_rate = (
            get_kis_realtime_price(
                ticker,
                access_token
            )
        )

        auto_name = get_stock_name_auto(
            ticker
        )

        current_date = (
            datetime.now()
            .strftime("%Y.%m.%d")
        )

        if base_p and curr_p:

            return {
                "ticker": ticker,
                "기준가": base_p,
                "현재가": curr_p,
                "당일등락률": day_rate,
                "업데이트날짜": current_date,
                "auto_name": auto_name,
            }

    except Exception:
        return None

    return None


# =========================================================
# 상단 타이틀
# =========================================================

st.title("🧭 주식 동행")


# =========================================================
# 실시간 갱신 버튼
# =========================================================

if st.button("🔄 실시간 시세 갱신"):

    # 현재가 캐시만 삭제
    get_kis_realtime_price.clear()

    st.rerun()


# =========================================================
# 상단 안내 박스
# =========================================================

st.markdown(
    f"""
    <div style='
        padding:20px;
        background-color:#ffffff;
        border-radius:15px;
        border:1px solid #dee2e6;
        box-shadow:0 4px 6px rgba(0,0,0,0.05);
        margin-bottom:20px;
    '>

        <h4 style='
            color:#1a3a5f;
            margin-top:0;
            font-size:1.2rem;
        '>
            🧭 주식 동행 : 정보 상황판
        </h4>

        <p style='
            color:#333;
            font-size:1rem;
            line-height:1.6;
        '>

            <span style='
                font-weight:bold;
                font-size:1.05rem;
            '>
                "나누는 지식은 투자의 눈을 밝히고,
                <br>
                함께하는 동행은 수익의 뿌리를 깊게 합니다."
            </span>

            <br>

            <span style='
                color:#666;
                font-size:0.9rem;
            '>
                {BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]}
                부터 현재까지의 기록입니다.
            </span>

        </p>

        <div style='
            border-top:1px solid #eee;
            padding-top:10px;
            margin-top:10px;
        '>

            <p style='
                color:#e74c3c;
                font-size:0.85rem;
                font-weight:bold;
                margin-bottom:0;
            '>
                ⚠️ [주의] 본 데이터는 한국투자증권 OpenAPI 정보를
                기반으로 한 정보 공유용이며,
                모든 투자의 책임은 본인에게 있습니다.
            </p>

        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 데이터 처리
# =========================================================

try:

    # -----------------------------------------------------
    # 한국투자 토큰 확인
    # -----------------------------------------------------

    access_token = get_access_token()


    # -----------------------------------------------------
    # 구글 시트 데이터 조회
    # -----------------------------------------------------

    df_list = load_stock_list()

    df_list.columns = (
        df_list.columns
        .str.strip()
    )

    df_list = df_list.dropna(
        subset=["종목코드", "참가자"]
    )


    # -----------------------------------------------------
    # 중복되지 않은 종목코드 추출
    # -----------------------------------------------------

    unique_tickers = [
        str(t)
        .strip()
        .split(".")[0]
        .zfill(6)

        for t in df_list[
            "종목코드"
        ].unique()
    ]


    # -----------------------------------------------------
    # 기준일 전체 종가 일괄 조회
    # -----------------------------------------------------

    base_price_map = get_base_price_map(
        BASE_DATE
    )


    # -----------------------------------------------------
    # 한국투자 현재 시세 병렬 조회
    # -----------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=8
    ) as executor:

        price_results = list(
            executor.map(
                lambda ticker:
                fetch_single_ticker_data(
                    ticker,
                    base_price_map,
                    access_token
                ),
                unique_tickers
            )
        )


    # -----------------------------------------------------
    # 종목코드별 가격 데이터 변환
    # -----------------------------------------------------

    price_map = {
        result["ticker"]: result

        for result in price_results

        if result is not None
    }


    # -----------------------------------------------------
    # 참가자별 최종 결과 구성
    # -----------------------------------------------------

    final_results = []

    for _, row in df_list.iterrows():

        ticker = (
            str(row["종목코드"])
            .strip()
            .split(".")[0]
            .zfill(6)
        )

        p_data = price_map.get(
            ticker
        )

        if p_data:

            raw_name = row.get(
                "종목명",
                ""
            )

            if (
                pd.notna(raw_name)
                and str(raw_name).strip() != ""
            ):
                display_name = raw_name

            else:
                display_name = p_data[
                    "auto_name"
                ]

            base_p = p_data["기준가"]
            curr_p = p_data["현재가"]

            rate = round(
                (
                    (curr_p - base_p)
                    / base_p
                ) * 100,
                2
            )

            final_results.append(
                {
                    "참가자": row["참가자"],
                    "종목명": display_name,
                    "ticker": ticker,
                    "기준가": base_p,
                    "현재가": curr_p,
                    "등락": curr_p - base_p,
                    "수익률": rate,
                    "당일등락률": p_data[
                        "당일등락률"
                    ],
                    "업데이트날짜": p_data[
                        "업데이트날짜"
                    ],
                }
            )


    # =====================================================
    # 결과 테이블 표시
    # =====================================================

    if final_results:

        data = pd.DataFrame(
            final_results
        ).sort_values(
            by="수익률",
            ascending=False
        ).reset_index(
            drop=True
        )

        data["rank"] = data[
            "수익률"
        ].rank(
            method="min",
            ascending=False
        ).astype(int)


        # -------------------------------------------------
        # HTML 테이블 행 생성
        # -------------------------------------------------

        table_rows = ""

        for _, row in data.iterrows():

            rank = row["rank"]
            ticker = row["ticker"]
            day_rate = row[
                "당일등락률"
            ]


            # ---------------------------------------------
            # 상위 3위 메달 표시
            # ---------------------------------------------

            if rank in [1, 2, 3]:

                medal_icon = [
                    "🥇",
                    "🥈",
                    "🥉"
                ][rank - 1]

                rank_disp = f"""
                <div style="
                    position:relative;
                    display:inline-block;
                    width:45px;
                    text-align:center;
                ">

                    <span style="
                        font-size:1rem;
                        color:#333;
                        font-weight:bold;
                        position:relative;
                        z-index:1;
                    ">
                        {rank}위
                    </span>

                    <span style="
                        font-size:1.35rem;
                        position:absolute;
                        top:-28px;
                        left:10px;
                        z-index:2;
                        opacity:0.85;
                    ">
                        {medal_icon}
                    </span>

                </div>
                """

            else:

                rank_disp = f"""
                <span style="
                    font-size:1rem;
                    color:#333;
                    font-weight:bold;
                ">
                    {rank}위
                </span>
                """


            # ---------------------------------------------
            # 누적 수익률 색상 설정
            # ---------------------------------------------

            if row["수익률"] > 0:

                color = "color:#e74c3c;"
                icon = "▲"
                prefix = "+"

            elif row["수익률"] < 0:

                color = "color:#3498db;"
                icon = "▼"
                prefix = ""

            else:

                color = "color:#333;"
                icon = ""
                prefix = ""


            # ---------------------------------------------
            # 당일 등락률 색상 설정
            # ---------------------------------------------

            if day_rate > 0:

                d_color = "#e74c3c"
                d_icon = "▲"

            elif day_rate < 0:

                d_color = "#3498db"
                d_icon = "▼"

            else:

                d_color = "#333"
                d_icon = ""


            # ---------------------------------------------
            # 네이버 증권 바로가기
            # ---------------------------------------------

            naver_url = (
                "https://finance.naver.com/"
                f"item/main.naver?code={ticker}"
            )


            # ---------------------------------------------
            # 테이블 행 추가
            # ---------------------------------------------

            table_rows += f"""
            <tr style="font-size:0.95rem;">

                <td style="
                    padding:10px 2px;
                    border-bottom:1px solid #eee;
                    font-weight:bold;
                ">
                    {rank_disp}
                </td>

                <td style="
                    padding:10px 5px;
                    border-bottom:1px solid #eee;
                    font-weight:bold;
                    color:#333;
                ">
                    {row['참가자']}
                </td>

                <td style="
                    padding:10px 10px;
                    border-bottom:1px solid #eee;
                    text-align:center;
                ">

                    <a
                        href="{naver_url}"
                        target="_blank"
                        style="
                            text-decoration:none;
                            color:inherit;
                        "
                    >

                        <div style="
                            font-size:1.04rem;
                            font-weight:bold;
                            color:#000;
                            margin-bottom:5px;
                            cursor:pointer;
                        ">
                            {row['종목명']}
                        </div>

                    </a>

                    <div
                        class="pc-only"
                        style="
                            font-size:0.85rem;
                            color:{d_color};
                            font-weight:bold;
                            margin-top:-2px;
                        "
                    >
                        ({d_icon}{abs(day_rate):.2f}%)
                    </div>

                    <div
                        class="mobile-only"
                        style="
                            font-size:0.72rem;
                            color:#555;
                            line-height:1.4;
                            font-weight:normal;
                            text-align:left;
                            display:inline-block;
                            width:100%;
                            max-width:120px;
                        "
                    >

                        <div style="
                            display:table;
                            width:100%;
                        ">

                            <div style="
                                display:table-row;
                            ">

                                <div style="
                                    display:table-cell;
                                ">
                                    기준가:
                                </div>

                                <div style="
                                    display:table-cell;
                                    text-align:right;
                                ">
                                    {row['기준가']:,.0f}원
                                </div>

                            </div>

                            <div style="
                                display:table-row;
                                color:#333;
                                font-weight:bold;
                            ">

                                <div style="
                                    display:table-cell;
                                ">
                                    현재가:
                                </div>

                                <div style="
                                    display:table-cell;
                                    text-align:right;
                                ">
                                    {row['현재가']:,.0f}원
                                </div>

                            </div>

                            <div style="
                                display:table-row;
                                {color}
                            ">

                                <div style="
                                    display:table-cell;
                                ">
                                    등락:
                                </div>

                                <div style="
                                    display:table-cell;
                                    text-align:right;
                                ">
                                    {icon}{abs(row['등락']):,.0f}원
                                </div>

                            </div>

                        </div>

                    </div>

                </td>

                <td
                    class="pc-only"
                    style="
                        padding:10px 5px;
                        border-bottom:1px solid #eee;
                        color:#888;
                    "
                >
                    {row['기준가']:,.0f}원
                </td>

                <td
                    class="pc-only"
                    style="
                        padding:10px 5px;
                        border-bottom:1px solid #eee;
                        font-weight:bold;
                    "
                >
                    {row['현재가']:,.0f}원
                </td>

                <td
                    class="pc-only"
                    style="
                        padding:10px 5px;
                        border-bottom:1px solid #eee;
                        {color}
                        font-weight:bold;
                    "
                >
                    {icon} {abs(row['등락']):,.0f}원
                </td>

                <td style="
                    padding:12px 5px;
                    border-bottom:1px solid #eee;
                    {color}
                    font-weight:bold;
                    font-size:1.05rem;
                ">
                    {prefix}{row['수익률']:.2f}%
                </td>

            </tr>
            """


        # =================================================
        # 반응형 테이블 출력
        # =================================================

        st.markdown(
            f"""
            <style>

                .mobile-only {{
                    display:none !important;
                }}

                .pc-only {{
                    display:none !important;
                }}

                @media (min-width:801px) {{

                    .pc-only {{
                        display:table-cell !important;
                    }}

                    div.pc-only {{
                        display:block !important;
                    }}

                }}

                @media (max-width:800px) {{

                    .mobile-only {{
                        display:block !important;
                    }}

                    thead tr {{
                        font-size:1rem !important;
                    }}

                }}

            </style>

            <div style="
                width:100%;
                background:white;
                border-radius:12px;
                overflow:hidden;
                border:1px solid #eee;
            ">

                <table style="
                    width:100%;
                    border-collapse:collapse;
                    text-align:center;
                    table-layout:fixed;
                ">

                    <thead>

                        <tr style="
                            background-color:#1a3a5f;
                            color:white;
                            font-size:1.2rem;
                        ">

                            <th style="
                                width:10%;
                                padding:15px 2px;
                            ">
                                순위
                            </th>

                            <th style="width:17%;">
                                참가자
                            </th>

                            <th style="width:30%;">

                                <div>
                                    종목 정보
                                </div>

                                <div
                                    class="pc-only"
                                    style="
                                        font-size:0.8rem;
                                        font-weight:normal;
                                        opacity:0.8;
                                        margin-top:2px;
                                    "
                                >
                                    (당일등락률)
                                </div>

                            </th>

                            <th
                                class="pc-only"
                                style="width:15%;"
                            >
                                기준가
                            </th>

                            <th
                                class="pc-only"
                                style="width:15%;"
                            >
                                현재가
                            </th>

                            <th
                                class="pc-only"
                                style="width:15%;"
                            >
                                등락
                            </th>

                            <th style="width:18%;">
                                수익률
                            </th>

                        </tr>

                    </thead>

                    <tbody>
                        {table_rows}
                    </tbody>

                </table>

            </div>
            """,
            unsafe_allow_html=True
        )


        st.success(
            "✅ 한국투자증권 OpenAPI 시세 반영 완료 "
            f"({data['업데이트날짜'].iloc[0]})"
        )

    else:

        st.warning(
            "표시할 종목 시세 데이터가 없습니다."
        )


except Exception as e:

    st.error(
        f"오류 발생: {e}"
    )


# =========================================================
# 하단 데이터 산출 가이드
# =========================================================

st.markdown("---")

st.markdown(
    f"""
    <div style='
        background-color:#ffffff;
        padding:25px;
        border-radius:10px;
        border:1px solid #dee2e6;
        box-shadow:0 2px 4px rgba(0,0,0,0.05);
    '>

        <h3 style='
            color:#1a3a5f;
            margin-top:0;
            margin-bottom:20px;
            border-bottom:2px solid #1a3a5f;
            padding-bottom:10px;
        '>
            🧭 데이터 산출 가이드
        </h3>

        <p style='
            font-size:0.95rem;
            line-height:1.8;
            color:#333;
            margin:0;
        '>

            <b>1. 데이터 기준 및 출처</b>
            <br>

            - 본 시스템은 한국투자증권 OpenAPI의
            국내주식 현재가 시세를 참조합니다.
            <br>

            - 자료 출처: 한국투자증권 OpenAPI
            <br><br>


            <b>2. 휴일 및 비영업일 데이터 반영</b>
            <br>

            - 시장 휴장일(토, 일, 공휴일)에는 데이터가
            업데이트되지 않으며, 직전 거래일 종가로 산출됩니다.
            <br>

            - 반영 기간:
            {BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]}
            ~
            {END_DATE[:4]}.{END_DATE[4:6]}.{END_DATE[6:]}
            <br><br>


            <b>3. 장중 데이터와 장마감 데이터의 차이</b>
            <br>

            - 장중(09:00~15:30): 한국투자증권 OpenAPI
            현재가 시세를 바탕으로 수익률을 계산합니다.
            <br>

            - 장마감 후: 당일 최종 확정된 정규장 종가
            (15:30)를 기준으로 데이터가 고정됩니다.
            <br><br>


            <b>4. 실시간 데이터 오차 안내</b>
            <br>

            - 증권사 시스템과 실제 HTS 화면 사이에는
            통신 및 화면 갱신 시점에 따른 미세한 차이가
            발생할 수 있습니다.
            <br><br>


            <b>5. 업데이트 및 순위 산정</b>
            <br>

            - 본 페이지는 사용자가 새로고침(F5)을 할 때
            최신 데이터를 수집하여 반영합니다.
            <br>

            - 시작일 기준가 대비 현재가 수익률로
            실시간 순위가 결정됩니다.
            <br><br>


            <span style='
                color:#e74c3c;
                font-weight:bold;
            '>
                ⚠️ [주의] 본 데이터는 정보 공유를 목적으로 하며,
                모든 투자의 책임은 본인에게 있습니다.
            </span>

            <br>

            <span style='
                color:#888;
                font-size:0.85rem;
                display:block;
                margin-top:10px;
            '>
                * 시스템 수정 및 기술 문의: 푸른돌디
            </span>

        </p>

    </div>
    """,
    unsafe_allow_html=True
