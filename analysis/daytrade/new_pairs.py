# 단타 트리거 점검 + 신규 후보 탐색 (python3 new_pairs.py, 약 1분) — v6.8
#   데이터: fetch.py (국내 네이버 일봉 2014-08~, 미국 야후 일봉). 마지막 완결 거래일 END까지 사용
#   규칙: us_signal.py와 같음 — 미국 신호 → 다음 한국 거래일 시가 매수 → (기본) 그다음 거래일 시가 매도
#   비용: 수수료 편도 0.015%, 개별주 거래세 0.20%, 인버스 ETF 매매차익 15.4%(이익에만)
#   1부: 기존 6쌍 — 최신 데이터·기간별·최근 구간·기준 민감도·연도별 전진(walk-forward) 기준·동시 신호
#   2부: 신규 후보 — 학습(2014-08~2021) 구간에서만 고르고, 검증(2022~END) 구간으로 확인
import numpy as np, pandas as pd, warnings
from functools import lru_cache
import us_signal as S
warnings.filterwarnings('ignore')
END='2026-11-03'
_kr0,_us0=S.kr,S.us
@lru_cache(None)
def _kr(code):
    d=pd.read_csv(f'data/kr/{code}.csv',parse_dates=['t']).set_index('t'); return d[d.index<=END]
S.kr=lambda c:_kr(c).copy()
S.us=lru_cache(None)(_us0)
import surge_tp as ST          # S.kr 교체 뒤에 import → 같은 END 적용
ST.kr=S.kr
U=S.U; nm=lambda c:U.loc[c,'name'] if c in U.index else c
TRAIN=('2014','2021'); TEST=('2022',END)
PER=[('2014','2019'),('2020','2022'),('2023',END)]
BDAYS=None
@lru_cache(None)
def fr(code,tk): return S.frame(code,tk)[0]
@lru_cache(None)
def fade(code,tk,tp):
    d=ST.day_net(code,tp); d['sig']=S.align(S.kr(code),S.us(tk)); return d.dropna(subset=['sig'])
def leg(tk,th,code,exit='oo'):
    """신호일 순수익 Series(진입일 index), 그 종목의 아무 날 평균"""
    if exit=='tp':
        d=fade(code,tk,0.005); m=d.sig>=th; return d.net[m],d.net.mean()
    f=fr(code,tk); col='oo_net' if exit=='oo' else 'oc_net'; f=f.dropna(subset=[col])
    m=(f.sig<=th) if th<0 else (f.sig>=th)
    return f[col][m],f[col].mean()
def tstat(x): return x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 and x.std()>0 else np.nan
def port(legs):
    """legs: [Series] → 자금 1/N 균등, 신호 없는 날 현금 기준 일별 수익"""
    idx=pd.bdate_range('2014-08-12',END)
    R=pd.concat([s.groupby(level=0).mean().reindex(idx).fillna(0) for s in legs],axis=1)
    return R.mean(axis=1)
def pstat(r):
    eq=(1+r).cumprod(); sh=r.mean()/r.std()*np.sqrt(252) if r.std()>0 else 0
    return sh,(eq/eq.cummax()-1).min()*100
def sub(x,a,b): return x[a:b]
def fmt_per(x): return ' / '.join(f"{sub(x,a,b).mean()*100:+.2f}({len(sub(x,a,b))})" for a,b in PER)
EXIST=[('반도체','SOXX',-0.03,['000660','005930'],'oo'),('지수','SPY',-0.015,['069500','229200'],'oo'),
       ('바이오','LLY',-0.04,['244580','143860'],'oo'),('2차전지','ALB',-0.04,['305720','086520'],'oo'),
       ('에너지','XOM',-0.04,['117460','011170'],'oo'),('급등 역추세','QQQ',0.02,['114800','251340'],'tp')]
def pair_legs(p,th=None):
    sec,tk,t0,codes,ex=p; return [leg(tk,t0 if th is None else th,c,ex)[0] for c in codes]
