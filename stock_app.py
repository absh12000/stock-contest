import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 1. 구글 시트 및 페이지 설정
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
st.set_page_config(page_title="주식 동행", layout="wide")

# --- [날짜 고정 설정] ---
BASE_DATE = "20260511" 
END_DATE = "20260529"    

@st.cache_data(ttl=60) 
def get_pure_closing_price(ticker, target_date):
    try:
        df = stock.get_market_ohlcv_by_date(target_date, target_date, ticker)
        if not df.empty and df['종가'].iloc[-1] > 0:
            return int(df['종가'].iloc[-1]), target_date
        start_p = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
        df_prev = stock.get_market_ohlcv_by_date(start_p, target_date, ticker)
        if not df_prev.empty:
            valid_df = df_prev[df_prev['종가'] > 0]
            if not valid_df.empty:
                return int(valid_df['종가'].iloc[-1]), valid_df.index[-1].strftime("%Y%m%d")
    except:
        pass
    return None, None

def get_realtime_price(ticker):
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start_date, today_str, ticker)
        if not df.empty:
            valid_df = df[df['종가'] > 0]
            if not valid_df.empty:
                curr_p = int(valid_df['종가'].iloc[-1])
                if len(valid_df) > 1:
                    prev_p = int(valid_df['종가'].iloc[-2])
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
            'ticker': ticker, '기준가': base_p, '현재가': curr_p, 
            '당일등락률': day_rate, '업데이트날짜': current_date, 'auto_name': auto_name
        }
    return None

# 상단 UI 타이틀 및 레이아웃
st.title("🧭 주식 동행")

if st.button('🔄 실시간 시세 갱신'):
    st.cache_data.clear()
    st.rerun()

st.markdown(f"""
    <div style='padding:20px; background-color:#ffffff; border-radius:15px; border:1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom:20px;'>
        <h4 style='color:#1a3a5f; margin-top:0; font-size:1.2rem;'>🧭 주식 동행 : 정보 상황판 </h4>
        <p style='color:#333
