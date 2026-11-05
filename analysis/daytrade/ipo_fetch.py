# 신규상장(IPO) 원자료 → data/ipo  (python3 -I ipo_fetch.py, 약 3분)
#   1) 38커뮤니케이션 신규상장 목록: 기업명·상장일·공모가·시초가·첫날종가·종목코드 (https는 서버 DH 키 문제로 http 사용)
#   2) 38 수요예측결과 목록: 기관경쟁률·의무보유확약 비율
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
if __name__=='__main__':
    L=listing(); L.to_csv('data/ipo/list38.csv',index=False); print('신규상장',len(L),L.date.min(),L.date.max())
    D=demand(); pd.DataFrame(D).to_csv('data/ipo/demand38_raw.csv',index=False,header=False); print('수요예측',len(D))
    todo=L[L.code.notna()&(L.date<=time.strftime('%Y-%m-%d'))]
    with ThreadPoolExecutor(6) as ex:
        res=list(ex.map(lambda r:bars(r.code,r.date),todo.itertuples()))
    print('일봉',sum(1 for _,n in res if n>0),'/',len(res))