def pair_line(p,th=None):
    sec,tk,t0,codes,ex=p; L=pair_legs(p,th); x=pd.concat(L).sort_index(); base=np.mean([leg(tk,t0,c,ex)[1] for c in codes])
    sh,mdd=pstat(port(L)); n_yr=len(x)/((pd.Timestamp(END)-pd.Timestamp('2014-08-12')).days/365.25)
    r12=x['2025-11-04':]; r3=x['2026-08-04':]; oos=x['2026-10-15':]
    return (f"연 {n_yr:.0f}건 · 거래당 {x.mean()*100:+.2f}% (아무 날 {base*100:+.2f}) · 승률 {(x>0).mean()*100:.0f}% · t {tstat(x):.2f} · Sharpe {sh:.2f} · MDD {mdd:.0f}%"
            f"\n      기간별 {fmt_per(x)} | 최근12개월 {r12.mean()*100:+.2f}%({len(r12)}) · 최근3개월 {r3.mean()*100 if len(r3) else float('nan'):+.2f}%({len(r3)}) · 지난 분석 이후(10-15~) {oos.mean()*100 if len(oos) else float('nan'):+.2f}%({len(oos)})")
def wf(p,grid):
    """연도별 전진: Y년 기준 = Y−1년까지 t가 가장 큰 기준(건수 ≥ 10). 2017년부터 적용"""
    sec,tk,t0,codes,ex=p; out=[]
    for Y in range(2017,int(END[:4])+1):
        best=None
        for th in grid:
            x=pd.concat([leg(tk,th,c,ex)[0] for c in codes]).sort_index()[:str(Y-1)]
            if len(x)>=10 and (best is None or tstat(x)>best[1]): best=(th,tstat(x))
        if best is None: continue
        out.append((Y,best[0],pd.concat([leg(tk,best[0],c,ex)[0] for c in codes]).sort_index()[str(Y):str(Y)]))
    x=pd.concat([o[2] for o in out]); f=pd.concat([leg(tk,t0,c,ex)[0] for c in codes]).sort_index()['2017':]
    return x,f,[(Y,th) for Y,th,_ in out]
