# 단타 손절·익절 기준 격자 검증 (python3 tp_sl.py, 약 30초)
#   대상: 앱 기본 쌍. A = 미국 급락 다음날 시가 매수 5쌍(반도체·지수·바이오·2차전지·에너지), B = 급등 역추세(인버스 ETF)
#   진입: 신호일 D 시가. 익절 = 시가 +tp% 지정가(호가 올림), 손절 = 시가 −sl%(호가 내림, 그 가격에 체결 가정)
#   기본 청산(익절·손절 모두 안 닿으면): nextopen = D+1 시가(현재 A), close = D 종가(현재 B), d1close = D+1까지 감시 후 D+1 종가
#   d1close는 D+1 시가가 이미 목표가 위/손절가 아래면 시가에 체결.
#   일봉만 있어 같은 날 익절·손절이 둘 다 닿으면 순서를 모른다:
#     pess = 손절 먼저(보수), heur = 양봉이면 저가 먼저(손절), 음봉이면 고가 먼저(익절) — 흔히 쓰는 OHLC 경로 가정
#   비용: 수수료 편도 0.015%, 개별주 거래세 0.20%, 인버스 ETF 매매차익 15.4%(이익에만)
import numpy as np, pandas as pd, warnings
from us_signal import kr, us, align, U
warnings.filterwarnings('ignore')
FEE=0.00015; TAX={'stock':0.0020,'etf':0.0}; GTAX=0.154
PER=[('2014','2019'),('2020','2022'),('2023','2026')]
A=[('반도체','SOXX',-0.03,['000660','005930']),('지수','SPY',-0.015,['069500','229200']),('바이오','LLY',-0.04,['244580','143860']),
   ('2차전지','ALB',-0.04,['305720','086520']),('에너지','XOM',-0.04,['117460','011170'])]
B=[('급등 역추세','QQQ',0.02,['114800','251340'])]
GT={'114800','251340'}
TPS=[None,0.003,0.005,0.007,0.01,0.015,0.02,0.03]
SLS=[None,-0.005,-0.01,-0.015,-0.02,-0.03,-0.05]
def tick(p,etf):
    if etf: return np.where(p<2000,1,5)
    return np.select([p<2000,p<5000,p<20000,p<50000,p<200000,p<500000],[1,5,10,50,100,500],1000)
_cache={}
def leg(tk,th,code):
    key=(tk,th,code)
    if key in _cache: return _cache[key]
    k=kr(code); s=align(k,us(tk)); m=(s<=th) if th<0 else (s>=th)
    d=pd.DataFrame({'o':k.o,'h':k.h,'l':k.l,'c':k.c,'o1':k.o.shift(-1),'h1':k.h.shift(-1),'l1':k.l.shift(-1),'c1':k.c.shift(-1),'sig':m},index=k.index)
    d=d[d.sig.fillna(False).astype(bool)].dropna(subset=['o1'])
    _cache[key]=(d,U.loc[code,'type'],code in GT,len(k)); return _cache[key]
def exits(d,etf,tp,sl,base,path):
    o,h,l,c=d.o.values,d.h.values,d.l.values,d.c.values
    if tp is None: tg=np.full(len(o),np.inf)
    else: r=o*(1+tp); t=tick(r,etf); tg=np.ceil(r/t)*t
    if sl is None: st=np.full(len(o),-np.inf)
    else: r=o*(1+sl); t=tick(r,etf); st=np.floor(r/t)*t
    def intraday(H,L,O,C,fallback):
        ht=H>=tg; hs=L<=st; both=ht&hs
        tfirst=np.zeros(len(O),bool) if path=='pess' else (C<O)
        return np.where(both,np.where(tfirst,tg,st),np.where(ht,tg,np.where(hs,st,fallback)))
    if base=='nextopen': xp=intraday(h,l,o,c,d.o1.values)
    elif base=='close': xp=intraday(h,l,o,c,c)
    else:
        o1,h1,l1,c1=d.o1.values,d.h1.values,d.l1.values,d.c1.values
        day1=intraday(h1,l1,o1,c1,c1); day1=np.where(o1>=tg,o1,np.where(o1<=st,o1,day1))
        xp=intraday(h,l,o,c,day1)
    return xp
def net(o,xp,typ,gt):
    g=xp/o-1
    if gt: g=np.where(g>0,g*(1-GTAX),g); return (1+g)*(1-FEE)/(1+FEE)-1
    return (1+g)*(1-FEE-TAX[typ])/(1+FEE)-1
