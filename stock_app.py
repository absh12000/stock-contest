import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 기본 설정
st.set_page_config(page_title="수익률 대회", layout="wide")

st.title("🏆 주식투자 종목 수익률 대회")
st.markdown(f"<p style='text-align:center; color:#666;'>기준일: 2025년 05월 04일 | 조회 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_and_calculate():
    try:
        df_list = pd.read_csv(SHEET_URL)
        df_list.columns = df_list.columns.str.strip()
        df_list = df_list.dropna(subset=['종목코드', '참가자'])
    except Exception as e:
        st.error(f"시트를 읽을 수 없습니다: {e}")
        return pd.DataFrame()

    base_date = "20260504"
    today = datetime.now().strftime("%Y%m%d")
    final_results = []
    
    progress_bar = st.progress(0)
    for i, row in df_list.iterrows():
        ticker = str(row['종목코드']).strip().split('.')[0].zfill(6)
        try:
            df_base = stock.get_market_ohlcv(base_date, base_date, ticker)
            df_curr = stock.get_market_ohlcv(today, today, ticker)
            if not df_base.empty and not df_curr.empty:
                b_p = df_base['종가'].iloc[0]
                c_p = df_curr['종가'].iloc[-1]
                diff = c_p - b_p
                rate = round((diff / b_p) * 100, 2)
                final_results.append({
                    '참가자': row['참가자'],
                    '종목명': row['종목명'],
                    '기준가': b_p,
                    '현재가': c_p,
                    '등락': diff,
                    '수익률': rate
                })
        except: continue
        progress_bar.progress((i + 1) / len(df_list))

    if not final_results: return pd.DataFrame()
    return pd.DataFrame(final_results).sort_values(by='수익률', ascending=False).head(10).reset_index(drop=True)

data = load_and_calculate()

if not data.empty:
    # --- HTML 데이터 생성 ---
    table_rows = ""
    for i, row in data.iterrows():
        rank = i + 1
        rank_display = f"🥇 1등" if rank == 1 else f"🥈 2등" if rank == 2 else f"🥉 3등" if rank == 3 else f"{rank}위"
        color_style = "color:#e74c3c; font-weight:bold;" if row['수익률'] > 0 else "color:#3498db; font-weight:bold;" if row['수익률'] < 0 else ""
        prefix = "▲" if row['수익률'] > 0 else "▼" if row['수익률'] < 0 else ""

        table_rows += f"""
        <tr>
            <td style='padding:15px; border-bottom:1px solid #eee; font-weight:bold;'>{rank_display}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; font-weight:bold; color:#333;'>{row['참가자']}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; font-weight:bold; color:#333;'>{row['종목명']}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; color:#888;'>{row['기준가']:,.0f}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; font-weight:800; font-size:1.15rem;'>{row['현재가']:,.0f}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; {color_style}'>{prefix} {row['등락']:+,.0f}</td>
            <td style='padding:15px; border-bottom:1px solid #eee; {color_style}'>{row['수익률']:+.2f}%</td>
        </tr>
        """

    # --- 전체 HTML 조합 ---
    full_html = f"""
    <div style="font-family: sans-serif; background-color:#f8f9fa; padding:10px;">
        <table style="width:100%; background-color:white; border-collapse:collapse; border-radius:15px; overflow:hidden; box-shadow:0 4px 10px rgba(0,0,0,0.1); text-align:center;">
            <thead>
                <tr style="background-color:#1a3a5f; color:white;">
                    <th style="padding:15px;">순위</th><th style="padding:15px;">참가자</th><th style="padding:15px;">종목명</th>
                    <th style="padding:15px;">기준가</th><th style="padding:15px;">현재가</th><th style="padding:15px;">등락</th><th style="padding:15px;">수익률</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
    """
    
    # --- 가장 확실한 출력 방식 (컴포넌트 사용) ---
    import streamlit.components.v1 as components
    components.html(full_html, height=800, scrolling=True)
    st.success("✅ 실시간 순위 대시보드 작동 중!")
else:
    st.warning("표시할 데이터가 없습니다.")