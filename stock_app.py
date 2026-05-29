import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import FinanceDataReader as fdr  # 네이버 엔진

# 1. 구글 시트 ID 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 페이지 설정
st.set_page_config(page_title="주식 동행", layout="wide")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260511" 
END_DATE = "20260529"    

@st.cache_data(ttl=60) 
def get_pure_closing_price(ticker, target_date):
    try:
        df = fdr.DataReader(ticker, target_date, target_date)
        if not df.empty:
            return int(df['Close'].iloc[-1]), target_date
        df_prev = fdr.DataReader(ticker, (datetime.now() - timedelta(days=7)).strftime("%Y%m%d"), target_date)
        if not df_prev.empty:
            return int(df_prev['Close'].iloc[-1]), df_prev.index[-1].strftime("%Y%m%d")
    except:
        pass
    return None, None

def get_realtime_price(ticker):
    """장중 실시간 시세 및 전일 대비 등락률 계산"""
    try:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        df = fdr.DataReader(ticker, start_date)
        
        if not df.empty:
            curr_p = int(df['Close'].iloc[-1])
            if len(df) > 1:
                prev_p = int(df['Close'].iloc[-2])
                day_rate = ((curr_p - prev_p) / prev_p) * 100
            else:
                day_rate = 0.0
            return curr_p, day_rate
        return None, 0.0
    except:
        return None, 0.0

@st.cache_data
def get_stock_name_auto(ticker):
    try:
        name = stock.get_market_ticker_name(ticker)
        return name if name else "종목정보없음"
    except:
        return "코드오류"

def fetch_single_ticker_data(ticker):
    base_p, _ = get_pure_closing_price(ticker, BASE_DATE)
    curr_p, day_rate = get_realtime_price(ticker)
    auto_name = get_stock_name_auto(ticker)
    current_date = datetime.now().strftime("%Y.%m.%d")
    if base_p and curr_p:
        return {
            'ticker': ticker, 
            '기준가': base_p, 
            '현재가': curr_p, 
            '당일등락률': day_rate,
            '업데이트날짜': current_date,
            'auto_name': auto_name
        }
    return None

# 상단 타이틀
st.title("🧭 주식 동행")

# 실시간 갱신 버튼
if st.button('🔄 실시간 시세 갱신'):
    st.cache_data.clear()
    st.rerun()

st.markdown(f"""
    <div style='padding:20px; background-color:#ffffff; border-radius:15px; border:1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom:20px;'>
        <h4 style='color:#1a3a5f; margin-top:0; font-size:1.2rem;'>🧭 주식 동행 : 정보 상황판 </h4>
        <p style='color:#333; font-size:1rem; line-height:1.6;'>
            <span style='font-weight:bold; font-size:1.05rem;'> "나누는 지식은 투자의 눈을 밝히고,<br>함께하는 동행은 수익의 뿌리를 깊게 합니다."</span><br>
            <span style='color:#666; font-size:0.9rem;'>{BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]}부터 현재까지의 기록입니다.</span>
        </p>
        <div style='border-top:1px solid #eee; padding-top:10px; margin-top:10px;'>
            <p style='color:#e74c3c; font-size:0.85rem; font-weight:bold; margin-bottom:0;'>
                ⚠️ [주의] 본 데이터는 네이버 금융 정보를 기반으로 한 정보 공유용이며, 모든 투자의 책임은 본인에게 있습니다.
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

try:
    df_list = pd.read_csv(SHEET_URL)
    df_list.columns = df_list.columns.str.strip()
    df_list = df_list.dropna(subset=['종목코드', '참가자'])
    unique_tickers =
