# 신규상장일 60분봉(야후, 2024-11~)으로 '지정가 매수 + x% 익절 + 시간 손절' 검증 (python3 -I ipo_intraday.py)
#   일봉으로는 '못 팔면 종가'만 볼 수 있음 → 60분봉으로 '첫 1시간(또는 k시간) 안에 못 팔면 그 봉 종가에 매도'를 본다
#   야후 60분봉 첫 봉 = 09:00~10:00. 시가는 네이버 일봉 시가와 맞는 종목만 쓴다(차이 0.5% 이내)
import numpy as np, pandas as pd, os, warnings
from ipo_tp import X, up, dn, tick, net
warnings.filterwarnings('ignore')
rows=[]
for r in X.itertuples():
    f=f'data/ipo/{r.code}_60m.csv'
    if not os.path.exists(f): continue
    b=pd.read_csv(f,parse_dates=['t']).sort_values('t'); b=b[b.t.dt.hour>=9]
    if len(b)<4: continue
    k=r.o/b.o.iloc[0]                       # 야후 가격 단위를 일봉(공모가 기준)에 맞춤
    if abs(b.o.iloc[0]*k/r.o-1)>0.005 or abs(b.h.max()*k/r.h-1)>0.03: continue
    rows.append(dict(code=r.code,name=r.name,date=r.date,offer=r.offer,P=r.o,H=r.h,C=r.c,ratio=r.ratio,cap=r.cap,
                     hh=list(b.h*k),hl=list(b.l*k),hc=list(b.c*k)))
I=pd.DataFrame(rows)
def sim(N,x,k_hours,strict=True,sl=None):
    out=[]
    for r in I.itertuples():
        L=dn(np.array(r.offer*N)); 
        if not (r.P<=L) or r.P>=r.cap*0.999: continue
        T=min(up(np.array(r.P*(1+x))),r.cap); need=T if T>=r.cap else T+(tick(np.array(T)) if strict else 0)
        S=None if sl is None else dn(np.array(r.P*(1+sl)))
        xp=None; hit=False
        for i,(h,l,c) in enumerate(zip(r.hh,r.hl,r.hc)):
            if S is not None and l<=S and h>=need: xp=S; break          # 같은 봉에 둘 다 → 손절 먼저(보수)
            if h>=need: xp=T; hit=True; break
            if S is not None and l<=S: xp=S; break
            if i+1>=k_hours: xp=c; break
        if xp is None: xp=r.C
        out.append(dict(date=r.date,ret=float(net(xp/r.P-1)),hit=hit))
    return pd.DataFrame(out)
def st(R):
    x=R.ret; return f"{len(x)}건 · 익절 {R.hit.mean()*100:.0f}% · 거래당 {x.mean()*100:+.2f}% · 승률 {(x>0).mean()*100:.0f}% · t {x.mean()/x.std()*np.sqrt(len(x)):.1f} · 못 판 날 {x[~R.hit].mean()*100 if (~R.hit).any() else float('nan'):+.1f}% · 최악 {x.min()*100:+.1f}%"
if __name__=='__main__':
    print(f'# 60분봉 검증 대상 {len(I)}건 ({I.date.min()}~{I.date.max()})')
    first=pd.Series([r.hh[0]/r.P-1 for r in I.itertuples()]); allh=pd.Series([max(r.hh)/r.P-1 for r in I.itertuples()])
    when=pd.Series([int(np.argmax(r.hh)) for r in I.itertuples()])
    print(f"  장중 고가가 나온 시간: 09시대 {(when==0).mean()*100:.0f}% · 10시대 {(when==1).mean()*100:.0f}% · 11시 이후 {(when>=2).mean()*100:.0f}%")
    print('  첫 1시간 최대상승 ≥ x% 비율: '+' · '.join(f"+{x}% {(first>=x/100).mean()*100:.0f}%" for x in [1,2,3,5,10,20]))
    print('\n## 일봉 방식(못 팔면 종가)과 같은 표본에서 비교 — 보수 체결(+1호가)')
    for N in [1.5,2.0,4.0]:
        for x in [0.02,0.03,0.05,0.10]:
            print(f"  N ≤{N:.1f} · x +{x*100:g}%  | 종가까지 {st(sim(N,x,99))}")
            for kh in [1,2]:
                print(f"  {'':16} | {kh}시간 뒤 시간손절 {st(sim(N,x,kh))}")
    print('\n## 손절 추가 (같은 봉에 익절·손절 둘 다 닿으면 손절 먼저 = 보수)')
    for N in [1.5,2.0,4.0]:
        for x,sl in [(0.03,-0.05),(0.05,-0.05),(0.05,-0.10),(0.10,-0.10)]:
            print(f"  N ≤{N:.1f} · x +{x*100:g}% · 손절 {sl*100:g}%: {st(sim(N,x,99,sl=sl))}")
    print('\n## 5분봉 사례 (최근 60일, 상장일 데이터 있는 종목만) — 시가 대비 +x% 첫 도달 시각 · 그 전 최저')
    for r in X.itertuples():
        f=f'data/ipo/{r.code}_5m.csv'
        if not os.path.exists(f): continue
        b=pd.read_csv(f,parse_dates=['t']).sort_values('t'); b=b[b.t.dt.hour>=9]
        if not len(b): continue
        k=r.o/b.o.iloc[0]; h=b.h*k; l=b.l*k; tm=b.t.dt.strftime('%H:%M')
        cells=[]
        for x in [0.02,0.03,0.05,0.10]:
            idx=np.where(h.values>=r.o*(1+x))[0]
            if len(idx): i=idx[0]; cells.append(f"+{x*100:g}% {tm.iloc[i]}(그 전 최저 {l.values[:i+1].min()/r.o*100-100:+.1f}%)")
            else: cells.append(f"+{x*100:g}% 미도달")
        print(f"  {r.name} {r.date} 시초 {r.ratio:.2f}배 · 종가 {r.c/r.o*100-100:+.1f}%: "+' · '.join(cells))
