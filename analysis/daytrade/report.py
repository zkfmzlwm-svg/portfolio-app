# 국내 변동성 돌파 — README 표 재현 (약 5분)
from vb import *
import vb as V
pd.set_option('display.width',220)
F=lambda x:f'{x:.3f}'
CORE_ETF=['069500','229200','122630','233740','091160','102110']   # 2015 이전 상장 지수·섹터 ETF(레버리지 포함)
G=['069500','229200','091160','305720']   # 비레버리지 국내주식형 ETF — 증권거래세·매매차익 비과세
STKS=list(U[U.type=='stock'].code)
TR=(None,'2019-12-31'); TE=('2020-01-01',None)

print('## 1) 전체 그리드 (2014-07~2026-10)')
for gname,codes in [('ETF 6종(레버리지 포함, 비과세 가정)',CORE_ETF),('개별주 70종목(세금 0.2%)',STKS)]:
    b=summ(bh(codes)); print(f'\n### {gname}  동일비중 보유 CAGR {b[0]:+.1%} MDD {b[1]:.0%} Sharpe {b[2]:.2f}')
    rows=[]
    for k,f,ex in itertools.product([0.3,0.5,0.7],['none','ma5','ma20'],['close','nextopen']):
        pr,s=port(codes,k=k,filt=f,exit=ex); c,m,sh=summ(pr)
        rows.append([k,f,ex,c,m,sh,s['trades'],s['expo'],s['win'],s['avg_gross']*100,s['avg_net']*100])
    print(pd.DataFrame(rows,columns=['k','필터','청산','CAGR','MDD','Sharpe','거래수','보유비중','승률','거래당총%','거래당순%']).to_string(index=False,float_format=F))

print('\n## 2) 학습(2014-07~2019) 최적 → 검증(2020~2026-10)')
for gname,codes in [('ETF 6종',CORE_ETF),('ETF 4종(비레버리지)',G),('개별주',STKS)]:
    res=[]
    for k,f,ex in itertools.product([0.3,0.4,0.5,0.6,0.7,0.8],['none','ma5','ma20'],['close','nextopen']):
        res.append((k,f,ex,summ(port(codes,*TR,k=k,filt=f,exit=ex)[0]),summ(port(codes,*TE,k=k,filt=f,exit=ex)[0])))
    best=max(res,key=lambda x:x[3][2])
    tr_s=pd.Series([x[3][2] for x in res]); te_s=pd.Series([x[4][2] for x in res])
    bt=summ(bh(codes,*TE))
    print(f'{gname}: 학습 최적 k={best[0]} {best[1]} {best[2]} → 학습 Sharpe {best[3][2]:.2f} | 검증 Sharpe {best[4][2]:.2f} CAGR {best[4][0]:+.1%} MDD {best[4][1]:.0%}'
          f' | 순위상관 {tr_s.rank().corr(te_s.rank()):.2f} | 검증 Sharpe>0 {(te_s>0).mean():.0%} | 검증 보유 CAGR {bt[0]:+.1%} Sharpe {bt[2]:.2f} MDD {bt[1]:.0%}')
    for ex in ['close','nextopen']:
        sub=[x for x in res if x[2]==ex]
        print(f'   청산={ex:8s} 검증 Sharpe 중앙값 {np.median([x[4][2] for x in sub]):.2f}, CAGR 중앙값 {np.median([x[4][0] for x in sub]):+.1%}')

print('\n## 3) 비레버리지 ETF 4종 — 설정별 검증(2020~) + 수동 주문 지연 슬리피지')
rows=[]
for k,f in itertools.product([0.3,0.5,0.7],['none','ma5','ma20']):
    out=[k,f]
    for sp in [0,0.001,0.002]:
        pr,s=port(G,*TE,k=k,filt=f,exit='nextopen',slip_pct=sp); c,m,sh=summ(pr)
        out+= [c,sh] if sp else [c,m,sh,s['win'],s['avg_net']*100,s['trades']/(len(pr)/252)]
    pr,_=port(G,*TE,k=k,filt=f,exit='close'); c,_,sh=summ(pr); out+=[c,sh]
    rows.append(out)
print(pd.DataFrame(rows,columns=['k','필터','CAGR','MDD','Sharpe','승률','거래당순%','연간거래','CAGR@+0.1%','Sh@+0.1%','CAGR@+0.2%','Sh@+0.2%','당일청산CAGR','당일청산Sh']).to_string(index=False,float_format=F))

print('\n## 4) 연도별 (ETF 4종, k=0.7, 필터 없음, 익일 시가) vs 보유')
pr,_=port(G,k=0.7,filt='none',exit='nextopen'); bb=bh(G)
print(pd.DataFrame({'전략':(1+pr.fillna(0)).groupby(pr.index.year).prod()-1,'보유':(1+bb.fillna(0)).groupby(bb.index.year).prod()-1}).T.to_string(float_format=lambda x:f'{x:+.0%}'))

print('\n## 5) 세금 효과')
for t in [0.002,0.0]:
    V.TAX['stock']=t; pr,s=port(STKS,k=0.5,filt='ma20',exit='nextopen'); c,m,sh=summ(pr)
    print(f'  개별주 70 (k=0.5, MA20, 익일) 거래세 {t*100:.1f}%: CAGR {c:+.1%} MDD {m:.0%} Sharpe {sh:.2f} 거래당 총 {s["avg_gross"]*100:+.3f}% 순 {s["avg_net"]*100:+.3f}%')
V.TAX['stock']=0.002
for c in ['122630','233740']:
    d,typ,name=DATA[c]; r,g,ok=trades(d,typ,k=0.5,filt='none',exit='nextopen')
    for lab,x in [('비과세 가정',r),('매매차익 15.4% 과세',r.where(r<=0,r*(1-0.154)))]:
        a=summ(x['2020':]); print(f'  {name} {lab}: 2020~ CAGR {a[0]:+.1%} Sharpe {a[2]:.2f}')

print('\n## 6) 종목별 (k=0.5, MA5, 단일 종목 전액) 전체기간')
rows=[]
for r in U.itertuples():
    d,typ,name=DATA[r.code]
    if len(d)<500: continue
    pr,s=port([r.code],k=0.5,filt='ma5',exit='nextopen'); c,m,sh=summ(pr)
    pr2,_=port([r.code],k=0.5,filt='ma5',exit='close'); c2,_,sh2=summ(pr2)
    b=summ(d.c.pct_change()); rows.append([r.code,name,typ,c,sh,c2,sh2,b[0],b[2],s['avg_net']*100])
df=pd.DataFrame(rows,columns=['code','종목','유형','익일CAGR','익일Sh','당일CAGR','당일Sh','보유CAGR','보유Sh','거래당순%'])
print(df[df.유형=='etf'].to_string(index=False,float_format=F))
st=df[df.유형=='stock']
print(f'개별주 {len(st)}종목: 익일청산 CAGR>0 {(st.익일CAGR>0).mean():.0%} Sharpe 중앙 {st.익일Sh.median():.2f} | 당일청산 CAGR>0 {(st.당일CAGR>0).mean():.0%} Sharpe 중앙 {st.당일Sh.median():.2f}')