if __name__=='__main__':
    pd.set_option('display.width',250)
    print(f'# 1부. 기존 6쌍 재검증 (2014-08~{END})')
    for p in EXIST:
        print(f"\n[{p[0]}] {p[1]} {'≥ +' if p[2]>0 else '≤ '}{p[2]*100:g}% → {'·'.join(nm(c) for c in p[3])}{' (+0.5% 익절)' if p[4]=='tp' else ''}")
        print('   '+pair_line(p))
    print('\n## 1-2) 기준 민감도 (거래당 % / 건수 / t, 다음날 시가 · 역추세는 +0.5% 익절)')
    GR={'SOXX':[-.02,-.025,-.03,-.035,-.04],'SPY':[-.01,-.0125,-.015,-.0175,-.02],'LLY':[-.03,-.035,-.04,-.045,-.05],
        'ALB':[-.03,-.035,-.04,-.045,-.05],'XOM':[-.03,-.035,-.04,-.045,-.05],'QQQ':[.015,.0175,.02,.0225,.025]}
    for p in EXIST:
        cells=[]
        for th in GR[p[1]]:
            x=pd.concat(pair_legs(p,th)); cells.append(f"{th*100:+.2f}%: {x.mean()*100:+.2f} ({len(x)}, t {tstat(x):.1f})")
        print(f"  {p[1]}: "+' | '.join(cells))
    print('\n## 1-3) 연도별 전진 기준 (Y년 = Y−1년까지 t 최대 기준) vs 고정 기준, 2017~')
    for p in EXIST:
        x,f,ths=wf(p,GR[p[1]])
        print(f"  {p[1]}: 전진 {x.mean()*100:+.2f}% ({len(x)}, t {tstat(x):.1f}) vs 고정 {f.mean()*100:+.2f}% ({len(f)}, t {tstat(f):.1f}) · 고른 기준 "+' '.join(f"{str(Y)[2:]}:{th*100:g}" for Y,th in ths))
    print('\n## 1-4) 합산 (자금 1/N, 신호 없는 날 현금)')
    for name,ps in [('6쌍 전체',EXIST),('5쌍 (역추세 제외)',EXIST[:5]),('4쌍 (에너지·역추세 제외)',EXIST[:4]),('5쌍 (에너지 제외)',EXIST[:4]+EXIST[5:])]:
        L=sum([pair_legs(p) for p in ps],[]); x=pd.concat(L); r=port(L); sh,mdd=pstat(r)
        print(f"  {name}: 거래당 {x.mean()*100:+.2f}% ({len(x)}) · Sharpe {sh:.2f} · MDD {mdd:.0f}% | 기간별 Sharpe "+' / '.join(f"{pstat(r[a:b])[0]:.2f}" for a,b in PER)+f" | 최근12개월 Sharpe {pstat(r['2025-11-04':])[0]:.2f}")
    print('\n## 1-5) 같은 날 동시 신호 (쌍 수 기준) — 매수 종목 수 = 쌍 × 2')
    D=pd.DataFrame({p[1]:pd.Series(1,index=pair_legs(p)[0].index) for p in EXIST}).fillna(0)
    cnt=D[[p[1] for p in EXIST[:5]]].sum(axis=1); cnt=cnt[cnt>0]
    print('  급락 5쌍 신호일 '+str(len(cnt))+'일: '+' · '.join(f"{k}쌍 {v}일" for k,v in cnt.value_counts().sort_index().items()))
    L5={p[1]:pd.concat(pair_legs(p)).groupby(level=0).mean() for p in EXIST[:5]}
    dd=pd.DataFrame(L5).mean(axis=1)
    for k in sorted(cnt.unique()):
        g=dd[cnt[cnt==k].index]; print(f"   {int(k)}쌍 동시: 그날 평균 {g.mean()*100:+.2f}% · 승률 {(g>0).mean()*100:.0f}% ({len(g)}일)")
    print('  역추세(QQQ ≥ +2%)와 급락 쌍이 같은 날: '+str(int(((D.QQQ>0)&(D[[p[1] for p in EXIST[:5]]].sum(axis=1)>0)).sum()))+'일')

# ───────────────────────── 2부. 신규 후보 ─────────────────────────
# 섹터별 미국 신호 후보 × 국내 종목 후보. 방향 down = 미국 하락 ≤ 기준 → 국내 매수(기존 A와 같은 되돌림 가설)
# ^VIX는 up(급등 ≥ 기준) → 국내 매수(공포 급등 = 미국 급락과 같은 가설), 역추세(up → 인버스)는 지수만
CAND={
 '은행':(['XLF','KBE','KRE','JPM'],['091170','105560','055550','086790','024110']),
 '증권':(['GS','MS','SCHW','IAI'],['102970','006800','039490']),
 '보험':(['XLF'],['140700','032830','000810']),
 '방산':(['ITA','XAR','LMT','NOC','RTX'],['012450','064350','079550','047810']),
 '자동차':(['GM','F','TM','TSLA','XLY'],['091180','005380','000270','012330']),
 '인터넷·SW':(['META','GOOGL','IGV','XLC','QQQ'],['035420','035720','157490','266360']),
 '반도체장비':(['AMAT','LRCX','KLAC','ASML'],['042700','403870','058470','039030','240810','036930']),
 '반도체(기타 미국)':(['TSM','AMD','AVGO','SMH','MU','NVDA'],['091230','139260','091160','000660','005930']),
 '철강·소재':(['SLX','NUE','XLB','XME'],['117680','005490','010130']),
 '건설':(['XHB','ITB'],['117700','000720']),
 '중국소비':(['KWEB','FXI'],['228790','090430','051900']),
 '조선·기계':(['XLI'],['010140','009540','042660','329180']),
 '통신':(['XLC'],['098560','017670','030200']),
 '코스닥 바이오':(['XBI','IBB'],['261070','028300','196170']),
 '지수(추가 신호)':(['EWY','IWM','DIA','EEM','QQQ'],['069500','229200']),
}
DN=[-0.01,-0.015,-0.02,-0.025,-0.03,-0.04,-0.05]
VIXUP=[0.10,0.15,0.20,0.25,0.30]
def legstats(x,base):
    tr=x[TRAIN[0]:TRAIN[1]]; te=x[TEST[0]:TEST[1]]
    s=dict(n=len(x),avg=x.mean()*100,base=base*100,t=tstat(x),
           n_tr=len(tr),avg_tr=tr.mean()*100 if len(tr) else np.nan,t_tr=tstat(tr),
           a1=x['2014':'2019'].mean()*100,n1=len(x['2014':'2019']),a2=x['2020':'2021'].mean()*100,n2=len(x['2020':'2021']),
           n_te=len(te),avg_te=te.mean()*100 if len(te) else np.nan,t_te=tstat(te),win_te=(te>0).mean()*100 if len(te) else np.nan)
    return s
