# 홍춘욱 듀얼 스위칭 원 전략 방향(강세: 수출·가치·대형 ↑ / 약세: 내수·성장·소형 ↑)을 시장 앵커 ±15%p로 구현한 값 vs v7.1 데이터 검증값
from robust import *
HONG = {'kr.size': (0.90, 0.80, 0.65), 'kr.export': (0.75, 0.65, 0.50), 'kr.value': (0.65, 0.50, 0.35),
        'us.value': (0.65, 0.50, 0.35), 'us.size': (0.95, 0.90, 0.75)}
DATA = {'kr.size': (0.80, 0.80, 0.75), 'kr.export': (0.65, 0.65, 0.65), 'kr.value': (0.50, 0.50, 0.50),
        'us.value': (0.50, 0.50, 0.40), 'us.size': (0.90, 0.90, 0.95)}
ax = {k: (a, b, nm) for k, nm, a, b, anc, why in AXES}
def ev(W, dd):
    w = dd.reg.map(dict(zip(('bull', 'neutral', 'bear'), W))); r = w * dd.a + (1 - w) * dd.b; return perf(r)
if __name__ == '__main__':
    print('CAGR % / Sharpe — 홍춘욱(기본) vs 데이터 검증(v7.1)   ※ kr.value는 고배당:KODEX200(가치:시장) 대용, 2012~')
    for k in HONG:
        a, b, nm = ax[k]; d = frame(a, b); n = len(d)
        for lab, dd in (('전체', d), ('전반', d.iloc[:n // 2]), ('후반', d.iloc[n // 2:]), ('2010~', d[d.index >= pd.Period('2010-01', 'M')])):
            h, x = ev(HONG[k], dd), ev(DATA[k], dd)
            print(f'{nm:40s} {lab:5s} 홍춘욱 {h[0]:6.2f}/{h[1]:.3f}  데이터 {x[0]:6.2f}/{x[1]:.3f}  차이 {h[0]-x[0]:+.2f}%p')
