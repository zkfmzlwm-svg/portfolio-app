# 신규상장(IPO) 원자료 → data/ipo  (python3 -I ipo_fetch.py, 약 3분)
#   1) 38커뮤니케이션 신규상장 목록: 기업명·상장일·공모가·시초가·첫날종가·종목코드 (https는 서버 DH 키 문제로 http 사용)
#   2) 38 수요예측결과 목록: 기관경쟁률·의무보유확약 비율
#   (--intraday: 4) 야후 60분봉만 받음)
#   3) 네이버 fchart 일봉(수정주가) 상장일부터 최대 40봉 — 공모가 대비 배율은 38 시초가로 계산(ipo.py)
import re, time, urllib.request, pandas as pd, os, sys
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0'}
os.makedirs('data/ipo',exist_ok=True)
def get(url,enc='euc-kr'):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20) as r: return r.read().decode(enc,'ignore')
        except Exception: time.sleep(1.5*(i+1))
    raise RuntimeError(url)
num=lambda s:float(re.sub(r'[^\d.\-]','',s)) if re.search(r'\d',s or '') else None
strip=lambda s:re.sub(r'<[^>]+>','',s).replace('&nbsp;','').replace('&amp;','&').strip()
def pages(o):
    h=get(f'http://www.38.co.kr/html/fund/index.htm?o={o}'); m=re.findall(rf'o={o}&amp;page=(\d+)',h)
    return max(map(int,m)) if m else 1
def listing():
    rows=[]
    for pg in range(1,pages('nw')+1):
        h=get(f'http://www.38.co.kr/html/fund/index.htm?o=nw&page={pg}')
        body=h[h.find('summary="신규상장종목"'):]; body=body[:body.find('</table>')]
        for tr in re.findall(r'<tr bgColor[^>]*>(.*?)</tr>',body,re.S):
            td=re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S)
            if len(td)<10: continue
            code=re.search(r'code=(\w{6})',tr); no=re.search(r'no=(\d+)',tr)
            rows.append(dict(name=strip(td[0]),date=strip(td[1]).replace('/','-'),offer=num(strip(td[4])),open38=num(strip(td[6])),close38=num(strip(td[8])),
                             code=code.group(1) if code else None,no38=no.group(1) if no else None))
        time.sleep(0.3)
    return pd.DataFrame(rows)
def demand():
    rows=[]
    for pg in range(1,pages('r1')+1):
        h=get(f'http://www.38.co.kr/html/fund/index.htm?o=r1&page={pg}')
        body=h[h.find('summary="수요예측결과"'):]; body=body[:body.find('</table>')]
        for tr in re.findall(r'<tr bgColor[^>]*>(.*?)</tr>',body,re.S):
            td=[strip(x) for x in re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S)]
            if len(td)>=8: rows.append(td)
        time.sleep(0.3)
    return rows
