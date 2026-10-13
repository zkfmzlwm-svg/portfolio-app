# 비교용: 업비트 코인 단타 (수수료 0.05% + 슬리피지 0.02% 편도)
#   1) 5분봉 15개 전략 (BTC·ETH, 최근 1년)   2) 일봉 변동성 돌파 (2017-10~)
import numpy as np, pandas as pd
C=0.0005+0.0002
def ld(m,tf): return pd.read_csv(f'data/upbit/{m}_{tf}.csv',parse_dates=['t']).set_index('t')
def ema(x,n): return x.ewm(span=n,adjust=False).mean()
def rsi(c,n=14):
    d=c.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); v=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+u/v)
def statepos(enter,exit_):
    p=np.zeros(len(enter)); s=0
    for i,(a,b) in enumerate(zip(enter,exit_)):
        if s==0 and a: s=1
        elif s==1 and b: s=0
        p[i]=s
    return p
def strategies(d):
    c=d.c; out={}
    for f,s in [(6,48),(12,96),(24,288),(12,48),(48,288)]: out[f'EMA{f}/{s}']=(ema(c,f)>ema(c,s)).astype(float).values
    R=rsi(c)
    for th,ex in [(20,50),(25,50),(30,50),(30,60)]: out[f'RSI<{th}→>{ex}']=statepos((R<th).values,(R>ex).values)
    for n in [12,48,144,288]:
        out[f'돌파{n}봉']=statepos((c>d.h.rolling(n).max().shift(1)).values,(c<d.l.rolling(n//2).min().shift(1)).values)
    m=c.rolling(48).mean(); sd=c.rolling(48).std()
    for k in [2.0,2.5]: out[f'볼린저-{k}σ']=statepos((c<m-k*sd).values,(c>m).values)
    return out
def five_min(m):
    d=ld(m,'5m'); c=d.c; lr=np.log(c).diff().fillna(0).values; rows=[]
    for name,pos in strategies(d).items():
        p=pd.Series(pos).shift(1).fillna(0).values; turn=np.abs(np.diff(np.r_[0,p]))
        g=np.exp((p*lr).sum())-1; n=np.exp((p*lr+np.log(1-C*turn)).sum())-1
        ent=np.where(np.diff(np.r_[0,p])>0)[0]; ex=np.where(np.diff(np.r_[p,0])<0)[0]
        per=c.values[np.minimum(ex,len(c)-1)]/c.values[ent-1]-1
        rows.append([name,len(ent),g,n,per.mean()*100])
    df=pd.DataFrame(rows,columns=['전략','매수횟수','비용전','비용후','거래당총%'])
    print(f'\n== {m} 5분봉 {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d} 보유 {c.iloc[-1]/c.iloc[0]-1:+.1%}  (왕복비용 {2*C*100:.2f}%)')
    print(df.to_string(index=False,float_format=lambda x:f'{x:.3f}'))
def vb(d,k=0.5,ma=5,cost=C):
    tgt=d.o+k*(d.h-d.l).shift(1); hit=(d.h>=tgt)&(d.o>d.c.rolling(ma).mean().shift(1))
    return pd.Series(np.where(hit,d.o.shift(-1).fillna(d.c)*(1-cost)/(tgt*(1+cost))-1,0.0),index=d.index)
def summ(r):
    eq=(1+r).cumprod(); return eq.iloc[-1]**(365/len(r))-1,(eq/eq.cummax()-1).min(),r.mean()/r.std()*np.sqrt(365)
if __name__=='__main__':
    for m in ['KRW-BTC','KRW-ETH']: five_min(m)
    print('\n== 일봉 변동성 돌파 (k=0.5, MA5, 익일 09시 청산)')
    for m in ['KRW-BTC','KRW-ETH','KRW-XRP']:
        d=ld(m,'D').iloc[:-1]
        for lab,x in [('2017-21',d[:'2021-12-31']),('2022-26',d['2022-01-01':])]:
            c,mdd,sh=summ(vb(x)); bc=(x.c.iloc[-1]/x.o.iloc[0])**(365/len(x))-1
            print(f'{m} {lab}: CAGR {c:+.1%} MDD {mdd:.0%} Sharpe {sh:.2f} | 보유 CAGR {bc:+.1%} MDD {(x.c/x.c.cummax()-1).min():.0%}')
