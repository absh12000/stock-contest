import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 설정 (모바일 대응을 위해 layout="wide" 제거)
st.set_page_config(page_title="주식 상황판 - 동행")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260430"  # 시작일
END_DATE = "20260531"    # 최종 종료일

# --- 데이터 처리 로직 ---
@st.cache_data(ttl=600)
def get_safe_price(ticker, target_date):
    """휴장일일 경우 이전 거래일 데이터를 찾아오는 함수"""
    dt = datetime.strptime(target_date, "%Y%m%d")
    for i in range(10):
        check_date = (dt - timedelta(days=i)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv(check_date, check_date, ticker)
        if not df.empty:
            return df['종가'].iloc[-1], check_date
    return None, None

# --- [수정 포인트 1] 상단 타이틀 (중앙 정렬 및 모바일 최적화) ---
st.title("🤝 주식, 혼자 하니 디다! 함께해요")
st.markdown(f"""
    <div style='padding:15px; background-color:#ffffff; border-radius:15px; border:1px solid #dee2e6; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom:20px;'>
        <h4 style='color:#1a3a5f; margin-top:0; font-size:1.1rem;'>📈 잼이와 함께하는 '실전 정보' 주식 상황판</h4>
        <p style='color:#555; font-size:0.95rem; line-height:1.5;'>
            "함께 <b>지식</b>을 나누면 길이 보입니다.<br>
            <b>{BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]}</b>부터 현재까지의 성적입니다."
        </p>
        <p style='color:#e74c3c; font-size:0.85rem; font-weight:bold; margin-bottom:0;'>
            ⚠️ 모든 투자의 책임은 본인에게 있습니다.
        </p>
    </div>
""", unsafe_allow_html=True)

# 데이터 불러오기 및 계산
try:
    df_list = pd.read_csv(SHEET_URL)
    df_list.columns = df_list.columns.str.strip()
    df_list = df_list.dropna(subset=['종목코드', '참가자'])
    
    final_results = []
    progress_bar = st.progress(0)
    
    today_str = datetime.now().strftime("%Y%m%d")
    effective_end = END_DATE if END_DATE < today_str else today_str

    for i, row in df_list.iterrows():
        ticker = str(row['종목코드']).strip().split('.')[0].zfill(6)
        base_p, _ = get_safe_price(ticker, BASE_DATE)
        curr_p, last_date = get_safe_price(ticker, effective_end)
        
        if base_p and curr_p:
            diff = curr_p - base_p
            rate = round((diff / base_p) * 100, 2)
            final_results.append({
                '참가자': row['참가자'], '종목명': row['종목명'], 
                '기준가': base_p, '현재가': curr_p, '등락': diff, '수익률': rate
            })
        progress_bar.progress((i + 1) / len(df_list))

    if final_results:
        data = pd.DataFrame(final_results).sort_values(by='수익률', ascending=False).reset_index(drop=True)
        
        # --- [수정 포인트 2] 모바일 표 스크롤 가능하도록 HTML 수정 ---
        table_rows = ""
        for i, row in data.iterrows():
            rank = i + 1
            rank_disp = f"🥇 1" if rank == 1 else f"🥈 2" if rank == 2 else f"🥉 3" if rank == 3 else f"{rank}"
            color = "color:#e74c3c;" if row['수익률'] > 0 else "color:#3498db;" if row['수익률'] < 0 else ""
            
            table_rows += f"""
            <tr style='font-size:0.9rem;'>
                <td style='padding:10px; border-bottom:1px solid #eee; font-weight:bold;'>{rank_disp}</td>
                <td style='padding:10px; border-bottom:1px solid #eee; font-weight:bold;'>{row['참가자']}</td>
                <td style='padding:10px; border-bottom:1px solid #eee;'>{row['종목명']}</td>
                <td style='padding:10px; border-bottom:1px solid #eee;'>{row['기준가']:,.0f}</td>
                <td style='padding:10px; border-bottom:1px solid #eee; font-weight:bold;'>{row['현재가']:,.0f}</td>
                <td style='padding:10px; border-bottom:1px solid #eee; {color} font-weight:bold;'>{row['수익률']:+.2f}%</td>
            </tr>
            """
        
        # overflow-x: auto 설정으로 모바일에서 옆으로 밀어서 볼 수 있게 함
        st.markdown(f"""
            <div style="overflow-x: auto;">
                <table style="width:100%; border-collapse:collapse; text-align:center; min-width:500px; background:white;">
                    <thead>
                        <tr style="background-color:#1a3a5f; color:white; font-size:0.85rem;">
                            <th style="padding:10px;">순위</th><th style="padding:10px;">참가자</th><th style="padding:10px;">종목명</th>
                            <th style="padding:10px;">기준가</th><th style="padding:10px;">현재가</th><th style="padding:10px;">수익률</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        
        st.success(f"✅ 데이터 반영 완료 ({last_date[:4]}-{last_date[4:6]}-{last_date[6:]})")

except Exception as e:
    st.error(f"오류 발생: {e}")

# --- [수정 포인트 3] 하단 설명란 (모바일에서 표 아래에 위치) ---
st.markdown("---")
st.markdown(f"""
    <div style='background-color:#f1f3f5; padding:20px; border-radius:15px; border-left:5px solid #1a3a5f;'>
        <h3 style='color:#1a3a5f; margin-top:0; font-size:1.1rem;'>📖 사용 설명서</h3>
        <p style='font-size:0.85rem; line-height:1.6;'>
            <b>1. 자동 업데이트</b>: 장 마감 후 자동 반영<br>
            <b>2. 데이터 기준</b>: {BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]} 시작<br>
            <b>3. 순위 산정</b>: 현재가 수익률 기준 실시간 정렬<br>
            <span style='color:#777;'>* 수정 문의: 푸른돌디</span>
        </p>
    </div>
""", unsafe_allow_html=True)
