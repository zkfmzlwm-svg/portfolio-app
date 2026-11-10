"""5) 정기(반기) → 수시(한 자산군이라도 |현재 − 목표| 7%p 이상) 전환 점검 — 기본 비중 20/35/5/25/15 (v6.9)
   비교: 반기(6·12, v6.5~v6.8) vs 수시 ±5·±7·±10%p vs 반기+±7%p
   A. 과거 백테스트(월말 점검, 비용 0.3%, 적립 없음/월 적립)  B. 몬테카를로(../goal_sim 경로·가정) — 10억 확률·하방·경로별 MDD·연 횟수
   timing.py의 simc·row·mc를 그대로 씀(비중만 바꿈)."""
from timing import *                                    # simc, row, mc, G, X, np, pd

W0 = np.array([20, 35, 5, 25, 15]) / 100
RULES7 = {'반기(6·12) v6.5~6.8': dict(months=(6, 12)), '수시 ±5%p': dict(band=.05), '수시 ±7%p (v6.9)': dict(band=.07),
          '수시 ±10%p': dict(band=.10), '반기+수시 ±7%p': dict(months=(6, 12), band=.07)}

if __name__ == '__main__':
    pd.set_option('display.width', 220)
    for a, b in (('2003-01', '2026-09'), ('2014-10', '2026-09')):
        Rx = X[a:b]; rfs = Rx['rf'].values
        for cf, lab in ((0, '적립 없음'), (250 / 4200, '월 적립 250만원/초기 4,200만원')):
            print(f'\n[A. {a}~{b} · {lab} · 비용 0.3% · 20/35/5/25/15]')
            print(pd.DataFrame({k: row(*(lambda s: (s[0], rfs, s[1:]))(simc(Rx, contrib=cf, W=W0, **p))) for k, p in RULES7.items()}).T.to_string())
    print('\n[A-2. 하위기간 Sharpe / MDD, 적립 없음]')
    per = {'2003-2009': ('2003-01', '2009-12'), '2010-2017': ('2010-01', '2017-12'), '2018-2026': ('2018-01', '2026-09'), '2021.11-2022.12 코인 겨울': ('2021-11', '2022-12')}
    print(pd.DataFrame({nm: {k: (lambda z: f"{row(z[0], X[s:e]['rf'].values, z[1:])['Sharpe']:.2f} / {row(z[0], X[s:e]['rf'].values, z[1:])['MDD']}")(simc(X[s:e], W=W0, **p))
                             for k, p in RULES7.items()} for nm, (s, e) in per.items()}).to_string())
    print('\n[B-0. 블록 길이 민감도 — P(≥10억) %, 시작 1억]')
    print(pd.DataFrame({f'{L}개월 블록': {k: (mc(p, G.paths(4000, 120, seed=3, blk=L), G.MU['base'], 1e8, W=W0)[0] >= G.GOAL).mean() * 100
                         for k, p in RULES7.items()} for L in (1, 6, 12, 24)}).round(1).to_string())
    idx = G.paths(4000, 120, seed=2)
    for v0 in (0.0275e8, 1e8):
        out = {}
        for k, p in RULES7.items():
            F, D, n = mc(p, idx, G.MU['base'], v0, W=W0); F0, _, _ = mc(p, idx, G.MU['coin0'], v0, W=W0)
            out[k] = {'P10억': (F >= G.GOAL).mean() * 100, 'P10억(코인0%)': (F0 >= G.GOAL).mean() * 100, '하위10': np.percentile(F, 10) / 1e8,
                      '중앙': np.median(F) / 1e8, 'MDD중앙': np.median(D), 'MDD하위10': np.percentile(D, 10), '연횟수': n.mean()}
        print(f'\n[B. 몬테카를로 4,000경로 · 10년 · 월 250만 · 시작 {v0/1e8:.2f}억 · 20/35/5/25/15]')
        print(pd.DataFrame(out).T.round(2).to_string())
