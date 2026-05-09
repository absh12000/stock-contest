import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 설정
st.set_page_config(page_title="주식 상황판 - 동행", layout="wide")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260504" 
END_DATE = "20260529"   

@st.cache_data(ttl=600) 
def get_safe_price(ticker, target_date):
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
            rank_disp = f"🥇 {rank}위" if rank == 1 else (f"🥈 {rank}위" if rank == 2 else (f"🥉 {rank}위" if rank == 3 else f"{rank}위"))
            
            color = "color:#e74c3c;" if row['수익률'] > 0 else ("color:#3498db;" if row['수익률'] < 0 else "color:#333;")
            change_icon = "▲" if row['수익률'] > 0 else ("▼" if row['수익률'] < 0 else "")
            rate_sign = "+" if row['수익률'] > 0 else ""

            # [수정] 모바일 최적화: 줄바꿈 방지 및 글자 크기 미세 조정
            table_rows += f"""
            <tr style='font-size:0.95rem;'>
                <td style='padding:12px 2px; border-bottom:1px solid #eee; font-weight:bold; white-space:nowrap;'>{rank_disp}</td>
                <td style='padding:12px 5px; border-bottom:1px solid #eee; font-weight:bold; color:#333; white-space:nowrap;'>{row['참가자']}</td>
                <td style='padding:12px 10px; border-bottom:1px solid #eee; text-align:center;'>
                    <div style='font-size:1.1rem; font-weight:bold; color:#000; white-space:nowrap;'>{row['종목명']}</div>
                    <div class='mobile-only' style='font-size: 0.8rem; color:#666; margin-top:5px; font-weight:normal;'>
                        <div style='margin-bottom:2px;'>현재가: {row['현재가']:,.0f}원</div>
                        <div style='{color}'>기준대비: {change_icon}{abs(row['등락']):,.0f}원</div>
                    </div>
                </td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; color:#888; white-space:nowrap;'>{row['기준가']:,.0f}원</td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; font-weight:bold; white-space:nowrap;'>{row['현재가']:,.0f}원</td>
                <td class='pc-only' style='padding:15px 5px; border-bottom:1px solid #eee; {color} font-weight:bold; white-space:nowrap;'>{change_icon} {abs(row['등락']):,.0f}원</td>
                <td style='padding:12px 5px; border-bottom:1px solid #eee; {color} font-weight:bold; font-size:1.05rem;'>{rate_sign}{abs(row['수익률']):.2f}%</td>
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
                            <th style="width:12%; padding:12px 2px;">순위</th> <!-- 모바일 순위 꺾임 방지 -->
                            <th style="width:15%; padding:12px 2px;">참가자</th>
                            <th style="width:30%; padding:12px 5px;">종목 정보</th>
                            <th class='pc-only' style="width:15%;">기준가</th>
                            <th class='pc-only' style="width:15%;">현재가</th>
                            <th class='pc-only' style="width:15%;">등락</th>
                            <th style="width:19%; padding:12px 5px;">수익률</th>
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
                <b>1. 자동 업데이트 및 데이터 출처</b><br>
- <b>장중 (평일 09:00~15:30)</b>: 한국거래소(KRX) 기반 약 10분 단위 실시간 반영<br>
- <b>장 마감 후</b>: 당일 최종 종가(Final Price)로 데이터 고정<br>
- <b>정보 출처</b>: 한국거래소(KRX) 공시 데이터 기반<br><br>
                <b>2. 데이터 기준</b><br>
                - 시작일: {BASE_DATE[:4]}. {BASE_DATE[4:6]}. {BASE_DATE[6:]}<br>
                - 종료일: {END_DATE[:4]}. {END_DATE[4:6]}. {END_DATE[6:]}<br>
                <small>(현재 장이 열리지 않은 경우 가장 최근 영업일 기준)</small><br><br>
                <b>3. 순위 산정</b><br>
                기준일 대비 현재가의 수익률 비중으로 실시간 순위가 결정됩니다.<br><br>
                <b>4. 정보 공유</b><br>
                참가자들 간의 유익한 정보 교류를 목적으로 합니다.<br><br>
                <span style='color:#777;'>* 수정 문의: 푸른돌디</span>
        </p>
    </div>
""", unsafe_allow_html=True)
