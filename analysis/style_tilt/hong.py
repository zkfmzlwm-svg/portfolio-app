# 홍춘욱 듀얼 스위칭 원 전략 방향(강세: 수출·가치·대형 ↑ / 약세: 내수·성장·소형 ↑)을 시장 앵커 ±15%p로 구현한 값 vs v7.1 데이터 검증값
from robust import *
HONG = {'kr.size': (0.80, 0.80, 0.80),  # v7.3: 국내 대형:소형 80 고정
        'kr.export': (0.75, 0.65, 0.50), 'kr.value': (0.65, 0.50, 0.35),
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

# ---- v7.3 홍춘욱 2단계: 상승 신호 / 하락·중립 ----
#  국내 경기민감 : 방어·성장 = 70:30 / 35:65, 해외(대형) 가치 : 성장 = 60:40 / 35:65 — 50:50 고정과 비교
def two_stage():
    def st(r):
        r = r.dropna(); c = (1 + r).prod() ** (12 / len(r)) - 1; v = r.std() * np.sqrt(12); return f'{c*100:5.2f}%/{c/v:.2f}'
    kq = y('%5EKQ11') + 0.006 / 12
    rows = [('국내 경기민감(수출섹터) : 내수섹터', kr_exp, kr_dom, .70, .35),
            ('국내 경기민감(수출섹터) : 코스닥', kr_exp, kq, .70, .35),
            ('국내 경기민감(수출섹터) : 내수·코스닥 반반', kr_exp, ew(kr_dom, kq), .70, .35),
            ('해외 가치 : 성장 (IWD : IWF)', y('IWD'), y('IWF'), .60, .35),
            ('[검증] FF 대형 가치 : 성장', p6['BIG HiBM'], p6['BIG LoBM'], .60, .35)]
    for nm, a, b, wb, wo in rows:
        d = frame(a, b); w = d.reg.map({'bull': wb, 'neutral': wo, 'bear': wo})
        r = w * d.a + (1 - w) * d.b; s = 0.5 * d.a + 0.5 * d.b; ex = r - s
        print(f'{nm:36s} {d.index[0]}~ 2단계 {st(r)} | 50:50 고정 {st(s)} | 차이 {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) | 평균 A {w.mean()*100:.0f}%')
if __name__ == '__main__':
    print('\n[v7.3 2단계] CAGR / Sharpe')
    two_stage()
