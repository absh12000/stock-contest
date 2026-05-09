import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 설정
st.set_page_config(page_title="주식 상황판 - 동행")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260511"  # 시작일
END_DATE = "20260529"    # 최종 종료일

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
        
        table_rows = ""
        for i, row in data.iterrows():
            rank = i + 1
            # 85라인: 순위 문법 오류 수정 완료
            rank_disp = f"🥇 {rank}위" if rank == 1 else (f"🥈 {rank}위" if rank == 2 else (f"🥉 {rank}위" if rank == 3 else f"{rank}위"))
            
            # [네이버 표준 스타일 로직]
            if row['수익률'] > 0:
                color = "color:#e74c3c;"  # 상승: 빨간색
                change_icon = "▲"         # 금액 등락용 세모
                rate_sign = "+"           # 수익률용 기호
            elif row['수익률'] < 0:
                color = "color:#3498db;"  # 하락: 파란색
                change_icon = "▼"         # 금액 등락용 세모
                rate_sign = "-"           # 수익률용 기호
            else:
                color = "color:#333;"     # 보합: 검정색
                change_icon = ""
                rate_sign = ""

            table_rows += f"""
            <tr style='font-size:0.95rem;'>
                <td style='padding:12px 8px; border-bottom:1px solid #eee; font-weight:bold;'>{rank_disp}</td>
                <td style='padding:12px; border-bottom:1px solid #eee; font-weight:bold; color:#333;'>{row['참가자']}</td>
                
                <!-- [모바일 최적화] 종목명 아래에 현재가 배치 -->
                <td style='padding:12px; border-bottom:1px solid #eee; text-align:center;'>
                    <div style='font-weight:bold; color:#333;'>{row['종목명']}</div>
                    <div style='font-size:0.8rem; color:#888; margin-top:2px;'>현재 {row['현재가']:,.0f}원</div>
                </td>
                
                <td class='pc-only' style='padding:12px 8px; border-bottom:1px solid #eee; color:#888;'>{row['기준가']:,.0f}원</td>
                <td class='pc-only' style='padding:12px 8px; border-bottom:1px solid #eee; font-weight:bold;'>{row['현재가']:,.0f}원</td>
                <td class='pc-only' style='padding:12px 8px; border-bottom:1px solid #eee; {color} font-weight:bold;'>{change_icon} {abs(row['등락']):,.0f}원</td>
                <td style='padding:12px 8px; border-bottom:1px solid #eee; {color} font-weight:bold;'>{rate_sign}{abs(row['수익률']):.2f}%</td>
            </tr>
            """
        
        st.markdown(f"""
            <style>
                .pc-only {{ display: table-cell; }}
                @media (max-width: 600px) {{
                    .pc-only {{ display: none; }}
                    th, td {{ padding: 8px 4px !important; font-size: 0.85rem !important; }}
                }}
            </style>
            
            <div style="width:100%; background:white; border-radius:12px; overflow:hidden; border:1px solid #eee;">
                <table style="width:100%; border-collapse:collapse; text-align:center;">
                    <thead>
                        <tr style="background-color:#1a3a5f; color:white; font-size:0.9rem;">
                            <th style="padding:12px 8px;">순위</th>
                            <th style="padding:12px 8px;">참가자</th>
                            <th style="padding:12px 8px;">종목명</th>
                            <th class='pc-only' style="padding:12px 8px;">기준가</th>
                            <th class='pc-only' style="padding:12px 8px;">현재가</th>
                            <th class='pc-only' style="padding:12px 8px;">등락</th>
                            <th style="padding:12px 8px;">수익률</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        
        st.success(f"✅ 데이터 반영 완료 ({last_date[:4]}-{last_date[4:6]}-{last_date[6:]})")

except Exception as e:
    st.error(f"오류 발생: {e}")

# 하단 설명란 생략 (기존 코드와 동일)