def evaluate(pairs,tp,sl,base,path):
    xs=[];idx=[];days=0;nleg=0;series=[]
    for _,tk,th,codes in pairs:
        for code in codes:
            d,typ,gt,n=leg(tk,th,code); days=max(days,n); nleg+=1
            x=net(d.o.values,exits(d,typ=='etf',tp,sl,base,path),typ,gt)
            xs.append(x); series.append(pd.Series(x,index=d.index))
    x=np.concatenate(xs); allx=pd.concat(series).sort_index()
    port=pd.concat(series,axis=1).fillna(0).sum(axis=1)/nleg
    full=pd.Series(0.0,index=pd.date_range('2014-07-21','2026-10-14',freq='B')); full.loc[port.index]=port.values
    sh=full.mean()/full.std()*np.sqrt(252); eq=(1+full).cumprod()
    per=[(allx[a:b].mean()*100,(allx[a:b]>0).mean()*100,len(allx[a:b])) for a,b in PER]
    return dict(n=len(x),win=(x>0).mean()*100,avg=x.mean()*100,t=x.mean()/x.std()*np.sqrt(len(x)),sh=sh,mdd=(eq/eq.cummax()-1).min()*100,per=per)
lab=lambda v,s:'없음' if v is None else f"{'+' if s>0 else '−'}{abs(v)*100:g}%"
def grid(name,pairs,bases):
    rows=[]
    for base in bases:
        for path in ['pess','heur']:
            for tp in TPS:
                for sl in SLS:
                    r=evaluate(pairs,tp,sl,base,path); rows.append(dict(base=base,path=path,tp=tp,sl=sl,**r))
    R=pd.DataFrame(rows)
    print(f'\n# {name}')
    for base in bases:
        P=R[(R.base==base)&(R.path=='pess')]
        print(f'\n## 기본 청산 {base} — 승률% / 거래당% (보수: 같은 날 둘 다 닿으면 손절 먼저)')
        print('익절\\손절 | '+' | '.join(lab(s,-1) for s in SLS))
        for tp in TPS:
            q=P[P.tp.apply(lambda v:v==tp if tp is not None else v is None or pd.isna(v))]
            print(f"{lab(tp,1):>6} | "+' | '.join(f"{r.win:.0f} / {r.avg:+.2f}" for _,r in q.iterrows()))
    def show(t,q):
        print(f'\n## {t}')
        for _,r in q.iterrows():
            print(f"  [{r.base}·{r.path}] 익절 {lab(r.tp if not pd.isna(r.tp) else None,1)} · 손절 {lab(r.sl if not pd.isna(r.sl) else None,-1)}: 승률 {r.win:.0f}% · 거래당 {r.avg:+.2f}% · t {r.t:.2f} · Sharpe {r.sh:.2f} · MDD {r.mdd:.0f}% | "
                  +' / '.join(f"{a:+.2f}%·승{w:.0f}({n})" for a,w,n in r.per))
    P=R[R.path=='pess']
    show('승률 상위 5 (보수)',P.sort_values('win',ascending=False).head(5))
    show('승률 상위 5 중 거래당 플러스만 (보수)',P[P.avg>0].sort_values('win',ascending=False).head(5))
    show('Sharpe 상위 5 (보수)',P.sort_values('sh',ascending=False).head(5))
    H=R[R.path=='heur']
    show('Sharpe 상위 5 (OHLC 경로 가정)',H.sort_values('sh',ascending=False).head(5))
    return R
if __name__=='__main__':
    pd.set_option('display.width',250)
    RA=grid('A. 미국 급락 다음날 매수 5쌍 (10종목 합산)',A,['nextopen','d1close','close'])
    RB=grid('B. 급등 역추세 (QQQ ≥ +2% → 인버스 2종)',B,['close','d1close'])
    print('\n## 현재 앱 설정 비교')
    for name,pairs,tp,sl,base in [('A 현재(익절·손절 없음, 다음날 시가)',A,None,None,'nextopen'),('B 현재(+0.5% 익절, 손절 없음, 종가)',B,0.005,None,'close')]:
        r=evaluate(pairs,tp,sl,base,'pess'); print(f"  {name}: 승률 {r['win']:.0f}% · 거래당 {r['avg']:+.2f}% · Sharpe {r['sh']:.2f} · MDD {r['mdd']:.0f}%")
    print('\n## A 쌍별 — 현재 vs 보수 Sharpe 1위 설정')
    best=RA[RA.path=='pess'].sort_values('sh',ascending=False).iloc[0]
    btp=None if pd.isna(best.tp) else best.tp; bsl=None if pd.isna(best.sl) else best.sl
    for p in A:
        c=evaluate([p],None,None,'nextopen','pess'); b=evaluate([p],btp,bsl,best.base,'pess')
        print(f"  {p[0]}: 현재 승률 {c['win']:.0f}% · {c['avg']:+.2f}% · Sh {c['sh']:.2f}  →  익절 {lab(btp,1)}·손절 {lab(bsl,-1)}·{best.base}: 승률 {b['win']:.0f}% · {b['avg']:+.2f}% · Sh {b['sh']:.2f}")
