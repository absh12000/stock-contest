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
    """장외 거래를 제외한 정규장(15:30) 종가만 가져오는 부품"""
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
    """장중 실시간 시세 부품 (네이버 기반)"""
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        df = fdr.DataReader(ticker, today_str)
        if not df.empty:
            return int(df['Close'].iloc[-1])
        else:
            df_yest = fdr.DataReader(ticker, (datetime.now() - timedelta(days=5)).strftime("%Y%m%d"))
            return int(df_yest['Close'].iloc[-1])
    except:
        return None

@st.cache_data
def get_stock_name_auto(ticker):
    """종목명 자동 검색"""
    try:
        name = stock.get_market_ticker_name(ticker)
        return name if name else "종목정보없음"
    except:
        return "코드오류"

def fetch_single_ticker_data(ticker):
    """시세 데이터 수집 및 날짜 기록"""
    base_p, _ = get_pure_closing_price(ticker, BASE_DATE)
    curr_p = get_realtime_price(ticker)
    auto_name = get_stock_name_auto(ticker)
    
    # [핵심 수정] 시간은 완전히 버리고 날짜만 기록합니다.
    current_date = datetime.now().strftime("%Y.%m.%d")
    
    if base_p and curr_p:
        return {
            'ticker': ticker, 
            '기준가': base_p, 
            '현재가': curr_p, 
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
        <h4 style='color:#1a3a5f; margin-top:0; font-size:1.2rem;'>🧭 주식 동행 : 실전 정보 상황판 </h4>
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
    
    unique_tickers = [str(t).strip().split('.')[0].zfill(6) for t in df_list['종목코드'].unique()]

    with ThreadPoolExecutor(max_workers=20) as executor:
        price_results = list(executor.map(fetch_single_ticker_data, unique_tickers))

    price_map = {res['ticker']: res for res in price_results if res is not None}

    final_results = []
    for _, row in df_list.iterrows():
        ticker = str(row['종목코드']).strip().split('.')[0].zfill(6)
        p_data = price_map.get(ticker)
        if p_data:
            raw_name = row.get('종목명', "")
            display_name = raw_name if pd.notna(raw_name) and str(raw_name).strip() != "" else p_data['auto_name']
            
            base_p, curr_p = p_data['기준가'], p_data['현재가']
            diff = curr_p - base_p
            rate = round((diff / base_p) * 100, 2)
            final_results.append({
                '참가자': row['참가자'], '종목명': display_name, 
                '기준가': base_p, '현재가': curr_p, '등락': diff, '수익률': rate,
                '업데이트날짜': p_data['업데이트날짜']
            })

    if final_results:
        data = pd.DataFrame(final_results).sort_values(by='수익률', ascending=False).reset_index(drop=True)
        last_date = data['업데이트날짜'].iloc[0]
        data['rank'] = data['수익률'].rank(method='min', ascending=False).astype(int)
        
        table_rows = ""
        for i, row in data.iterrows():
            rank = row['rank'] 
            if rank in [1, 2, 3]:
                medal_icon = ["🥇", "🥈", "🥉"][rank-1]
                rank_disp = f'<div style="position: relative; display: inline-block; width: 45px; text-align: center;"><span style="font-size: 1rem; color: #333; font-weight: bold; position: relative; z-index: 1;">{rank}위</span><span style="font-size: 1.35rem; position: absolute; top: -28px; left: 10px; z-index: 2; opacity: 0.85;">{medal_icon}</span></div>'
            else:
                rank_disp = f'<span style="font-size: 1rem; color: #333; font-weight: bold;">{rank}위</span>'
            
            if row['수익률'] > 0: color, icon, prefix = "color:#e74c3c;", "▲", "+"
            elif row['수익률'] < 0: color, icon, prefix = "color:#3498db;", "▼", ""
            else: color, icon, prefix = "color:#333;", "", ""

            table_rows += f"""
            <tr style="font-size:0.95rem;">
                <td style="padding:7px 2px; border-bottom:1px solid #eee; font-weight:bold;">{rank_disp}</td>
                <td style="padding:7px 5px; border-bottom:1px solid #eee; font-weight:bold; color:#333;">{row['참가자']}</td>
                <td style="padding:7px 10px; border-bottom:1px solid #eee; text-align:center;">
                    <div style="font-size:1.04rem; font-weight:bold; color:#000; margin-bottom:5px;">{row['종목명']}</div>
                    <div class="mobile-only" style="font-size:0.72rem; color:#555; line-height:1.4; font-weight:normal; text-align:left; display:inline-block; width:100%; max-width:120px;">
                        <div style="display:table; width:100%;">
                            <div style="display:table-row;"><div style="display:table-cell;">기준가:</div><div style="display:table-cell; text-align:right;">{row['기준가']:,.0f}원</div></div>
                            <div style="display:table-row; color:#333; font-weight:bold;"><div style="display:table-cell;">현재가:</div><div style="display:table-cell; text-align:right;">{row['현재가']:,.0f}원</div></div>
                            <div style="display:table-row; {color}"><div style="display:table-cell;">등락:</div><div style="display:table-cell; text-align:right;">{icon}{abs(row['등락']):,.0f}원</div></div>
                        </div>
                    </div>
                </td>
                <td class="pc-only" style="padding:9px 5px; border-bottom:1px solid #eee; color:#888;">{row['기준가']:,.0f}원</td>
                <td class="pc-only" style="padding:9px 5px; border-bottom:1px solid #eee; font-weight:bold;">{row['현재가']:,.0f}원</td>
                <td class="pc-only" style="padding:9px 5px; border-bottom:1px solid #eee; {color} font-weight:bold;">{icon} {abs(row['등락']):,.0f}원</td>
                <td style="padding:12px 5px; border-bottom:1px solid #eee; {color} font-weight:bold; font-size:1.05rem;">{prefix}{row['수익률']:.2f}%</td>
            </tr>
            """
        
        st.markdown(f"""
            <style>
                .mobile-only {{ display: none !important; }}
                .pc-only {{ display: table-cell !important; }}
                @media (max-width: 800px) {{
                    .mobile-only {{ display: block !important; }}
                    .pc-only {{ display: none !important; }}
                }}
            </style>
            <div style="width:100%; background:white; border-radius:12px; overflow:hidden; border:1px solid #eee;">
                <table style="width:100%; border-collapse:collapse; text-align:center; table-layout: fixed;">
                    <thead>
                        <tr style="background-color:#1a3a5f; color:white; font-size:0.9rem;">
                            <th style="width:12%; padding:12px 2px;">순위</th>
                            <th style="width:13%; padding:12px 2px;">참가자</th>
                            <th style="width:30%; padding:12px 5px;">종목 정보</th>
                            <th class="pc-only" style="width:15%;">기준가</th>
                            <th class="pc-only" style="width:15%;">현재가</th>
                            <th class="pc-only" style="width:15%;">등락</th>
                            <th style="width:18%; padding:12px 5px;">수익률</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        # [수리 완료] 시간은 삭제하고 날짜만 깔끔하게 노출
        st.success(f"✅ 네이버 금융 시세 반영 완료 ({last_date})")
except Exception as e:
    st.error(f"오류 발생: {e}")

st.markdown("---")
st.markdown(f"""
<div style='background-color:#ffffff; padding:25px; border-radius:10px; border:1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
<h3 style='color:#1a3a5f; margin-top:0; margin-bottom:20px; border-bottom:2px solid #1a3a5f; padding-bottom:10px;'>🧭 데이터 산출 가이드</h3>
<p style='font-size:0.95rem; line-height:1.8; color:#333; margin:0;'>
<b>1. 데이터 기준 및 출처</b><br>
- 본 시스템은 네이버 금융(Naver Finance)의 시장 정보를 실시간으로 참조합니다.<br>
- 자료 출처: 네이버 금융 정보 서비스<br><br>
<b>2. 휴일 및 비영업일 데이터 반영</b><br>
- 시장 휴장일(토, 일, 공휴일)에는 데이터가 업데이트되지 않으며, 직전 거래일 종가로 산출됩니다.<br>
- 반영 기간: {BASE_DATE[:4]}.{BASE_DATE[4:6]}.{BASE_DATE[6:]} ~ {END_DATE[:4]}.{END_DATE[4:6]}.{END_DATE[6:]}<br><br>
<b>3. 장중 데이터와 장마감 데이터의 차이</b><br>
- 장중(09:00~15:30): 네이버 금융 실시간 시세를 바탕으로 수익률을 계산합니다.<br>
- 장마감 후: 당일 최종 확정된 정규장 종가(15:30)를 기준으로 데이터가 고정됩니다.<br><br>
<b>4. 실시간 데이터 오차 안내</b><br>
- 네이버 시스템과 실제 HTS 간에는 약 수 초에서 수 분의 시차가 발생할 수 있습니다.<br><br>
<b>5. 업데이트 및 순위 산정</b><br>
- 본 페이지는 사용자가 새로고침(F5)을 할 때 최신 데이터를 수집하여 반영합니다.<br>
- 시작일 기준가 대비 현재가 수익률로 실시간 순위가 결정됩니다.<br><br>
<span style='color:#e74c3c; font-weight:bold;'>⚠️ [주의] 본 데이터는 정보 공유를 목적으로 하며, 모든 투자의 책임은 본인에게 있습니다.</span><br>
<span style='color:#888; font-size:0.85rem; display:block; margin-top:10px;'>* 시스템 수정 및 기술 문의: 푸른돌디</span>
</p>
</div>
""", unsafe_allow_html=True)
