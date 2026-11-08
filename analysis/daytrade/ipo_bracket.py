# 신규상장 '지정가 매수 + 익절 +x% · 손절 −y% 동시 주문(OCO)' 검증 (python3 ipo_bracket.py) — 원자료: ipo_fetch.py (--intraday 포함)
#   진입은 ipo_tp.py와 같음(공모가 × N 지정가, 시초가 체결, 상한가 시작은 미체결)
#   익절: 고가 ≥ 목표가 + 1호가(목표가 = 상한가면 고가 ≥ 상한가) → 목표가 체결
#   손절: 저가 ≤ 손절가(시초가 × (1 − y%) 호가 내림) → 손절가 − 1호가 체결(시장가 매도 미끄러짐). 봉 시가가 이미 손절가 아래면 그 시가 − 1호가
#   같은 봉에서 둘 다 닿으면 순서를 모름 → 비관(손절 먼저) / 낙관(익절 먼저) 두 값을 함께 본다
#   봉 해상도: 일봉(252건) · 60분봉(91건, 2024-11~) · 1~2분봉(최근, 네이버 1분봉 우선 → 야후 2분봉)
#   둘 다 안 닿으면: 일봉 = 당일 종가, 분봉 = 10:00 직전 가격(시간 손절)
import numpy as np, pandas as pd, os, warnings
from ipo_tp import X, up, dn, tick, net
warnings.filterwarnings('ignore')
def bars_of(r,kind):
    if kind=='1d': return [(r.o,r.h,r.l,r.c)]
    for k in (['1m','2m'] if kind=='fine' else [kind]):
        f=f'data/ipo/{r.code}_{k}.csv'
        if not os.path.exists(f): continue
        b=pd.read_csv(f,parse_dates=['t']).sort_values('t'); b=b[(b.t.dt.strftime('%Y-%m-%d')==r.date)&(b.t.dt.hour>=9)]
        if not len(b): continue
        s=r.o/b.o.iloc[0]
        if abs(s-1)>0.005 and k!='60m': continue          # 분봉 시가가 일봉 시가와 다르면 버림(수정주가는 ipo_tp에서 이미 맞춤)
        b=b[b.t.dt.hour*100+b.t.dt.minute<1000] if k!='60m' else b.head(1)
        return [(o*s,h*s,l*s,c*s) for o,h,l,c in zip(b.o,b.h,b.l,b.c)]
    return None
def one(r,N,x,y,kind,order):
    F,P,cap=r.offer,r.o,r.cap
    if P>dn(np.array(F*N)) or P>=cap*0.999: return None
    T=min(float(up(np.array(P*(1+x)))),cap); need=T if T>=cap else T+float(tick(np.array(T)))
    S=float(dn(np.array(P*(1-y)))) if y else -1
    B=bars_of(r,kind)
    if B is None: return None
    for i,(o,h,l,c) in enumerate(B):
        th=h>=need; sh=l<=S
        sfill=(min(S,o) if i>0 else S)-float(tick(np.array(S))) if y else None
        if th and sh: return ('sl',sfill,1) if order=='pess' else ('tp',T,1)
        if th: return ('tp',T,0)
        if sh: return ('sl',sfill,0)
    return ('end',B[-1][3],0)
def run(N,x,y,kind,order='pess'):
    out=[]
    for r in X.itertuples():
        z=one(r,N,x,y,kind,order)
        if z: out.append(dict(date=r.date,name=r.name,how=z[0],amb=z[2],ret=float(net(z[1]/r.o-1))))
    return pd.DataFrame(out)
def st(R):
    if not len(R): return '0건'
    x=R.ret; return (f"{len(x)}건 · 익절 {(R.how=='tp').mean()*100:.0f}% · 손절 {(R.how=='sl').mean()*100:.0f}% · 시간/종가 {(R.how=='end').mean()*100:.0f}% · 같은 봉 동시 {R.amb.mean()*100:.0f}%"
            f" · 거래당 {x.mean()*100:+.2f}% · 승률 {(x>0).mean()*100:.0f}% · 최악 {x.min()*100:+.1f}%")
if __name__=='__main__':
    print('# 익절 +x% · 손절 −y% 동시 주문 (보수 체결: 익절 +1호가, 손절 −1호가)')
    for kind,lab in [('1d','일봉 252건 (둘 다 안 닿으면 종가)'),('60m','60분봉 91건 (첫 1시간, 안 닿으면 10:00)'),('fine','1·2분봉 (최근, 09:00~09:59, 안 닿으면 10:00)')]:
        print(f'\n## {lab}')
        for N in [1.5,4.0]:
            for x,y in [(0.03,0.03),(0.02,0.02),(0.05,0.05),(0.03,0.05),(0.03,None)]:
                p=run(N,x,y,kind,'pess'); o=run(N,x,y,kind,'opt')
                print(f"  N ≤{N:.1f} · +{x*100:g}% / {'−'+format(y*100,'g')+'%' if y else '손절 없음'}: 비관 {st(p)}")
                if y: print(f"  {'':22}낙관 거래당 {o.ret.mean()*100:+.2f}% · 승률 {(o.ret>0).mean()*100:.0f}%")
    print('\n## 1·2분봉 종목별 (+3% / −3%, N 4 = 모두 체결 기준)')
    for r in X.itertuples():
        B=bars_of(r,'fine')
        if B is None: continue
        z=one(r,4.0,0.03,0.03,'fine','pess')
        if not z: print(f"  {r.date} {r.name}: 미체결(시초 {r.ratio:.2f}배)"); continue
        P=r.o; T=float(up(np.array(P*1.03))); S=float(dn(np.array(P*0.97)))
        first_tp=next((i for i,b in enumerate(B) if b[1]>=T+float(tick(np.array(T)))),None); first_sl=next((i for i,b in enumerate(B) if b[2]<=S),None)
        print(f"  {r.date} {r.name} 시초 {r.ratio:.2f}배: {z[0]}{' (같은 봉)' if z[2] else ''} {net(z[1]/P-1)*100:+.2f}% · 익절가 첫 도달 {first_tp}번째 봉 · 손절가 첫 도달 {first_sl}번째 봉 · 첫 봉 고가 {B[0][1]/P*100-100:+.1f}% 저가 {B[0][2]/P*100-100:+.1f}%")
