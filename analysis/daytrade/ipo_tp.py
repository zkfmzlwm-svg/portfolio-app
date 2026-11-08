# 신규상장일 '공모가 × N배 지정가 매수 + 매수가 +x% 지정가 매도' 설계 검증 (python3 -I ipo_tp.py, 약 5초) — 원자료: ipo_fetch.py, ipo.py
#   매수: 08:30~09:00 동시호가에 지정가 L = 공모가 × N (호가 내림). 시초가 P ≤ L이면 시초가 P에 체결
#         A안: 09:00에 미체결분 취소 / B안: 취소 안 함(장중 L까지 내려오면 L에 체결)
#   매도: 체결 직후 지정가 T = P × (1 + x%) (호가 올림). 상장일 상한가 = 공모가 × 4 → T가 넘으면 T = 공모가 × 4
#         장중 고가 ≥ T면 체결(낙관) / 고가 ≥ T + 1호가면 체결(보수, 대기 순서 고려)
#         못 팔면: 당일 종가(15:20~15:30 동시호가 시장가) 또는 다음날 시가
#   시초가 = 상한가(공모가 × 4)면 매수 대기 물량이 많아 미체결로 본다
#   비용: 수수료 편도 0.015%, 거래세 0.20%
import numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
FEE=0.00015; TAX=0.0020
def tick(p): return np.select([p<2000,p<5000,p<20000,p<50000,p<200000,p<500000],[1,5,10,50,100,500],1000)
def up(p): t=tick(p); return np.ceil(p/t)*t
def dn(p): t=tick(p); return np.floor(p/t)*t
def net(g): return (1+g)*(1-FEE-TAX)/(1+FEE)-1
X=pd.read_csv('data/ipo/ipo_table.csv',dtype={'code':str}); X=X[~X.spac&~X.reit].reset_index(drop=True)
# 공모가 기준(수정 전) 가격으로 통일
for c in ['o','h','l','c','o1','h1','l1','c1','c5']: X[c]=X[c]*X.adj
X['cap']=X.offer*4; X['lim_lo']=X.offer*0.6
X['maxup']=X.h/X.o-1; X['head']=X.cap/X.o-1          # 시가 대비 당일 최대상승 / 상한가까지 여유
def sim(N,x,fb='close',strict=False,rest=False,D=None):
    D=X if D is None else D
    F,P,H,Lo,C=D.offer.values,D.o.values,D.h.values,D.l.values,D.c.values
    L=dn(F*N); atcap=P>=D.cap.values*0.999
    fill_a=(P<=L)&~atcap; fill_b=rest&~fill_a&(Lo<=L)&~atcap
    ent=np.where(fill_a,P,np.where(fill_b,L,np.nan))
    T=np.minimum(up(ent*(1+x)),D.cap.values)
    need=T+np.where(strict,tick(T),0)
    need=np.where(T>=D.cap.values,T,need)            # 상한가 매도는 대기 매수가 있어 고가=상한가면 체결
    hit=np.where(fill_a,H>=need,C>=need)             # B안 장중 체결분은 종가가 목표 이상일 때만 확실히 익절(보수)
    fbp={'close':C,'nextopen':D.o1.values,'d1close':D.c1.values}[fb]
    xp=np.where(hit,T,fbp); r=net(xp/ent-1)
    m=fill_a|fill_b
    return pd.DataFrame({'date':D.date.values,'ret':r,'hit':hit,'fill':m,'ratio':D.ratio.values})[m]
def st(R,n_all=None):
    x=R.ret; n=len(x)
    if n<3: return dict(n=n,fill=np.nan,hit=np.nan,avg=np.nan,win=np.nan,t=np.nan,miss=np.nan,worst=np.nan,tot=np.nan)
    return dict(n=n,hit=R.hit.mean()*100,avg=x.mean()*100,win=(x>0).mean()*100,t=x.mean()/x.std()*np.sqrt(n),
                miss=x[~R.hit].mean()*100 if (~R.hit).any() else np.nan,worst=x.min()*100,tot=x.sum()*100)
