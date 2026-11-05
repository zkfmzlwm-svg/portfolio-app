# 신규상장일 시가 매수 단타 검증 (python3 -I ipo.py, 약 5초) — 원자료: ipo_fetch.py
#   대상: 2023-06-26(상장일 가격제한폭 공모가 60~400%로 개편) 이후 공모 상장. 스팩·리츠는 따로 본다
#   진입: 상장일 시가(08:30~09:00 동시호가). 시가는 네이버 일봉, 공모가 대비 배율은 38커뮤니케이션 시초가 기준
#   청산: 당일 종가 / 다음날 시가 / 시가 +tp% 지정가 익절(못 닿으면 종가) / 손절 / 5거래일 뒤 종가
#   비용: 수수료 편도 0.015%, 매도 거래세 0.20%
#   일봉만 있어서 같은 날 익절·손절이 둘 다 닿으면 손절 먼저(보수)로 본다
import numpy as np, pandas as pd, re, os, warnings
warnings.filterwarnings('ignore')
FEE=0.00015; TAX=0.0020; START='2023-06-26'; END='2026-11-04'
def tick(p): return np.select([p<2000,p<5000,p<20000,p<50000,p<200000,p<500000],[1,5,10,50,100,500],1000)
def net(g): return (1+g)*(1-FEE-TAX)/(1+FEE)-1
def load():
    L=pd.read_csv('data/ipo/list38.csv',dtype={'code':str}); L=L[(L.date>=START)&(L.date<=END)&L.code.notna()]
    D=pd.read_csv('data/ipo/demand38_raw.csv',header=None,dtype=str).iloc[:,:8]
    D.columns=['name','fdate','band','fix','size','comp','lock','uw']
    n=lambda s:float(re.sub(r'[^\d.]','',s)) if isinstance(s,str) and re.search(r'\d',s) else np.nan
    D['comp']=D.comp.map(lambda s:n(str(s).split(':')[0])); D['lock']=D.lock.map(n); D['size']=D['size'].map(n)
    D['band_hi']=D.band.map(lambda s:n(str(s).split('~')[-1])); D['band_lo']=D.band.map(lambda s:n(str(s).split('~')[0])); D['fix']=D.fix.map(n)
    D=D.drop_duplicates('name')
    rows=[]
    for r in L.itertuples():
        f=f'data/ipo/{r.code}.csv'
        if not os.path.exists(f): continue
        b=pd.read_csv(f,parse_dates=['t']); b=b[b.t>=r.date].reset_index(drop=True)
        if len(b)<2 or b.t[0].strftime('%Y-%m-%d')!=r.date: continue
        adj=r.open38/b.o[0] if r.open38 and r.open38>0 else 1.0     # 이후 액면분할 등으로 수정된 경우 공모가 기준으로 되돌림
        x=dict(name=r.name,date=r.date,code=r.code,offer=r.offer,o=b.o[0],h=b.h[0],l=b.l[0],c=b.c[0],v=b.v[0],o1=b.o[1],h1=b.h[1],l1=b.l[1],c1=b.c[1],
               c5=b.c[min(5,len(b)-1)],adj=adj,spac='스팩' in r.name,reit='리츠' in r.name)
        rows.append(x)
    X=pd.DataFrame(rows).merge(D[['name','comp','lock','size','band_lo','band_hi','fix']],on='name',how='left')
    X['ratio']=X.o*X.adj/X.offer                          # 시초가/공모가
    X['vs_band']=np.where(X.fix>X.band_hi,'상단 초과',np.where(X.fix==X.band_hi,'상단',np.where(X.fix<X.band_lo,'하단 미만','밴드 안')))
    return X
def exits(X,tp=None,sl=None,base='close'):
    o,h,l,c=X.o.values,X.h.values,X.l.values,X.c.values
    tg=np.full(len(o),np.inf) if tp is None else np.ceil(o*(1+tp)/tick(o*(1+tp)))*tick(o*(1+tp))
    st=np.full(len(o),-np.inf) if sl is None else np.floor(o*(1+sl)/tick(o*(1+sl)))*tick(o*(1+sl))
    fb={'close':c,'nextopen':X.o1.values,'d5':X.c5.values,'d1close':X.c1.values}[base]
    ht=h>=tg; hs=l<=st
    xp=np.where(hs,st,np.where(ht,tg,fb))                 # 둘 다 닿으면 손절 먼저(보수)
    return net(xp/o-1)
def st(x):
    x=pd.Series(x); return dict(n=len(x),avg=x.mean()*100,med=x.median()*100,win=(x>0).mean()*100,t=x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan,
                                p10=x.quantile(.1)*100,worst=x.min()*100)
