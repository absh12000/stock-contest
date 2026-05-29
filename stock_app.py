import streamlit as st
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정 및 시트 주소
st.set_page_config(page_title="주식 동행", layout="wide")
SHEET_ID = "1qY0Z-Mzny61lk4TfO0FNoYF870ve3sI5SbDA4jS5M0Y"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"

BASE_DATE = "20260511" 

@st.cache_data(ttl=60)
def get_pure_closing_price(ticker, target_date):
    try:
        df = stock.get_market_ohlcv_by_date(target_date, target_date, ticker)
        if not df.empty and df['종가'].iloc[-1] > 0:
            return int(df['종가'].iloc[-1])
        start_p = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
        df_prev = stock.get_market_ohlcv_by_date(start_p, target_date, ticker)
        if not df_prev.empty:
            valid_df = df_prev[df_prev['종가'] > 0]
            if not valid_df.empty:
                return int(valid_df['종가'].iloc[-1])
    except:
        pass
    return None

def get_realtime_price(ticker):
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start_date, today_str, ticker)
        if not df.empty:
            valid_df = df[df['종가'] > 0]
            if not valid_df.empty:
                curr_p = int(valid_df['종가'].iloc[-1])
                prev_p = int(valid_df['종가'].iloc[-2]) if len(valid_df) > 1 else curr_p
                day_rate = ((curr_p - prev_p) / prev_p) * 100 if len(valid_df) > 1 else 0.0
                return curr_p, day_rate
    except:
        pass
    return None, 0.0

def fetch_single_ticker_data(ticker):
    base_p = get_pure_closing_price(ticker, BASE_DATE)
    curr_p, day_rate = get_realtime_price(ticker)
    name = stock.get_market_ticker_name(ticker)
    if base_p and curr_p:
        return {'ticker': ticker, '기준가': base_p, '현재가': curr_p, '당일등락률': day_rate, '종목명': name if name else "종목정보없음"}
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
    unique_tickers = [str(t).strip().split('.')[0].zfill(6) for t in df_list['종목코드'].unique()]

    with ThreadPoolExecutor(max_workers=20) as executor:
        price_results = list(executor.map(fetch_single_ticker_data, unique_tickers))

    price_map = {res['ticker']: res for res in price_results if res is not None}

    final_results = []
    for _, row in df_list.iterrows():
        ticker = str(row['종목코드']).strip().split('.')[0].zfill(6)
        p_data = price_map.get(ticker)
        if p_data:
            base_p, curr_p = p_data['기준가'], p_data['현재가']
            rate = round(((curr_p - base_p) / base_p) * 100, 2)
            final_results.append({
                '참가자': row['참가자'], '종목명': p_data['종목명'], 'ticker': ticker,
                '기준가': base_p, '현재가': curr_p, '등락': curr_p - base_p, '수익률': rate,
                '당일등락률': p_data['당일등락률']
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
                <td style="padding:12px; border-bottom:1px solid #eee; color:#888;">{row['기준가']:,.0f}원</td>
                <td style="padding:12px; border-bottom:1px solid #eee; font-weight:bold;">{row['현재가']:,.0f}원</td>
                <td style="padding:12px; border-bottom:1px solid #eee; {color}">{icon} {abs(row['등락']):,.0f}원</td>
                <td style="padding:12px; border-bottom:1px solid #eee; {color} font-weight:bold; font-size:1.05rem;">{prefix}{row['수익률']:.2f}%</td>
            </tr>
            """
        
        st.markdown(f"""
            <div style="width:100%; background:white; border-radius:12px; overflow:hidden; border:1px solid #eee;">
                <table style="width:100%; border-collapse:collapse;">
                    <thead>
                        <tr style="background-color:#1a3a5f; color:white; font-size:1rem; height:45px;">
                            <th style="width:10%;">순위</th>
                            <th style="width:15%;">참가자</th>
                            <th style="width:25%;">종목명</th>
                            <th style="width:15%;">기준가</th>
                            <th style="width:15%;">현재가</th>
                            <th style="width:15%;">등락</th>
                            <th style="width:15%;">수익률</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        st.success(f"✅ 한국거래소(KRX) 시세 반영 완료")
except Exception as e:
    st.error(f"오류 발생: {e}")

# 끝
