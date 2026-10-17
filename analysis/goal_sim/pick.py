"""2) 후보 비중 정밀 비교(4,000경로) + 하방·과거 MDD로 최종안 선택  3) 레버별 효과(월 적립·기간·절세·스위칭)
   python3 pick.py   (sim.py 그리드 결과 상위권 + 대조군)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rebal_cycle'))
from sim import *
from cycle import sim as bt                                # 과거 경로 백테스트(반기+±25%) — MDD 확인용

C = {'기준 20/30/10/25/15': BASE, '공격형 20/40/10/15/15': [20, 40, 10, 15, 15], '초공격 20/40/5/15/20': [20, 40, 5, 15, 20],
     '35/20/0/25/20': [35, 20, 0, 25, 20], '30/25/0/25/20': [30, 25, 0, 25, 20], '30/30/0/20/20': [30, 30, 0, 20, 20],
     '35/25/0/20/20': [35, 25, 0, 20, 20], '25/30/5/20/20': [25, 30, 5, 20, 20], '25/35/0/20/20': [25, 35, 0, 20, 20],
     '25/30/0/25/20': [25, 30, 0, 25, 20], '20/35/5/20/20': [20, 35, 5, 20, 20],
     '코인25 25/30/0/20/25': [25, 30, 0, 20, 25], '코인30 25/25/0/20/30': [25, 25, 0, 20, 30]}
def hist(w):
    Rx = X['2014-10':'2026-09']; s = bt(Rx, months=(6, 12), rel=.25, W=np.array(w) / 100)[0]; c = (1 + s).cumprod()
    return (c / c.cummax() - 1).min() * 100, (c.iloc[-1] ** (12 / len(s)) - 1) * 100

if __name__ == '__main__':
    pd.set_option('display.width', 220)
    M = 120; idx = paths(4000, M, seed=2); W = np.array(list(C.values()))
    V = float(os.environ.get('V0', 0))
    if not V:                                              # 시작 자산 보정: 기준안 중앙값이 이전 답변(6.22억)과 같아지는 V0
        lo, hi = 0.0, 2e8
        for _ in range(14):
            mid = (lo + hi) / 2; F = run(np.array([BASE]), idx[:1500], MU['base'], v0=mid)[0]
            lo, hi = (mid, hi) if np.median(F) < 6.22e8 else (lo, mid)
        V = (lo + hi) / 2
    print(f'시작 자산 V0 = {V/1e8:.2f}억 (기준안 중앙 6.22억 보정) · 10년 · 월 250만')
    out = {}
    for s, mu in MU.items():
        F = run(W, idx, mu, v0=V)
        for k, f in zip(C, F): out.setdefault(k, {})[s] = (f >= GOAL).mean() * 100
        if s == 'base': base = {k: summ(f) for k, f in zip(C, F)}
    D = pd.DataFrame(out).T; D['평균P'] = D.mean(axis=1)
    for k in C: D.loc[k, '하위10(억)'] = base[k]['하위10']; D.loc[k, '중앙(억)'] = base[k]['중앙']; D.loc[k, '상위10(억)'] = base[k]['상위10']
    for k, w in C.items(): D.loc[k, '과거MDD'], D.loc[k, '과거CAGR'] = hist(w)
    print('\n[2] P(≥10억)% — 코인 기하수익 15(base)/0/8/30% 가정, 분위수는 base'); print(D.round(1).to_string())
    # 3) 레버 — 최종안 기준
    best = [30, 25, 0, 25, 20]                          # 최상위권(35/20·35/25·30/30)과 오차 내 동률, 과거 MDD 최소
    def one(w, **kw):
        F = run(np.array([w]), idx, MU['base'], v0=V, **kw)[0]; F0 = run(np.array([w]), idx, MU['coin0'], v0=V, **kw)[0]
        d = summ(F); d['P10억(코인0%)'] = (F0 >= GOAL).mean() * 100; return d
    L = {'기준안·월250': (BASE, {}), '최종안·월250': (best, {}), '최종안·월300': (best, dict(monthly=300e4)),
         '최종안·월400': (best, dict(monthly=400e4)), '최종안·12년': (best, dict(months=None)),
         '최종안·절세 재투자(연 118.8만)': (best, dict(tax=118.8e4)), '최종안·절세(연 148.5만)': (best, dict(tax=148.5e4)),
         '최종안·스위칭 성공(국내 +3%p 가정)': (best, dict(krx=.03)),
         '최종안·월300+절세118.8+스위칭': (best, dict(monthly=300e4, tax=118.8e4, krx=.03))}
    rows = {}
    for k, (w, kw) in L.items():
        if kw.get('months', 1) is None:
            i12 = paths(4000, 144, seed=2); F = run(np.array([w]), i12, MU['base'], v0=V)[0]; F0 = run(np.array([w]), i12, MU['coin0'], v0=V)[0]
            d = summ(F); d['P10억(코인0%)'] = (F0 >= GOAL).mean() * 100; rows[k] = d
        else: rows[k] = one(w, **kw)
    print('\n[3] 레버별 (억, %)'); print(pd.DataFrame(rows).T.round(2).to_string())
    # 50% 확률에 필요한 월 적립
    for w, nm in ((BASE, '기준안'), (best, '최종안')):
        lo, hi = 50e4, 1500e4
        for _ in range(12):
            mid = (lo + hi) / 2; F = run(np.array([w]), idx[:2000], MU['base'], v0=V, monthly=mid)[0]
            lo, hi = (mid, hi) if (F >= GOAL).mean() < .5 else (lo, mid)
        print(f'  {nm}: P(≥10억)=50%에 필요한 월 적립 ≈ {hi/1e4:.0f}만원')
