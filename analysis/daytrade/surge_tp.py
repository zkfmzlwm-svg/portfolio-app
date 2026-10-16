# 급등 다음날 당일 익절 전략 검증 (python3 surge_tp.py, 약 20초)
#   규칙: 미국 급등(≥ +X%) 다음 한국 거래일 시가 매수 → 시가 +tp% 지정가 익절, 못 닿으면 당일 종가 매도
#   일봉만 있어서 '장중 고가 ≥ 목표가'면 목표가에 체결됐다고 본다(낙관). 보수 기준은 목표가 + 1호가까지 올라야 체결.
#   비용: 수수료 편도 0.015%, 개별주 매도 거래세 0.20%, 국내 ETF 거래세 면제, 레버리지·인버스 ETF는 매매차익 15.4% 과세(이익에만).
#   목표가는 목표 가격대의 호가단위로 올림(앱 dtTpPrice와 같음).
import numpy as np, pandas as pd, warnings
from us_signal import kr, us, align, U
warnings.filterwarnings('ignore')
FEE=0.00015; TAX={'stock':0.0020,'etf':0.0}; GTAX=0.154
PER=[('2014','2019'),('2020','2022'),('2023','2026')]
LONG=[('반도체','SOXX',['000660','005930']),('지수','SPY',['069500','229200']),('바이오','LLY',['244580','143860']),
      ('2차전지','ALB',['305720','086520']),('에너지','XOM',['117460','011170'])]
INV=['114800','251340']   # KODEX 인버스, KODEX 코스닥150선물인버스 (fetch: data/kr, universe에 etf로 추가)
def tick(p,etf):
    if etf: return np.where(p<2000,1,5)
    return np.select([p<2000,p<5000,p<20000,p<50000,p<200000,p<500000],[1,5,10,50,100,500],1000)
def day_net(code,tp,strict=False,sl=None,worst=True):
    k=kr(code); typ=U.loc[code,'type']; etf=typ=='etf'; gt=etf and code in INV
    o,h,l,c=k.o.values,k.h.values,k.l.values,k.c.values
    raw=o*(1+tp); t=tick(raw,etf); tg=np.ceil(raw/t)*t
    ht=h>=(tg+t if strict else tg)
    if sl is None: g=np.where(ht,tg/o,c/o)
    else:
        rs=o*(1+sl); ts=tick(rs,etf); st=np.floor(rs/ts)*ts; hs=l<=st
        g=np.where(ht&hs,np.where(worst,st/o,tg/o),np.where(ht,tg/o,np.where(hs,st/o,c/o)))
    g=g-1
    if gt: g=np.where(g>0,g*(1-GTAX),g); net=(1+g)*(1-FEE)/(1+FEE)-1
    else: net=(1+g)*(1-FEE-TAX[typ])/(1+FEE)-1
    return pd.DataFrame({'net':net,'hit':ht},index=k.index)
def run(tk,codes,th,tp,**kw):
    R=[];H=[];M=[]
    for c in codes:
        d=day_net(c,tp,**kw); s=align(kr(c),us(tk)); d['sig']=s; d=d.dropna(subset=['sig'])
        m=d.sig>=th; R.append(d.net.where(m,0.0).rename(c)); H.append(d.hit.where(m).rename(c)); M.append(m.rename(c))
    r=pd.concat(R,axis=1); h=pd.concat(H,axis=1); m=pd.concat(M,axis=1).fillna(False).astype(bool)
    x=r.values[m.values]; x=x[~np.isnan(x)]; hh=h.values[m.values]; hh=hh[~pd.isna(hh)].astype(bool)
    q=r.fillna(0).mean(axis=1); eq=(1+q).cumprod(); sh=q.mean()/q.std()*np.sqrt(252) if q.std()>0 else 0
    per=[]
    for a,b in PER:
        xx=r[a:b].values[m[a:b].values]; xx=xx[~np.isnan(xx)]; qq=q[a:b]
        per.append((xx.mean()*100 if len(xx) else np.nan,len(xx),qq.mean()/qq.std()*np.sqrt(252) if qq.std()>0 else 0))
    r3=r['2026-07-14':]; x3=r3.values[m['2026-07-14':].values]; x3=x3[~np.isnan(x3)]
    return dict(n=len(x),yr=len(x)/(len(q)/252),hit=hh.mean()*100 if len(hh) else np.nan,avg=x.mean()*100 if len(x) else np.nan,
                win=(x>0).mean()*100 if len(x) else np.nan,sh=sh,mdd=(eq/eq.cummax()-1).min()*100,per=per,
                m3=(x3.mean()*100 if len(x3) else np.nan,len(x3)))
def fmt(s,periods=True):
    out=f"연 {s['yr']:.0f} · 도달 {s['hit']:.0f}% · 거래당 {s['avg']:+.2f}% · 승 {s['win']:.0f}% · Sh {s['sh']:.2f} · MDD {s['mdd']:.0f}%"
    if periods: out+=" | "+' / '.join(f"{a:+.2f}({n}, Sh {sh:.2f})" for a,n,sh in s['per'])+f" | 최근3개월 {s['m3'][0]:+.2f}({s['m3'][1]})"
    return out
if __name__=='__main__':
    print('## 1) 원안: 미국 급등 다음날 종목 시가 매수 → +tp% 익절 / 못 닿으면 당일 종가 (낙관 체결)')
    for sec,tk,codes in LONG:
        print(f'\n[{sec}] {tk} → '+'·'.join(U.loc[c,'name'] for c in codes))
        for th in [0.0001,0.01,0.02,0.03]:
            for tp in [0.005,0.007,0.01]:
                print(f"  {tk} ≥ +{th*100:.0f}% · 익절 +{tp*100:.1f}%: "+fmt(run(tk,codes,th,tp),periods=False))
    print('\n## 2) 손절 추가 (낙관 = 같은 날 익절·손절 둘 다 닿으면 익절 먼저 / 비관 = 손절 먼저)')
    for tk,codes in [('SOXX',['000660','005930']),('SPY',['069500','229200'])]:
        for th in [0.01,0.02]:
            for tp,sl in [(0.005,-0.005),(0.005,-0.01),(0.01,-0.01),(0.01,-0.02)]:
                b=run(tk,codes,th,tp,sl=sl,worst=False); w=run(tk,codes,th,tp,sl=sl,worst=True)
                print(f"  {tk} ≥ +{th*100:.0f}% · 익절 +{tp*100:.1f}% / 손절 {sl*100:.1f}%: 낙관 {b['avg']:+.2f}% · 비관 {w['avg']:+.2f}% ({b['n']}건)")
    print('\n## 3) 뒤집기: 미국 급등 다음날 인버스 ETF 시가 매수 → +tp% 익절 / 당일 종가 (차익과세 15.4% 반영)')
    for tk in ['QQQ','SPY','SOXX','NVDA','EWY']:
        for th in [0.015,0.02,0.025,0.03]:
            for tp in ([0.003,0.005,0.007,0.01] if tk=='QQQ' else [0.005]):
                print(f"  {tk} ≥ +{th*100:.1f}% · 익절 +{tp*100:.1f}%: "+fmt(run(tk,INV,th,tp)))
    print('\n## 4) 앱 기본값 QQQ ≥ +2% · 익절 +0.5% — 보수 체결(+1호가) / 익절 없이 종가')
    print('  보수 체결: '+fmt(run('QQQ',INV,0.02,0.005,strict=True)))
    print('  당일 종가: '+fmt(run('QQQ',INV,0.02,9.0)))
