import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정 및 구글 시트 주소 (오류 방지 주소 가공)
st.set_page_config(page_title="주식 동행", layout="wide")
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"

BASE_DATE = "20260511" 

@st.cache_data(ttl=60)
def get_pure_closing_price(ticker, target_date):
    """기준일 종가 가져오기 (주말일 경우 전 거래일 추적)"""
    try:
        df = fdr.DataReader(ticker, target_date, target_date)
        if not df.empty and 'Close' in df.columns and df['Close'].iloc[-1] > 0:
            return int(df['Close'].iloc[-1])
        
        # 주말/휴일 대응: 7일 전부터 넉넉히 수집 후 마지막 거래일 종가 선택
        start_p = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
        df_prev = fdr.DataReader(ticker, start_p, target_date)
        if not df_prev.empty and 'Close' in df_prev.columns:
            valid_df = df_prev[df_prev['Close'] > 0]
            if not valid_df.empty:
                return int(valid_df['Close'].iloc[-1])
    except:
        pass
    return None

def get_realtime_price(ticker):
    """최신 장중 시세 및 전일 대비 등락률 산출"""
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        df = fdr.DataReader(ticker, start_date, today_str)
        if not df.empty and 'Close' in df.columns:
            valid_df = df[df['Close'] > 0]
            if not valid_df.empty:
                curr_p = int(valid_df['Close'].iloc[-1])
                prev_p = int(valid_df['Close'].iloc[-2]) if len(valid_df) > 1 else curr_p
                day_rate = ((curr_p - prev_p) / prev_p) * 100 if len(valid_df) > 1 else 0.0
                return curr_p, day_rate
    except:
        pass
    return None, 0.0

def fetch_single_ticker_data(ticker):
    base_p = get_pure_closing_price(ticker, BASE_DATE)
    curr_p, day_rate = get_realtime_price(ticker)
    if base_p and curr_p:
        return {'ticker': ticker, '기준가': base_p, '현재가': curr_p, '당일등락률': day_rate}
    return None

# 상단 타이틀
st.title("🧭 주식 동행")

if st.button('🔄 실시간 시세 갱신'):
    st.cache_data.clear()
    st.rerun()

st.markdown(f"""
    <div style='padding:20px; background-color:#ffffff; border-radius:15px; border:1px solid #dee2e6; margin-bottom:20px;'>
        <h4 style='color:#1a3a5f; margin-top:0;'>🧭 주식 동행 : 정보 상황판 </h4>
        <p style='color:#333; margin-bottom:0;'><b>"나누는 지식은 투자의 눈을 밝히고, 함께하는 동행은 수익의 뿌리를 깊게 합니다."</b></p>
    </div>
""", unsafe_allow_html=True)

try:
    df_list = pd.read_csv(SHEET_URL)
    df_list.columns = df_list.columns.str.strip()
    df_list = df_list.dropna(subset=['종목코드', '참가자'])
    
    # 종목코드 자릿수 포맷팅 (6자리 맞춤)
    unique_tickers = []
    for t in df_list['종목코드'].unique():
        t_str = str(t).strip().split('.')[0]
        if t_str.isdigit():
            unique_tickers.append(t_str.zfill(6))

    with ThreadPoolExecutor(max_workers=20) as executor:
        price_results = list(executor.map(fetch_single_ticker_data, unique_tickers))

    price_map = {res['ticker']: res for res in price_results if res is not None}

    final_results = []
    for _, row in df_list.iterrows():
        t_raw = str(row['종목코드']).strip().split('.')[0]
        if not t_raw.isdigit():
            continue
        ticker = t_raw.zfill(6)
        p_data = price_map.get(ticker)
        if p_data:
            base_p, curr_p = p_data['기준가'], p_data['현재가']
            rate = round(((curr_p - base_p) / base_p) * 100, 2)
            
            # 구글 시트에 기재된 종목명을 우선 사용
            sh_name = row.get('종목명', '')
            final_name = str(sh_name).strip() if pd.notna(sh_name) and str(sh_name).strip() != "" else f"종목({ticker})"
            
            final_results.append({
                '참가자': row['참가자'], '종목명': final_name, 'ticker': ticker,
                '기준가': base_p, '현재가': curr_p, '등락': curr_p - base_p, '수익률': rate
            })

    if final_results:
        data = pd.DataFrame(final_results).sort_values(by='수익률', ascending=False).reset_index(drop=True)
        data['rank'] = data['수익률'].rank(method='min', ascending=False).astype(int)
        
        table_rows = ""
        for i, row in data.iterrows():
            rank = row['rank']
            color = "color:#e74c3c;" if row['수익률'] > 0 else "color:#3498db;" if row['수익률'] < 0 else "color:#333;"
            icon = "▲" if row['수익률'] > 0 else "▼" if row['수익률'] < 0 else ""
            prefix = "+" if row['수익률'] > 0 else ""
            
            table_rows += f"""
            <tr style="font-size:0.95rem; text-align:center;">
                <td style="padding:12px; border-bottom:1px solid #eee; font-weight:bold;">{rank}위</td>
                <td style="padding:12px; border-bottom:1px solid #eee; font-weight:bold;">{row['참가자']}</td>
                <td style="padding:12px; border-bottom:1px solid #eee;">{row['종목명']}</td>
                <td style="padding:12px; border-bottom:1px solid #eee;
