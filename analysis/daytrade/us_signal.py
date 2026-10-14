# 미국 섹터 ETF 밤사이 등락 → 다음날 국내 연계 대형주 매매 검증 (python3 us_signal.py, 약 2분)
#   신호: 직전 한국 거래일 장 마감 이후 끝난 미국 정규장(들)의 종가 등락률
#   매매: 한국 시가 매수(09:00 동시호가) → 당일 종가 매도(또는 다음날 시가) — 동시호가 체결이라 스프레드 없음
import json, numpy as np, pandas as pd, sys
FEE=0.00015; TAX={'stock':0.0020,'etf':0.0}
U=pd.read_csv('data/kr/universe.csv',dtype=str).set_index('code')
def kr(code):
    d=pd.read_csv(f'data/kr/{code}.csv',parse_dates=['t']).set_index('t'); return d[d.index<='2026-10-14']
def us(tk):
    r=json.load(open(f'data/us/{tk}.json'))['chart']['result'][0]; q=r['indicators']['quote'][0]
    idx=pd.to_datetime(r['timestamp'],unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
    return pd.Series(q['close'],index=idx).dropna()
def align(k,c_us):
    # 한국 D의 신호 = (D 전날까지 끝난 마지막 미국 종가) / (직전 한국 거래일 P 전날까지 끝난 마지막 미국 종가) − 1
    D=k.index; P=D.to_series().shift(1)
    pos_d=c_us.index.searchsorted(D,side='left')-1; pos_p=c_us.index.searchsorted(P.fillna(D[0]),side='left')-1
    a=c_us.values[np.clip(pos_d,0,None)]; b=c_us.values[np.clip(pos_p,0,None)]
    s=pd.Series(a/b-1,index=D); s[(pos_d==pos_p)|(pos_p<0)]=np.nan   # 새 미국 세션 없으면 신호 없음
    return s
def frame(code,tk):
    k=kr(code); s=align(k,us(tk)); typ=U.loc[code,'type']
    f=pd.DataFrame({'sig':s,'gap':k.o/k.c.shift(1)-1,'oc':k.c/k.o-1,'oo':k.o.shift(-1)/k.o-1},index=k.index)
    cost=lambda g:(1+g)*(1-FEE-TAX[typ])/(1+FEE)-1
    f['oc_net']=cost(f.oc); f['oo_net']=cost(f.oo)
    return f.dropna(subset=['sig','gap','oc']),typ
def summ(r,days):
    # r: 거래일별 순수익(신호 없으면 0) → CAGR·Sharpe·MDD
    eq=(1+r).cumprod(); yrs=days/252
    return eq.iloc[-1]**(1/yrs)-1,(r.mean()/r.std()*np.sqrt(252) if r.std()>0 else 0),(eq/eq.cummax()-1).min()
def test(f,th,col='oc_net',start=None,end=None):
    g=f[start:end]; m=g.sig>th; r=g[col].where(m,0.0)
    x=g.loc[m,col]; c,sh,mdd=summ(r,len(g))
    t=x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan
    return dict(n=int(m.sum()),per_yr=m.sum()/(len(g)/252),avg=x.mean()*100,gross=g.loc[m,col.split('_')[0]].mean()*100,win=(x>0).mean()*100,t=t,cagr=c*100,sh=sh,mdd=mdd*100)
PAIRS=[('반도체','SOXX',['005930','000660','042700','091160']),('반도체','SOXL',['005930','000660','042700','091160']),
       ('반도체','MU',['000660','005930']),('반도체','NVDA',['000660','005930','042700']),
       ('지수','SPY',['069500']),('지수','EWY',['069500','005930','000660']),('나스닥','QQQ',['069500','035420','035720']),
       ('2차전지','LIT',['373220','006400','247540','003670','305720']),('2차전지','TSLA',['373220','006400','247540','003670']),
       ('에너지','XLE',['096770','010950']),('금융','XLF',['105560','055550','086790']),('금융','KBE',['105560','055550','086790']),
       ('방산','ITA',['012450','064350']),('바이오','XBI',['207940','068270','196170']),('바이오','IBB',['207940','068270','196170']),
       ('자동차','GM',['005380','000270']),('소재','XME',['005490','010130']),('전력','ETN',['010120','267260','298040','034020'])]
if __name__=='__main__':
    pd.set_option('display.width',250)
    F=lambda x:f'{x:.2f}'
    print('## 1) 상관: 미국 신호 vs 한국 시가 갭 / 장중(시가→종가)')
    rows=[]
    for sec,tk,codes in PAIRS:
        for code in codes:
            f,typ=frame(code,tk); rows.append([sec,tk,U.loc[code,'name'],f.sig.corr(f.gap),f.sig.corr(f.oc)])
    T=pd.DataFrame(rows,columns=['섹터','미국','국내','상관_갭','상관_장중'])
    print(T.groupby('섹터')[['상관_갭','상관_장중']].agg(['min','max']).round(2).to_string())
    print('\n## 2) 미국 신호 구간별 한국 시가 갭·장중 평균 % (건수)')
    for tk,codes,bins in [('SOXX',['005930','000660','091160'],[-1,-.03,-.01,0,.01,.03,1]),('SPY',['069500','229200'],[-1,-.015,-.005,0,.005,.015,1])]:
        for code in codes:
            f,_=frame(code,tk); g=f.groupby(pd.cut(f.sig,bins),observed=True).agg(gap=('gap','mean'),oc=('oc','mean'),n=('oc','size'))
            print(f"{tk}→{U.loc[code,'name']}: "+' | '.join(f"{i.left*100:+.1f}~{i.right*100:+.1f}%: 갭 {r.gap*100:+.2f} 장중 {r.oc*100:+.2f} ({r.n})" for i,r in g.iterrows()))
    print('\n## 3) 전략 비교 (거래당 순수익, 수수료 0.015%×2 + 개별주 거래세 0.20%)')
    def leg(tk,th,code,col):
        f,_=frame(code,tk); f=f.dropna(subset=[col]); m=(f.sig<=th) if th<0 else (f.sig>th)
        return f[col].where(m,0.0).rename(code+tk),m.rename(code+tk)
    def strat(name,legs,col):
        L=[leg(*l,col) for l in legs]; R=pd.concat([a for a,_ in L],axis=1).fillna(0); M=pd.concat([b for _,b in L],axis=1).fillna(False)
        r=R.mean(axis=1); out=[name]
        for a,b in [(None,'2019-12-31'),('2020-01-01','2022-12-31'),('2023-01-01',None),(None,None)]:
            rr=r[a:b]; x=R[a:b][M[a:b]].stack().dropna(); c,sh,mdd=summ(rr,len(rr))
            out+=[len(x)/(len(rr)/252),x.mean()*100,(x>0).mean()*100,c*100,sh,mdd*100]
        return out
    S=[('원래안 SOXL>0% → SK하이닉스·삼성전자, 당일 종가',[('SOXL',0,'000660'),('SOXL',0,'005930')],'oc_net'),
       ('원래안 SOXL>+3% → SK하이닉스·삼성전자, 다음날 시가',[('SOXL',0.03,'000660'),('SOXL',0.03,'005930')],'oo_net'),
       ('A SOXX≤−3% → SK하이닉스·삼성전자, 다음날 시가',[('SOXX',-0.03,'000660'),('SOXX',-0.03,'005930')],'oo_net'),
       ('A′ 같은 신호, 당일 종가',[('SOXX',-0.03,'000660'),('SOXX',-0.03,'005930')],'oc_net'),
       ('B SPY≤−1.5% → KODEX 200·코스닥150, 다음날 시가',[('SPY',-0.015,'069500'),('SPY',-0.015,'229200')],'oo_net'),
       ('B′ 같은 신호, 당일 종가',[('SPY',-0.015,'069500'),('SPY',-0.015,'229200')],'oc_net'),
       ('A+B 4종목 (앱 기본값)',[('SOXX',-0.03,'000660'),('SOXX',-0.03,'005930'),('SPY',-0.015,'069500'),('SPY',-0.015,'229200')],'oo_net'),
       ('A 기준 완화 SOXX≤−2%',[('SOXX',-0.02,'000660'),('SOXX',-0.02,'005930')],'oo_net'),
       ('B 기준 완화 SPY≤−1%',[('SPY',-0.01,'069500'),('SPY',-0.01,'229200')],'oo_net')]
    cols=['전략']
    for p in ['14-19','20-22','23-26','전체']: cols+=[f'{p} 연건수',f'{p} 거래당%',f'{p} 승률',f'{p} CAGR',f'{p} Sh',f'{p} MDD']
    T=pd.DataFrame([strat(*x) for x in S],columns=cols)
    for p in ['14-19','20-22','23-26','전체']:
        print(T[['전략']+[c for c in cols if c.startswith(p)]].to_string(index=False,float_format=F)); print()
    print('## 4) 기준별: 미국 하락 ≤ 기준 → 시가 매수 (거래당 순수익 %: 당일 종가 / 다음날 시가, 건수)')
    for tk,code,ths in [('SPY','069500',[-.005,-.01,-.015,-.02,-.03]),('SPY','229200',[-.005,-.01,-.015,-.02,-.03]),
                        ('SOXX','000660',[-.01,-.02,-.03,-.04,-.05]),('SOXX','005930',[-.01,-.02,-.03,-.04,-.05]),('SOXX','091160',[-.01,-.02,-.03,-.04,-.05])]:
        f,_=frame(code,tk); f=f.dropna(subset=['oo_net'])
        print(f"{tk}→{U.loc[code,'name']}: "+' | '.join(f"{th*100:+.1f}%: {f.oc_net[f.sig<=th].mean()*100:+.2f}/{f.oo_net[f.sig<=th].mean()*100:+.2f} ({(f.sig<=th).sum()})" for th in ths))
    print('\n## 5) 신호일 vs 아무 날 (시가→다음날 시가 순수익 %)')
    rows=[]
    for tk,th,code in [('SPY',-0.015,'069500'),('SPY',-0.015,'229200'),('SOXX',-0.03,'000660'),('SOXX',-0.03,'005930')]:
        f,_=frame(code,tk); f=f.dropna(subset=['oo_net']); m=f.sig<=th
        for a,b in [(None,'2019-12-31'),('2020-01-01','2022-12-31'),('2023-01-01',None)]:
            g=f[a:b]; mm=m[a:b]; rows.append([f"{tk}≤{th*100:.1f}%",U.loc[code,'name'],f"{(a or '2014')[:4]}~{(b or '2026')[:4]}",int(mm.sum()),g.oo_net[mm].mean()*100,g.oo_net.mean()*100])
    print(pd.DataFrame(rows,columns=['신호','국내','기간','n','신호일','아무날']).to_string(index=False,float_format=lambda x:f'{x:+.2f}'))
