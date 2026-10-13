# 국내 주식·ETF 변동성 돌파 백테스트 (일봉, 2014-07~2026-10)
import numpy as np, pandas as pd, sys, itertools
FEE=0.00015            # 매수·매도 수수료(편도)
TAX={'stock':0.0020,'etf':0.0}   # 2026 증권거래세(매도, 코스피는 농특세 포함 0.20%) — 국내 ETF는 면제
U=pd.read_csv('data/kr/universe.csv',dtype=str)
def tick(p,etf):
    if etf: return np.where(p<2000,1,5)
    return np.select([p<2000,p<5000,p<20000,p<50000,p<200000,p<500000],[1,5,10,50,100,500],1000)
def load(code):
    d=pd.read_csv(f'data/kr/{code}.csv',parse_dates=['t']).set_index('t')
    return d[d.index<'2026-10-13']   # 오늘(미완성) 제외
DATA={r.code:(load(r.code),r.type,r.name) for r in U.itertuples()}
def trades(d,typ,k=0.5,filt='ma5',exit='close',slip_ticks=1,slip_pct=0.0,noise=False):
    etf=typ=='etf'
    rng=(d.h-d.l).shift(1)
    if noise:
        kk=(1-(d.c-d.o).abs()/(d.h-d.l).replace(0,np.nan)).rolling(20).mean().shift(1)
        tgt=d.o+kk*rng
    else: tgt=d.o+k*rng
    tk=tick(tgt.values,etf); tgt=np.ceil(tgt/tk)*tk
    ok=(d.h>=tgt)&rng.gt(0)
    if filt=='ma5': ok&=d.o>d.c.rolling(5).mean().shift(1)
    if filt=='ma20': ok&=d.o>d.c.rolling(20).mean().shift(1)
    ent=np.maximum(tgt,d.o)
    ent=(ent+slip_ticks*tick(ent.values,etf))*(1+slip_pct)
    ex=d.c if exit=='close' else d.o.shift(-1)
    r=ex*(1-FEE-TAX[typ])/(ent*(1+FEE))-1
    g=ex/ent-1
    r=r.where(ok&ex.notna(),0.0); g=g.where(ok&ex.notna(),0.0)
    return r,g,ok
def port(codes,start=None,end=None,**kw):
    R=[];G=[];N=[]
    for c in codes:
        d,typ,_=DATA[c]
        r,g,ok=trades(d,typ,**kw); R.append(r.rename(c)); G.append(g.rename(c)); N.append(ok.rename(c))
    R=pd.concat(R,axis=1)[start:end]; G=pd.concat(G,axis=1)[start:end]; N=pd.concat(N,axis=1)[start:end]
    avail=R.notna()
    pr=R.mean(axis=1)            # 종목별 1/N 자금 — 신호 없으면 현금
    nt=int(N.sum().sum()); 
    M=N.fillna(False).astype(bool); tr=R[M].stack().dropna(); gr=G[M].stack().dropna()
    return pr,dict(trades=nt,avg_net=tr.mean(),avg_gross=gr.mean(),win=(tr>0).mean(),expo=N.sum().sum()/avail.sum().sum())
def summ(pr):
    pr=pr.fillna(0); eq=(1+pr).cumprod(); yrs=len(pr)/252
    cagr=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min(); sh=pr.mean()/pr.std()*np.sqrt(252) if pr.std()>0 else 0
    return cagr,mdd,sh
def bh(codes,start=None,end=None):
    rr=pd.concat([DATA[c][0].c.pct_change().rename(c) for c in codes],axis=1)[start:end]
    return rr.mean(axis=1)
