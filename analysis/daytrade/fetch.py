# 원자료 → ./data  (국내: 네이버 fchart 일봉 수정주가 최대 3000봉 / 미국: 야후 일봉 / 코인: 업비트 일봉·5분봉)
#   python3 fetch.py          국내 + 미국 (약 1분)
#   python3 fetch.py --upbit  업비트 포함 (5분봉 1년치는 마켓당 약 10분)
import json, re, sys, time, urllib.request, pandas as pd
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
ETF={'069500':'KODEX 200','229200':'KODEX 코스닥150','122630':'KODEX 레버리지','233740':'KODEX 코스닥150레버리지',
     '091160':'KODEX 반도체','305720':'KODEX 2차전지산업','102110':'TIGER 200','364980':'TIGER 2차전지TOP10',
     '494670':'TIGER 조선TOP10','471990':'KODEX AI반도체핵심장비','461950':'KODEX 2차전지핵심소재','0101N0':'RISE AI전력인프라'}
# 개별주: 앱 보유·워치리스트 국내 종목 + KOSPI/KOSDAQ 시총 상위(현존 — 생존편향 있음)
STK='''237690 에스티팜|000250 삼천당제약|010120 LS ELECTRIC|005930 삼성전자|066570 LG전자|067630 HLB생명과학|000660 SK하이닉스|373220 LG에너지솔루션|403870 HPSP|058470 리노공업|140860 파크시스템스|105560 KB금융|000270 기아|329180 HD현대중공업|247540 에코프로비엠|196170 알테오젠|263750 펄어비스|033780 KT&G|097950 CJ제일제당|000080 하이트진로|005380 현대차|005490 POSCO홀딩스|012450 한화에어로스페이스|035420 NAVER|035720 카카오|051910 LG화학|207940 삼성바이오로직스|068270 셀트리온|006400 삼성SDI|055550 신한지주|028260 삼성물산|012330 현대모비스|096770 SK이노베이션|017670 SK텔레콤|030200 KT|003550 LG|034730 SK|015760 한국전력|032830 삼성생명|086790 하나금융지주|018260 삼성에스디에스|009150 삼성전기|010950 S-Oil|011200 HMM|042660 한화오션|009540 HD한국조선해양|034020 두산에너빌리티|064350 현대로템|298040 효성중공업|267260 HD현대일렉트릭|042700 한미반도체|086520 에코프로|028300 HLB|041510 에스엠|352820 하이브|036570 엔씨소프트|259960 크래프톤|000810 삼성화재|024110 기업은행|010130 고려아연|003670 포스코퓨처엠|066970 엘앤에프|293490 카카오게임즈|112040 위메이드|047050 포스코인터내셔널|011170 롯데케미칼|323410 카카오뱅크|251270 넷마블|161390 한국타이어앤테크놀로지|000720 현대건설'''
STK=dict(x.split(' ',1) for x in STK.split('|'))
# 미국: 섹터 ETF·대형주 (us_signal.py) + 워치리스트 해외 6종목
US=['SOXX','SOXL','SMH','MU','NVDA','QQQ','TQQQ','SPY','EWY','XLK','XLE','XLF','KBE','ITA','IBB','XBI','LIT','TSLA','GM','XME','ETN','VRT',
    'MSFT','AMZN','AAPL','JPM','XOM']
def read(url,enc='utf-8'):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20) as r: return r.read().decode(enc,'ignore')
        except Exception: time.sleep(1.5*(i+1))
    raise RuntimeError(url)
def kr(code):
    txt=read(f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=3000&requestType=0','euc-kr')
    df=pd.DataFrame([r.split('|') for r in re.findall(r'item data="([^"]+)"',txt)],columns=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t); df[['o','h','l','c','v']]=df[['o','h','l','c','v']].astype(float)
    df=df[(df.o>0)&(df.h>0)&(df.l>0)]          # 거래정지일(0) 제외
    df.to_csv(f'data/kr/{code}.csv',index=False); return code,len(df)
def upbit(market,unit,start):
    base=f"https://api.upbit.com/v1/candles/{'days' if unit=='days' else 'minutes/'+str(unit)}?market={market}&count=200"
    rows=[];to=None
    while True:
        d=json.loads(read(base+(f'&to={to}' if to else '')))
        if not d: break
        rows+=d; last=d[-1]['candle_date_time_utc']
        if last<start: break
        to=last+'Z'; time.sleep(0.11)
    df=pd.DataFrame(rows)[['candle_date_time_kst','opening_price','high_price','low_price','trade_price','candle_acc_trade_price']]
    df.columns=['t','o','h','l','c','val']; df['t']=pd.to_datetime(df.t)
    return df.drop_duplicates('t').sort_values('t').query('t>=@start').reset_index(drop=True)
if __name__=='__main__':
    import os; os.makedirs('data/kr',exist_ok=True); os.makedirs('data/upbit',exist_ok=True)
    meta=[(c,n,'etf') for c,n in ETF.items()]+[(c,n,'stock') for c,n in STK.items()]
    pd.DataFrame(meta,columns=['code','name','type']).to_csv('data/kr/universe.csv',index=False)
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(kr,[m[0] for m in meta]): print(*r)
    os.makedirs('data/us',exist_ok=True)
    for t in US:
        open(f'data/us/{t}.json','w').write(read(f'https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=1388534400&period2=9999999999&interval=1d')); time.sleep(0.4)
    print('미국',len(US),'종목')
    if '--upbit' in sys.argv:
        for m in ['KRW-BTC','KRW-ETH','KRW-XRP']:
            upbit(m,'days','2017-10-01').to_csv(f'data/upbit/{m}_D.csv',index=False)
            if m!='KRW-XRP': upbit(m,5,'2025-10-13').to_csv(f'data/upbit/{m}_5m.csv',index=False)
            print(m,'ok')