def scan():
    rows=[]
    for sec,(tks,codes) in CAND.items():
        for tk in tks:
            for c in codes:
                for th in DN:
                    x,b=leg(tk,th,c); rows.append(dict(sec=sec,tk=tk,code=c,th=th,**legstats(x,b)))
    for c in ['069500','229200','091160','000660','005930']:
        for th in VIXUP:
            x,b=leg('^VIX',th,c); rows.append(dict(sec='VIX 급등',tk='^VIX',code=c,th=th,**legstats(x,b)))
    for tk in ['SPY','DIA','IWM','EWY']:      # 역추세 추가 후보 (인버스 2종, +0.5% 익절)
        for th in [0.01,0.015,0.02]:
            for c in ['114800','251340']:
                x,b=leg(tk,th,c,'tp'); rows.append(dict(sec='역추세(추가)',tk=tk,code=c,th=th,**legstats(x,b)))
    return pd.DataFrame(rows)
# 학습 구간 통과 조건(미리 정함): 건수 ≥ 20, t ≥ 2.0, 2014-19·2020-21 모두 플러스, 아무 날보다 높음
def passed(R): return R[(R.n_tr>=20)&(R.t_tr>=2.0)&(R.a1>0)&(R.a2>0)&(R.avg_tr>R.base)]
if __name__=='__main__':
    R=scan(); P=passed(R)
    print(f'\n# 2부. 신규 후보 — 종목 단위 {len(R)}개 조합 (학습 {TRAIN[0]}~{TRAIN[1]} / 검증 {TEST[0]}~{END})')
    print(f'  학습 조건 통과 {len(P)}개 → 검증 플러스 {int((P.avg_te>0).sum())}개 ({(P.avg_te>0).mean()*100:.0f}%), 검증 거래당 평균 {P.avg_te.mean():+.2f}%')
    F=R.drop(P.index); F=F[F.n_te>=5]
    print(f'  학습 미통과 {len(F)}개 → 검증 플러스 {(F.avg_te>0).mean()*100:.0f}%, 검증 거래당 평균 {F.avg_te.mean():+.2f}%')
    print('\n## 2-1) 섹터별 학습 통과 조합 (학습 t 순, 섹터당 상위 6)')
    for sec in R.sec.unique():
        g=P[P.sec==sec].sort_values('t_tr',ascending=False).head(6)
        if not len(g): print(f'  [{sec}] 통과 없음'); continue
        print(f'  [{sec}]')
        for _,r in g.iterrows():
            print(f"    {r.tk} {'≥ +' if r.th>0 else '≤ '}{r.th*100:g}% → {nm(r.code)}: 학습 {r.avg_tr:+.2f}% ({r.n_tr}, t {r.t_tr:.1f}; 14-19 {r.a1:+.2f}, 20-21 {r.a2:+.2f}) | 검증 {r.avg_te:+.2f}% ({r.n_te}, t {r.t_te:.1f}, 승률 {r.win_te:.0f}%) | 아무 날 {r.base:+.2f}")
    R.to_csv('data/new_pairs_scan.csv',index=False)

