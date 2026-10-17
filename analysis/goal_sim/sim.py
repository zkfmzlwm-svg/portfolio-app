"""10억 목표 도달 확률 — 몬테카를로 (12개월 블록 부트스트랩)
   변동성·상관·꼬리는 2014-10~2026-09 원화 월수익률(../regime_weights)에서, 평균은 아래 기대수익 가정으로 재중심화.
   앱 운영 규칙 그대로: 매월 적립금은 부족 자산군에만(부족액 비례), 6·12월 정기 + 목표 금액 ±25% 수시 리밸런싱, 비용 0.3%."""
import os, sys, itertools
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'regime_weights'))
from static import X, A                                   # A = kr, us, bonds, gold, crypto

GOAL = 10e8
V0 = float(os.environ.get('V0', 1.0e8))                    # 시작 자산(원) — 앱은 실제 총자산으로 계산
# 연 기하 기대수익(원화, %). 과거(2014-10~) 11/15/3/13/65%를 그대로 쓰면 낙관적이라 낮춘 값
MU = {'base': [7, 8, 3.5, 5, 15], 'coin0': [7, 8, 3.5, 5, 0], 'coin8': [7, 8, 3.5, 5, 8], 'coin30': [7, 8, 3.5, 5, 30]}
R = X['2014-10':'2026-09'][A]
L0 = np.log1p(R.values); L0 = L0 - L0.mean(0)              # 평균 제거한 월 로그수익률 (T,5)
T = len(L0)

def paths(n, months, seed=7, blk=12):
    rng = np.random.default_rng(seed); idx = np.empty((n, months), int)
    for i in range(n):
        s = []
        while len(s) < months: a = rng.integers(0, T - blk + 1); s.extend(range(a, a + blk))
        idx[i] = s[:months]
    return idx

def run(W, idx, mu, monthly=250e4, v0=V0, tax=0.0, krx=0.0, months0=10, cost=.003, rel=.25):
    """W: (k,5) 목표비중, idx: (n,M) 부트스트랩 인덱스 → 최종자산 (k,n)
       tax: 연 세액공제 환급액(원) — 매년 12월 적립에 더함, krx: 국내주식 연 초과수익(스위칭 성공 가정, 소수)"""
    W = np.asarray(W, float); W = W / W.sum(1, keepdims=True); k = len(W); n, M = idx.shape
    g = np.log1p(np.array(mu) / 100) / 12; g[0] += np.log1p(krx) / 12
    r = np.expm1(L0[idx] + g)                               # (n,M,5)
    h = W[:, None, :] * v0 * np.ones((k, n, 5))
    m0 = 10                                                 # 시작 월 = 10월 → 12월부터 정기
    for t in range(M):
        h = h * (1 + r[None, :, t, :])
        c = monthly + (tax if (m0 + t) % 12 == 11 else 0)   # 12월 적립에 환급분 재투자 (앱과 동일)
        tot = h.sum(2, keepdims=True) + c
        need = np.maximum(W[:, None, :] * tot - h, 0); ns = need.sum(2, keepdims=True)
        add = np.where(ns > 0, need / np.maximum(ns, 1e-9) * np.minimum(c, ns), 0); h = h + add
        left = c - add.sum(2, keepdims=True); h = h + W[:, None, :] * np.maximum(left, 0)
        mon = (m0 + t) % 12 + 1
        S = h.sum(2, keepdims=True); cur = h / S
        hit = (np.abs(cur / np.maximum(W[:, None, :], 1e-9) - 1) * (W[:, None, :] > 0) > rel).any(2, keepdims=True)
        if mon in (6, 12): hit[:] = True
        tv = np.abs(cur - W[:, None, :]).sum(2, keepdims=True) / 2 * S
        h = np.where(hit, W[:, None, :] * (S - tv * cost), h)
    return h.sum(2)

def summ(F):
    return dict(하위10=np.percentile(F, 10) / 1e8, 중앙=np.median(F) / 1e8, 상위10=np.percentile(F, 90) / 1e8,
                P10억=(F >= GOAL).mean() * 100)

BASE = [20, 30, 10, 25, 15]
if __name__ == '__main__':
    pd.set_option('display.width', 220)
    M = 120
    # 1) 비중 그리드: 국내 0~40, 해외 20~60, 채권 0~20, 금 0~35, 코인 0~20 (코인 상한 20%는 regime_weights 그리드와 동일)
    G = np.array([w for w in itertools.product(range(0, 41, 5), range(20, 61, 5), range(0, 21, 5), range(0, 36, 5))
                  for c in [100 - sum(w)] if 0 <= c <= 20 for w in [w + (c,)]])
    idx = paths(1500, M, seed=1)
    res = {s: (run(G, idx, mu) >= GOAL).mean(1) * 100 for s, mu in MU.items()}
    D = pd.DataFrame(res); D.index = ['/'.join(map(str, w)) for w in G]
    D['평균'] = D[list(MU)].mean(1); D['최소'] = D[list(MU)].min(1)
    print(f'[1] 비중 {len(G)}조합 · 10년 · 월 250만 · 시작 {V0/1e8:.1f}억 · P(≥10억)% (1,500경로)')
    print('  기대수익 가정(국내/해외/채권/금/코인, 연%):', MU)
    print('\n  평균 기준 상위 12'); print(D.sort_values('평균', ascending=False).head(12).round(1).to_string())
    print('\n  코인 0% 가정(최악)에서도 기준안보다 나은 조합 중 평균 상위 8')
    b0 = D.loc['/'.join(map(str, BASE))]
    print('  기준', '/'.join(map(str, BASE)), b0.round(1).to_dict())
    print(D[D.coin0 >= b0.coin0].sort_values('평균', ascending=False).head(8).round(1).to_string())