def bars(code,d0):
    t=get(f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=3000&requestType=0')
    df=pd.DataFrame([r.split('|') for r in re.findall(r'item data="([^"]+)"',t)],columns=['t','o','h','l','c','v'])
    if not len(df): return code,0
    df['t']=pd.to_datetime(df.t); df[['o','h','l','c','v']]=df[['o','h','l','c','v']].astype(float)
    df=df[df.t>=pd.Timestamp(d0)-pd.Timedelta(days=10)].head(40)
    df.to_csv(f'data/ipo/{code}.csv',index=False); return code,len(df)
if __name__=='__main__' and '--intraday' not in sys.argv:
    L=listing(); L.to_csv('data/ipo/list38.csv',index=False); print('신규상장',len(L),L.date.min(),L.date.max())
    D=demand(); pd.DataFrame(D).to_csv('data/ipo/demand38_raw.csv',index=False,header=False); print('수요예측',len(D))
    todo=L[L.code.notna()&(L.date<=time.strftime('%Y-%m-%d'))]
    with ThreadPoolExecutor(6) as ex:
        res=list(ex.map(lambda r:bars(r.code,r.date),todo.itertuples()))
    print('일봉',sum(1 for _,n in res if n>0),'/',len(res))

# 4) 야후 60분봉(최근 730일)·5분봉·2분봉(최근 60일), 네이버 1분봉(최근 약 5거래일) — 상장일 장중 경로(익절이 언제 닿았는지, 시간 손절) 확인용. python3 -I ipo_fetch.py --intraday
def yahoo_60m(code,d0,iv='60m',rng='730d'):
    import json
    for suf in ['.KQ','.KS']:
        try:   # 없는 접미사(.KQ/.KS)는 404 → 재시도 없이 다음으로
            with urllib.request.urlopen(urllib.request.Request(f'https://query1.finance.yahoo.com/v8/finance/chart/{code}{suf}?interval={iv}&range={rng}',headers=UA),timeout=20) as rr: j=json.loads(rr.read().decode())
        except Exception: continue
        r=(j.get('chart') or {}).get('result')
        if not r or not r[0].get('timestamp'): continue
        r=r[0]; q=r['indicators']['quote'][0]
        df=pd.DataFrame({'t':pd.to_datetime(r['timestamp'],unit='s',utc=True).tz_convert('Asia/Seoul').tz_localize(None),
                         'o':q['open'],'h':q['high'],'l':q['low'],'c':q['close'],'v':q['volume']}).dropna()
        df=df[df.t.dt.strftime('%Y-%m-%d')==d0]
        if len(df): df.to_csv(f'data/ipo/{code}_{iv}.csv',index=False); return code,len(df),suf
    return code,0,None
if __name__=='__main__' and '--intraday' in sys.argv:
    L=pd.read_csv('data/ipo/list38.csv',dtype={'code':str})
    todo=L[L.code.notna()&(L.date>='2024-11-06')&(L.date<=time.strftime('%Y-%m-%d'))&~L.name.str.contains('스팩|리츠')]
    skip=lambda c,iv:os.path.exists(f'data/ipo/{c}_{iv}.csv')       # 이미 받은 종목은 건너뜀(야후 요청 수 줄이기)
    with ThreadPoolExecutor(4) as ex: res=list(ex.map(lambda r:(r.code,1,'') if skip(r.code,'60m') else yahoo_60m(r.code,r.date),todo.itertuples()))
    print('60분봉 상장일 있음',sum(1 for _,n,_ in res if n>0),'/',len(res))
    t5=todo[todo.date>=(pd.Timestamp.today()-pd.Timedelta(days=58)).strftime('%Y-%m-%d')]   # 5분봉은 최근 60일만
    with ThreadPoolExecutor(4) as ex: res=list(ex.map(lambda r:(r.code,1,'') if skip(r.code,'5m') else yahoo_60m(r.code,r.date,'5m','60d'),t5.itertuples()))
    print('5분봉 상장일 있음',sum(1 for _,n,_ in res if n>0),'/',len(res))
    with ThreadPoolExecutor(4) as ex: res=list(ex.map(lambda r:(r.code,1,'') if skip(r.code,'2m') else yahoo_60m(r.code,r.date,'2m','60d'),t5.itertuples()))
    print('2분봉 상장일 있음',sum(1 for _,n,_ in res if n>0),'/',len(res))
    # 네이버 1분봉(약 5거래일 보관) — 손절·익절 중 먼저 닿은 쪽 확인용
    import json
    t1=todo[todo.date>=(pd.Timestamp.today()-pd.Timedelta(days=10)).strftime('%Y-%m-%d')]; n1=0
    for r in t1.itertuples():
        ymd=r.date.replace('-','')
        try: arr=json.loads(get(f'https://api.stock.naver.com/chart/domestic/item/{r.code}/minute?startDateTime={ymd}0900&endDateTime={ymd}1530','utf-8'))
        except Exception: continue
        if arr:
            pd.DataFrame([{'t':pd.to_datetime(x['localDateTime'],format='%Y%m%d%H%M%S'),'o':x['openPrice'],'h':x['highPrice'],'l':x['lowPrice'],'c':x['currentPrice']} for x in arr]).to_csv(f'data/ipo/{r.code}_1m.csv',index=False); n1+=1
    print('네이버 1분봉 상장일 있음',n1,'/',len(t1))