# 2-2) 쌍 구성: 섹터마다 학습 통과 조합 중 (미국 티커, 기준)별 학습 t 합이 가장 큰 것 → 그 기준에서 학습 t 상위 국내 2종목
def build_pairs(R,P):
    out=[]
    for sec in P.sec.unique():
        g=P[P.sec==sec]
        key=g.groupby(['tk','th']).apply(lambda q:q.sort_values('t_tr',ascending=False).head(2).t_tr.sum()*(min(len(q),2)/2)).sort_values(ascending=False)
        tk,th=key.index[0]; codes=g[(g.tk==tk)&(g.th==th)].sort_values('t_tr',ascending=False).code.head(2).tolist()
        out.append((sec,tk,th,codes,'tp' if sec.startswith('역추세') else 'oo'))
    return out
def overlap(p):
    mine=set(pair_legs(p)[0].index); ex=set().union(*[set(pair_legs(q)[0].index) for q in EXIST[:5]])
    return len(mine&ex)/max(len(mine),1)
if __name__=='__main__':
    B=build_pairs(R,P)
    L6=sum([pair_legs(q) for q in EXIST],[]); r6=port(L6); sh6,mdd6=pstat(r6)
    print(f'\n## 2-2) 섹터별 대표 쌍 (학습으로 구성) — 검증 구간 성과 · 기존 급락 5쌍과 같은 날 비율 · 6쌍에 더했을 때 Sharpe (기존 {sh6:.2f}, MDD {mdd6:.0f}%)')
    rows=[]
    for p in B:
        L=pair_legs(p); x=pd.concat(L).sort_index(); te=x[TEST[0]:]; tr=x[:TRAIN[1]]
        r=port(L6+L); sh,mdd=pstat(r); rte=port(L)[TEST[0]:]
        rows.append((p,tstat(tr),te.mean()*100,len(te),tstat(te),overlap(p),sh,mdd,pstat(rte)[0]))
    rows.sort(key=lambda z:-z[1])
    for p,ttr,ate,nte,tte,ov,sh,mdd,shte in rows:
        print(f"  [{p[0]}] {p[1]} {'≥ +' if p[2]>0 else '≤ '}{p[2]*100:g}% → {'·'.join(nm(c) for c in p[3])}: 학습 t {ttr:.1f} | 검증 {ate:+.2f}% ({nte}, t {tte:.1f}, Sharpe {shte:.2f}) | 같은 날 {ov*100:.0f}% | 7쌍 Sharpe {sh:.2f} · MDD {mdd:.0f}%")
        print('      '+pair_line(p))

# 2-3) 최종 후보 — 앱 미반영(사용자 결정) (2-2에서 검증 t ≥ 2 이고 7쌍 Sharpe를 올린 쌍) — 구성 비교·기존 신호와 겹치지 않는 날·민감도·8쌍 합산
FINAL=[('반도체(NVDA)','NVDA',-0.03),('공포지수','^VIX',0.15)]
COMPS={'NVDA':[['091230','091160'],['091160','000660'],['091230','000660'],['091160','042700']],
       '^VIX':[['000660','091160'],['000660','229200'],['091160','229200'],['000660','069500']]}
