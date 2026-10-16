# 바이오·2차전지·에너지(정유/원전·전력)로 미국 밤사이 신호 확장 검증 (python3 sector_signal.py, 약 1분)
#   규칙은 us_signal.py와 같음: 미국 신호 → 한국 시가 매수 → 다음 거래일 시가(또는 당일 종가) 매도, 수수료·거래세 포함
#   추가 데이터: fetch.py의 ETF·STK·US 목록(KODEX 바이오·TIGER 헬스케어·KODEX 에너지화학·한전기술·한전KPS, USO·XOP·URA·CCJ·LLY·ALB)
import numpy as np, pandas as pd, warnings
from us_signal import frame, U
warnings.filterwarnings('ignore')
SECTORS={
 '바이오':(['XBI','IBB','LLY'],['207940','068270','196170','028300','244580','143860']),
 '2차전지':(['LIT','TSLA','ALB'],['373220','006400','247540','086520','003670','051910','066970','305720','364980']),
 '정유·화학':(['XLE','XOM','USO','XOP'],['096770','010950','117460','011170']),
 '원전·전력':(['URA','CCJ','ETN','VRT'],['034020','052690','051600','015760','267260','298040','010120']),
}
DOWN=[-0.01,-0.015,-0.02,-0.03,-0.04]; UP=[0.01,0.02,0.03]
PER=[('2014','2019'),('2020','2022'),('2023','2026')]
def legs(tk,codes,th,col):
    # 종목별 순수익(신호 없는 날 0)과 신호 여부
    R=[];M=[]
    for c in codes:
        f,_=frame(c,tk); f=f.dropna(subset=[col]); m=(f.sig<=th) if th<0 else (f.sig>=th)
        R.append(f[col].where(m,0.0).rename(c)); M.append(m.rename(c))
    return pd.concat(R,axis=1),pd.concat(M,axis=1)
def stat(r,m):
    x=r.values[m.fillna(False).astype(bool).values]; x=x[~np.isnan(x)]
    days=len(r); port=r.fillna(0).mean(axis=1)
    sh=port.mean()/port.std()*np.sqrt(252) if port.std()>0 else 0
    eq=(1+port).cumprod(); mdd=(eq/eq.cummax()-1).min()
    t=x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan
    return dict(n=len(x),yr=len(x)/(days/252),avg=x.mean()*100 if len(x) else np.nan,win=(x>0).mean()*100 if len(x) else np.nan,t=t,sh=sh,mdd=mdd*100)
def per(r,m):
    out=[]
    for a,b in PER:
        rr,mm=r[a:b],m[a:b]; x=rr.values[mm.fillna(False).astype(bool).values]; x=x[~np.isnan(x)]
        out.append((x.mean()*100 if len(x) else np.nan,len(x)))
    return out
if __name__=='__main__':
    pd.set_option('display.width',250)
    nm=lambda c:U.loc[c,'name'] if c in U.index else c
    print('## 1) 종목별: 미국 신호 하락 기준(다음날 시가 매도) — 거래당 순수익 %, 건수, t')
    best=[]
    for sec,(tks,codes) in SECTORS.items():
        print(f'\n[{sec}]')
        for tk in tks:
            line=[]
            for c in codes:
                cells=[]
                for th in DOWN+UP:
                    r,m=legs(tk,[c],th,'oo_net'); s=stat(r,m)
                    if s['n']>=12: best.append(dict(sec=sec,tk=tk,code=c,th=th,**s,p=per(r,m)))
                    cells.append(f"{th*100:+.1f}:{s['avg']:+.2f}({s['n']})" if s['n'] else f"{th*100:+.1f}:—")
                line.append(f"  {tk}→{nm(c)}: "+' '.join(cells))
            print('\n'.join(line))
    B=pd.DataFrame(best)
    B['stable']=B.p.apply(lambda p:all((a>0) for a,n in p if n>=4) and sum(n>=4 for a,n in p)>=2)
    print('\n## 2) 섹터별 상위 (n≥12, 3개 기간 중 4건 이상 있는 기간 모두 플러스, t 순)')
    for sec in SECTORS:
        g=B[(B.sec==sec)&B.stable&(B.avg>0)].sort_values('t',ascending=False).head(8)
        print(f'\n[{sec}]')
        for _,r in g.iterrows():
            print(f"  {r.tk} {'≤' if r.th<0 else '≥'}{r.th*100:+.1f}% → {nm(r.code)}: 연 {r.yr:.1f}건 · 거래당 {r.avg:+.2f}% · 승률 {r.win:.0f}% · t {r.t:.2f} · Sharpe {r.sh:.2f} · MDD {r.mdd:.0f}% · 기간별 "+' / '.join(f"{a:+.2f}({n})" for a,n in r.p))

# 3) 앱 후보 종목쌍(미국 1종목 → 국내 2종목) — 기간별·최근 3개월·당일 종가 비교
CAND=[('바이오','LLY',-0.03,['244580','143860']),('바이오','LLY',-0.03,['068270','196170']),('바이오','IBB',-0.03,['068270','207940']),
      ('바이오','IBB',-0.03,['244580','068270']),('바이오','LLY',-0.03,['244580','068270']),('바이오','XBI',-0.03,['244580','196170']),
      ('2차전지','LIT',-0.03,['305720','247540']),('2차전지','LIT',-0.02,['305720','247540']),('2차전지','LIT',-0.03,['086520','247540']),
      ('2차전지','LIT',-0.03,['305720','003670']),('2차전지','TSLA',-0.03,['305720','247540']),
      ('정유·화학','XOM',-0.03,['117460','011170']),('정유·화학','XLE',-0.03,['117460','096770']),('정유·화학','XLE',-0.03,['096770','010950']),
      ('원전·전력','VRT',-0.015,['267260','034020']),('원전·전력','ETN',-0.03,['298040','267260']),('원전·전력','URA',-0.03,['034020','052690'])]
def cand_table():
    nm=lambda c:U.loc[c,'name']
    print('\n## 3) 앱 후보 종목쌍 (다음날 시가 매도 / 당일 종가 매도)')
    for sec,tk,th,codes in CAND:
        r,m=legs(tk,codes,th,'oo_net'); s=stat(r,m); p=per(r,m)
        rc,mc=legs(tk,codes,th,'oc_net'); sc=stat(rc,mc)
        r3,m3=r['2026-07-14':],m['2026-07-14':]; x3=r3.values[m3.fillna(False).astype(bool).values]; x3=x3[~np.isnan(x3)]
        print(f"  [{sec}] {tk} ≤{th*100:.1f}% → {'·'.join(nm(c) for c in codes)}: 연 {s['yr']:.1f}건 · 거래당 {s['avg']:+.2f}% · 승률 {s['win']:.0f}% · t {s['t']:.2f} · Sharpe {s['sh']:.2f} · MDD {s['mdd']:.0f}%"
              f" | 기간별 "+' / '.join(f"{a:+.2f}({n})" for a,n in p)+f" | 최근3개월 {x3.mean()*100 if len(x3) else float('nan'):+.2f}%({len(x3)}) | 당일종가 {sc['avg']:+.2f}% Sharpe {sc['sh']:.2f}")
if __name__=='__main__': cand_table()