F=lambda d:f"{d['n']}건 · 거래당 {d['avg']:+.2f}% (중앙 {d['med']:+.2f}) · 승률 {d['win']:.0f}% · t {d['t']:.1f} · 하위10% {d['p10']:+.1f}% · 최악 {d['worst']:+.1f}%"
if __name__=='__main__':
    X=load(); X.to_csv('data/ipo/ipo_table.csv',index=False)
    C=X[~X.spac&~X.reit].copy(); S=X[X.spac]
    print(f'# 신규상장일 시가 매수 ({START}~{END}) — 일반 공모 {len(C)}건 · 스팩 {len(S)}건 · 리츠 {int(X.reit.sum())}건')
    print(f"  시초가/공모가 중앙 {C.ratio.median():.2f}배 · 시가가 공모가 아래 {(C.ratio<1).mean()*100:.0f}% · 2배 이상 {(C.ratio>=2).mean()*100:.0f}% · 4배(상한) {(C.ratio>=3.99).mean()*100:.0f}%")
    print(f"  (참고) 공모가 매수 → 상장일 종가: 중앙 {((C.c*C.adj/C.offer)-1).median()*100:+.1f}%, 평균 {((C.c*C.adj/C.offer)-1).mean()*100:+.1f}%")
    print('\n## 1) 청산 방식별 (일반 공모 전체)')
    for lab,kw in [('당일 종가',dict(base='close')),('다음날 시가',dict(base='nextopen')),('다음날 종가',dict(base='d1close')),('5거래일 뒤 종가',dict(base='d5'))]:
        print(f'  {lab}: '+F(st(exits(C,**kw))))
    print('\n## 2) 익절·손절 격자 (당일 종가 청산, 승률% / 거래당%)')
    TPS=[None,0.02,0.03,0.05,0.1,0.2]; SLS=[None,-0.03,-0.05,-0.1,-0.2]
    print('  익절\\손절 | '+' | '.join('없음' if s is None else f'{s*100:g}%' for s in SLS))
    for tp in TPS:
        print(f"  {'없음' if tp is None else f'+{tp*100:g}%':>6} | "+' | '.join((lambda d:f"{d['win']:.0f} / {d['avg']:+.2f}")(st(exits(C,tp,sl))) for sl in SLS))
    print('\n## 3) 시초가/공모가 구간별 (당일 종가 청산)')
    for a,b in [(0,1),(1,1.3),(1.3,1.7),(1.7,2.2),(2.2,3),(3,3.99),(3.99,9)]:
        g=C[(C.ratio>=a)&(C.ratio<b)]
        if len(g): print(f'  {a:.2f}~{b:.2f}배: '+F(st(exits(g)))+f" | 장중 고가 시가 대비 중앙 +{((g.h/g.o)-1).median()*100:.1f}%")
    print('\n## 4) 상장 전 알 수 있는 정보별 (당일 종가 청산)')
    C['comp_q']=pd.cut(C.comp,[0,300,700,1000,5000],labels=['<300:1','300~700','700~1000','≥1000:1'])
    C['lock_q']=pd.cut(C.lock,[-1,1,5,15,100],labels=['<1%','1~5%','5~15%','≥15%'])
    C['size_q']=pd.cut(C['size'],[0,15000,30000,100000,1e9],labels=['<150억','150~300억','300~1000억','≥1000억'])
    for col,lab in [('comp_q','기관경쟁률'),('lock_q','의무보유확약'),('size_q','공모금액'),('vs_band','확정가 vs 희망밴드')]:
        print(f'  [{lab}]')
        for k,g in C.groupby(col,observed=True):
            print(f'    {k}: '+F(st(exits(g)))+f" · 시초/공모 중앙 {g.ratio.median():.2f}배")
    print('\n## 5) 지정가로 구현 가능한 필터: 시초가 ≤ 공모가 × X 일 때만 체결 (동시호가 지정가 매수)')
    for X_ in [1.0,1.2,1.5,2.0,2.5,3.0]:
        g=C[C.ratio<=X_]; print(f'  ≤ {X_:.1f}배: 당일 종가 '+F(st(exits(g)))+' | 다음날 시가 '+(lambda d:f"{d['avg']:+.2f}% 승률 {d['win']:.0f}%")(st(exits(g,base='nextopen'))))
    print('\n## 6) 연도별 (당일 종가)')
    for y,g in C.groupby(C.date.str[:4]): print(f'  {y}: '+F(st(exits(g))))
    print('\n## 7) 스팩 (당일 종가 / 다음날 시가)')
    print('  당일 종가: '+F(st(exits(S)))); print('  다음날 시가: '+F(st(exits(S,base='nextopen'))))
    print('\n## 8) 손절 체결 가정 민감도 (당일 종가 청산) — 손절가보다 s% 더 낮게 체결될 때')
    for sl in [-0.03,-0.05,-0.1]:
        cells=[]
        for s in [0,0.01,0.02,0.05]:
            o,l=C.o.values,C.l.values; stp=np.floor(o*(1+sl)/tick(o*(1+sl)))*tick(o*(1+sl)); hit=l<=stp
            xp=np.where(hit,np.maximum(stp*(1-s),l),C.c.values); x=net(xp/o-1); cells.append(f"s {s*100:g}%: {x.mean()*100:+.2f}%")
        print(f'  손절 {sl*100:g}% (닿은 비율 {(C.l.values<=np.floor(C.o.values*(1+sl))).mean()*100:.0f}%): '+' · '.join(cells))
    print('\n## 9) 대형 공모 (공모금액 기준) — 청산 방식별')
    for lo in [50000,100000]:
        g=C[C['size']>=lo]
        for lab,kw in [('당일 종가',dict(base='close')),('다음날 시가',dict(base='nextopen')),('5거래일',dict(base='d5'))]:
            print(f'  ≥{lo//100}억 {lab}: '+F(st(exits(g,**kw))))
    print('\n## 10) 데이터 점검')
    print(f"  네이버 시가 vs 38 시초가 배율(수정 여부): 중앙 {C.adj.median():.3f}, 1에서 1% 넘게 다른 종목 {int(((C.adj-1).abs()>0.01).sum())}건")
    print(f"  시초가 4배(상한가 시작) {int((C.ratio>=3.99).sum())}건 — 매수 대기 물량이 많아 실제로는 체결이 어려움")