SENS={'NVDA':[-0.025,-0.03,-0.035,-0.04],'^VIX':[0.10,0.125,0.15,0.175,0.20,0.25]}
def ex_days(): return set().union(*[set(pair_legs(q)[0].index) for q in EXIST[:5]])
if __name__=='__main__':
    print('\n## 2-3) 최종 후보 상세')
    exd=ex_days()
    for sec,tk,th in FINAL:
        print(f'\n[{sec}] {tk} {"≥ +" if th>0 else "≤ "}{th*100:g}%')
        for codes in COMPS[tk]:
            p=(sec,tk,th,codes,'oo'); L=pair_legs(p); x=pd.concat(L).sort_index()
            new=x[~x.index.isin(exd)]; old=x[x.index.isin(exd)]
            sh7,mdd7=pstat(port(L6+L)); te=x[TEST[0]:]
            print(f"  → {'·'.join(nm(c) for c in codes)}: 거래당 {x.mean()*100:+.2f}% ({len(x)}, t {tstat(x):.1f}) · 검증 {te.mean()*100:+.2f}% (t {tstat(te):.1f})"
                  f" | 기존 쌍과 겹치는 날 {old.mean()*100:+.2f}% ({len(old)}) · 안 겹치는 날 {new.mean()*100:+.2f}% ({len(new)}, t {tstat(new):.1f}) | 7쌍 Sharpe {sh7:.2f} MDD {mdd7:.0f}%")
        codes=COMPS[tk][0]
        print('   기준 민감도: '+' | '.join(f"{t*100:+g}%: {pd.concat(pair_legs((sec,tk,t,codes,'oo'))).mean()*100:+.2f} ({len(pd.concat(pair_legs((sec,tk,t,codes,'oo'))))}, t {tstat(pd.concat(pair_legs((sec,tk,t,codes,'oo')))):.1f})" for t in SENS[tk]))
        oc=pd.concat(pair_legs((sec,tk,th,codes,'oc'))).sort_index(); print(f'   당일 종가 매도면: {oc.mean()*100:+.2f}% · 2023~ {oc["2023":].mean()*100:+.2f}%')

# 2-4) 8쌍 합산 (기존 6 + 최종 2) — 기간별 Sharpe, 같은 날 최대 매수 종목 수
NEW=[('반도체(NVDA)','NVDA',-0.03,['091230','091160'],'oo'),('공포지수','^VIX',0.15,['000660','091160'],'oo')]
if __name__=='__main__':
    print('\n## 2-4) 합산 비교 (자금 1/N, 신호 없는 날 현금)')
    for name,ps in [('기존 6쌍',EXIST),('6쌍 + NVDA',EXIST+NEW[:1]),('6쌍 + VIX',EXIST+NEW[1:]),('8쌍 (6 + NVDA + VIX)',EXIST+NEW),('7쌍 (에너지 빼고 + NVDA + VIX)',EXIST[:4]+EXIST[5:]+NEW)]:
        L=sum([pair_legs(p) for p in ps],[]); x=pd.concat(L).sort_index(); r=port(L); sh,mdd=pstat(r)
        legs=pd.concat([pd.Series(1,index=s.index) for s in L]).groupby(level=0).sum()
        yrs=(pd.Timestamp(END)-pd.Timestamp('2014-08-12')).days/365.25
        print(f"  {name}: 연 {len(x)/yrs:.0f}건 · 거래당 {x.mean()*100:+.2f}% · 승률 {(x>0).mean()*100:.0f}% · Sharpe {sh:.2f} · MDD {mdd:.0f}% | 기간별 Sharpe "+' / '.join(f"{pstat(r[a:b])[0]:.2f}" for a,b in PER)
              +f" | 최근12개월 Sharpe {pstat(r['2025-11-04':])[0]:.2f} | 하루 최대 {int(legs.max())}종목 · 4종목 이상 {int((legs>=4).sum())}일")
    print('\n## 2-5) 최근 신호 (2026-08~): 날짜 · 미국 등락 · 종목별 순수익')
    for p in NEW:
        for c in p[3]:
            f=fr(c,p[1]); m=(f.sig<=p[2]) if p[2]<0 else (f.sig>=p[2]); g=f[m]['2026-08':]
            print(f"  {p[1]} → {nm(c)}: "+(' · '.join(f"{d:%m-%d} {s*100:+.1f}% → {r*100:+.2f}%" for d,s,r in zip(g.index,g.sig,g.oo_net)) or '없음'))