F=lambda d:(f"{d['n']}건 · 익절 {d['hit']:.0f}% · 거래당 {d['avg']:+.2f}% · 승률 {d['win']:.0f}% · t {d['t']:.1f} · 못 판 날 평균 {d['miss']:+.1f}% · 최악 {d['worst']:+.1f}%" if d['n']>=3 else f"{d['n']}건")
if __name__=='__main__':
    pd.set_option('display.width',250)
    print(f'# 신규상장 {len(X)}건 ({X.date.min()}~{X.date.max()}, 스팩·리츠 제외)')
    print('\n## 1) 상장일 최대상승(시가 → 장중 고가)과 상한가 여유')
    q=X.maxup.quantile([.1,.25,.5,.75,.9])*100
    print('  시가 대비 장중 최대상승: '+' · '.join(f"{int(k*100)}% 분위 +{v:.1f}%" for k,v in q.items())+f" · 평균 +{X.maxup.mean()*100:.1f}%")
    print('  최대상승 ≥ x% 비율(= 낙관 익절 확률): '+' · '.join(f"+{x}% {(X.maxup>=x/100).mean()*100:.0f}%" for x in [1,2,3,5,7,10,15,20,30,50]))
    print(f"  상한가(공모가 4배) 도달: {(X.h>=X.cap*0.999).mean()*100:.1f}% · 시가 대비 상한가 여유 중앙 +{X['head'].median()*100:.0f}%")
    print('  시초가 배율 구간별 최대상승 중앙 / 여유 중앙 / 종가 수익 중앙:')
    for a,b in [(0,1),(1,1.3),(1.3,1.7),(1.7,2.2),(2.2,3),(3,4)]:
        g=X[(X.ratio>=a)&(X.ratio<b)]
        print(f"    {a:.1f}~{b:.1f}배 ({len(g)}건): 최대상승 +{g.maxup.median()*100:.1f}% (75% 분위 +{g.maxup.quantile(.75)*100:.1f}%) · 여유 +{g['head'].median()*100:.0f}% · 시가→종가 {(g.c/g.o-1).median()*100:+.1f}%")
    NS=[1.0,1.2,1.5,2.0,2.5,3.0,4.0]; XS=[0.01,0.02,0.03,0.05,0.07,0.10,0.15,0.20,0.30]
    for fb in ['close','nextopen']:
        for strict in [False,True]:
            print(f"\n## 2) 격자 A안(09:00 취소) · 못 팔면 {'당일 종가' if fb=='close' else '다음날 시가'} · {'보수(+1호가)' if strict else '낙관'} 체결 — 거래당 % (익절률 %)")
            print('  N \\ x   | '+' | '.join(f'+{x*100:g}%' for x in XS)+' | 체결 건수')
            for N in NS:
                cells=[]
                for x in XS:
                    d=st(sim(N,x,fb,strict)); cells.append(f"{d['avg']:+.2f} ({d['hit']:.0f})")
                print(f"  ≤{N:.1f}배 | "+' | '.join(cells)+f" | {st(sim(N,0.05,fb,strict))['n']}")
    print('\n## 3) 상위 조합 (A안 보수 체결, 당일 종가, 체결 ≥ 30건) — 학습 2023-06~2024 / 검증 2025~')
    rows=[]
    for N in NS:
        for x in XS:
            for fb in ['close','nextopen']:
                R=sim(N,x,fb,True); d=st(R); tr=st(R[R.date<'2025']); te=st(R[R.date>='2025'])
                rows.append(dict(N=N,x=x,fb=fb,**d,tr_avg=tr['avg'],tr_n=tr['n'],te_avg=te['avg'],te_n=te['n'],te_t=te['t']))
    T=pd.DataFrame(rows); T=T[T.n>=30]
    for _,r in T.sort_values('tr_avg',ascending=False).head(10).iterrows():
        print(f"  N ≤{r.N:.1f} · x +{r.x*100:g}% · 못 팔면 {'종가' if r.fb=='close' else '다음날 시가'}: 학습 {r.tr_avg:+.2f}% ({r.tr_n}) → 검증 {r.te_avg:+.2f}% ({r.te_n}, t {r.te_t:.1f}) | 전체 {r.avg:+.2f}% · 익절 {r.hit:.0f}% · 승률 {r.win:.0f}% · 못 판 날 {r.miss:+.1f}%")
    print(f"  플러스 조합: 전체 {(T.avg>0).sum()}/{len(T)} · 학습·검증 둘 다 플러스 {((T.tr_avg>0)&(T.te_avg>0)).sum()}")
    print('\n## 4) B안(09:00에 취소 안 함 — 장중 L까지 내려오면 체결, 보수: 종가 ≥ 목표일 때만 익절)')
    for N in [1.0,1.2,1.5,2.0]:
        for x in [0.03,0.05,0.10]:
            R=sim(N,x,'close',True,rest=True); print(f"  N ≤{N:.1f} · x +{x*100:g}%: "+F(st(R)))
    print('\n## 5) 손익 구조: 익절 확률 p, 못 판 날 평균 손실 m → 손익분기 p* = |m| / (x + |m|)')
    for N in [1.2,1.5,2.0,4.0]:
        for x in [0.02,0.05,0.10]:
            d=st(sim(N,x,'close',True)); m=abs(d['miss'])/100; xx=x-0.0023
            print(f"  N ≤{N:.1f} · x +{x*100:g}%: 익절 {d['hit']:.0f}% vs 손익분기 {m/(xx+m)*100:.0f}% (못 판 날 {d['miss']:+.1f}%)")
