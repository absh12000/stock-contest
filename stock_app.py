import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 설정
st.set_page_config(page_title="주식 동행", layout="wide")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260504" 
END_DATE = "20260529"   

# [수동 새로고침 설정] 캐시 시간 제한(ttl)을 없애서 새로고침 시에만 업데이트
@st.cache_data
def get_safe_price(ticker, target_date):
    dt = datetime.strptime(target_date, "%Y%m%d")
    for i in range(10):
        check_date = (dt - timedelta(days=i)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv(check_date, check_date, ticker)
        if not df.empty:
            return df['종가'].iloc[-1], check_date
    return None, None

# [병렬 처리 함수] 종목코드 하나에 대해 가격 정보를 가져옴
def fetch_single_ticker_data(ticker, effective_end):
    base_p, _ = get_safe_price(ticker, BASE_DATE)
    curr_p, last_date = get_safe_price(ticker, effective_end)
    
    if base_p and curr_p:
        return {
            'ticker': ticker,
            '기준가': base_p,
            '현재가': curr_p,
            '최종날짜': last_date
        }
    return None

# 상단 타이틀
st.title("🧭 주식 동행")

st.markdown(f"""
    <div style='padding:20px; background-color:#ffffff; border-radius:15px; border:1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom:20px;'>
        <h4 style='color:#1a3a5f; margin-top:0; font-size:1.2rem;'>🧭 주식 동행 : 실전 정보 상황판</h4>
        <p style='color:#333; font-size:1rem; line-height:1.6;'>
            <span style='font-weight:bold; font-size:1.05rem;'> "나누는 지식은 투자의 눈을 밝히고,<br>함께하는 동행은 수익의 뿌리를 깊게 합니다."</span><br>
            <span style='color:#666; font-size:0.9rem;'>{BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]}부터 현재까지의 기록입니다.</span>
        </p>
        <div style='border-top:1px solid #eee; padding-top:10px; margin-top:10px;'>
            <p style='color:#e74c3c; font-size:0.85rem; font-weight:bold; margin-bottom:0;'>
                ⚠️ [주의] 본 데이터는 정보 공유용이며, 모든 투자의 책임은 본인에게 있습니다.
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

try:
    # 데이터 로드
    df_list = pd.read_csv(SHEET_URL)
    df_list.columns = df_list.columns.str.strip()
    df_list = df_list.dropna(subset=['종목코드', '참가자'])
    
    today_str = datetime.now().strftime("%Y%m%d")
    effective_end = END_DATE if END_DATE < today_str else today_str

    # [최적화 핵심] 중복된 종목코드를 제거하여 API 호출 횟수 최소화
    unique_tickers = [str(t).strip().split('.')[0].zfill(6) for t in df_list['종목코드'].unique()]

    # [병렬 처리] 일꾼 20명이 동시에 고유 종목의 가격을 수집
    with ThreadPoolExecutor(max_workers=20) as executor:
        price_results = list(executor.map(lambda t: fetch_single_ticker_data(t, effective_end), unique_tickers))

    # 가져온 가격 데이터를 매칭하기 편하게 딕셔너리로 변환
    price_map = {res['ticker']: res for res in price_results if res is not None}

    # 전체 명단에 가격 정보 결합
    final_results = []
    for _, row in df_list.iterrows():
        ticker = str(row['종목코드']).strip().split('.')[0].zfill(6)
        p_data = price_map.get(ticker)
        
        if p_data:
            base_p = p_data['기준가']
            curr_p = p_data['현재가']
            diff = curr_p - base_p
            rate = round((diff / base_p) * 100, 2)
            
            final_results.append({
                '참가자': row['참가자'], '종목명': row['종목명'], 
                '기준가': base_p, '현재가': curr_p, '등락': diff, '수익률': rate,
                '최종날짜': p_data['최종날짜']
            })

    if final_results:
        data = pd.DataFrame(final_results).sort_values(by='수익률', ascending=False).reset_index(drop=True)
        last_date = data['최종날짜'].iloc[0]
        
        table_rows = ""
        for i, row in data.iterrows():
            rank = i + 1
            rank_disp = f"🥇 {rank}위" if rank == 1 else (f"🥈 {rank}위" if rank == 2 else (f"🥉 {rank}위" if rank == 3 else f"{rank}위"))
            
            if row['수익률'] > 0:
                color = "color:#e74c3c;" # 빨간색
                change_icon = "▲"
                rate_prefix = "+"
            elif row['수익률'] < 0:
                color = "color:#3498db;" # 파란색
                change_icon = "▼"
                rate_prefix = "" # 마이너스 기호는 데이터에 포함됨
            else:
                color = "color:#333;"
                change_icon = ""
                rate_prefix = ""

            table_rows += f"""
            <tr style='font-size:0.95rem;'>
                <td style='padding:12px 2px; border-bottom:1px solid #eee; font-weight:bold; white-space:nowrap;'>{rank_disp}</td>
                <td style='padding:12px 5px; border-bottom:1px solid #eee; font-weight:bold; color:#333; white-space:nowrap;'>{row['참가자']}</td>
                <td style='padding:12px 10px; border-bottom:1px solid #eee; text-align:center;'>
                    <div style='font-size:1.0rem; font-weight:bold; color:#000; white-space:nowrap;'>{row['종목명']}</div>
                    <div class='mobile-only' style='font-size: 0.75rem; color:#666; margin-top:5px; font-weight:normal;'>
                        <div style='margin-bottom:2px;'>현재가: {row['현재가']:,.0f}원</div>
                        <div style='{color}'>기준가대비: {change_icon}{abs(row['등락']):,.0f}원</div>
                    </div>
                </td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; color:#888; white-space:nowrap;'>{row['기준가']:,.0f}원</td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; font-weight:bold; white-space:nowrap;'>{row['현재가']:,.0f}원</td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; {color} font-weight:bold; white-space:nowrap;'>{change_icon} {abs(row['등락']):,.0f}원</td>
                <td style='padding:12px 5px; border-bottom:1px solid #eee; {color} font-weight:bold; font-size:1.05rem;'>
                    {rate_prefix}{row['수익률']:.2f}%
                </td>
            </tr>
            """
        
        st.markdown(f"""
            <style>
                .mobile-only {{ display: none !important; }}
                .pc-only {{ display: table-cell !important; }}
                @media (max-width: 800px) {{
                    .mobile-only {{ display: block !important; }}
                    .pc-only {{ display: none !important; }}
                    th, td {{ padding: 10px 2px !important; }}
                }}
            </style>
            <div style="width:100%; background:white; border-radius:12px; overflow:hidden; border:1px solid #eee;">
                <table style="width:100%; border-collapse:collapse; text-align:center; table-layout: fixed;">
                    <thead>
                        <tr style="background-color:#1a3a5f; color:white; font-size:0.9rem;">
                            <th style="width:12%; padding:12px 2px;">순위</th>
                            <th style="width:13%; padding:12px 2px;">참가자</th>
                            <th style="width:30%; padding:12px 5px;">종목 정보</th>
                            <th class='pc-only' style="width:15%;">기준가</th>
                            <th class='pc-only' style="width:15%;">현재가</th>
                            <th class='pc-only' style="width:15%;">등락</th>
                            <th style="width:18%; padding:12px 5px;">수익률</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        
        st.success(f"✅ 데이터 반영 완료 ({last_date[:4]}-{last_date[4:6]}-{last_date[6:]})")

except Exception as e:
    st.error(f"오류 발생: {e}")

st.markdown("---")
st.markdown(f"""
    <div style='background-color:#f1f3f5; padding:20px; border-radius:15px; border-left:5px solid #1a3a5f;'>
            <h3 style='color:#1a3a5f; margin-top:0;'>📖 사용 설명서</h3>
            <p style='font-size:0.95rem; line-height:1.8;'>
                <b>1. 업데이트 안내</b><br>
- 본 페이지는 사용자가 <b>새로고침(F5)</b>을 할 때 최신 데이터를 수집합니다.<br>
- 동일 종목 중복 조회 방지 및 병렬 처리 시스템으로 인원이 많아져도 속도가 빠릅니다.<br><br>
                <b>2. 데이터 기준</b><br>
                - 시작일: {BASE_DATE[:4]}. {BASE_DATE[4:6]}. {BASE_DATE[6:]}<br>
                - 종료일: {END_DATE[:4]}. {END_DATE[4:6]}. {END_DATE[6:]}<br>
                <b>3. 순위 산정</b><br>
                기준일 대비 현재가의 수익률로 실시간 순위가 결정됩니다.<br><br>
                <span style='color:#777;'>* 수정 문의: 푸른돌디</span>
        </p>
    </div>
""", unsafe_allow_html=True)
