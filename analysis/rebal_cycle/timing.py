"""4) 리밸런싱 실행 시점 — 10억 목표형 30/20/5/25/20 기준 4안 비교
   ① 반기 1회(6·12월)  ② 분기 1회(3·6·9·12월)  ③ 수시: 한 자산군이라도 목표 비중 ±5%p 초과  ④ 수시: 목표 금액 대비 ±5% 초과
   (참고) 현행 v5.4 반기+목표 금액 ±25% 수시, 반기+±5%p 수시
   A. 과거 백테스트(월말 점검, 비용 0.3%, 적립 없음/월 적립)  B. 몬테카를로(../goal_sim 경로·가정) — 10억 확률·하방·경로별 MDD"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'goal_sim'))
from cycle import *                                     # sim(), X, A
import sim as G                                        # goal_sim: L0, paths, MU, GOAL

W5 = np.array([30, 20, 5, 25, 20]) / 100
RULES = {'① 반기(6·12)': dict(months=(6, 12)), '② 분기(3·6·9·12)': dict(months=(3, 6, 9, 12)),
         '③ 수시 ±5%p': dict(band=.05), '④ 수시 목표 금액 ±5%': dict(rel=.05),
         '(현행) 반기+±25% 수시': dict(months=(6, 12), rel=.25), '(참고) 반기+±5%p 수시': dict(months=(6, 12), band=.05)}

def simc(Rx, months=(), band=None, rel=None, cost=.003, contrib=0.0, W=W5):
    """cycle.sim과 같은 규칙이지만 매매비용을 그달 수익률에 반영(cycle.sim은 비용 차감 후 값을 다음 달 기준으로 써서 비용이 수익률에 안 잡힘)"""
    r = Rx[A].values; per = Rx.index; m0 = ~np.isnan(r[0]); h = np.where(m0, W, 0) / W[m0].sum(); out = []; traded = 0; n = 0; dev = 0
    for t in range(len(r)):
        rt = np.nan_to_num(r[t]); live = ~np.isnan(r[t]); w = np.where(live, W, 0); w = w / w.sum()
        before = h.sum(); h = h * (1 + rt); post = h.sum()
        cur = h / h.sum(); dev = max(dev, np.abs(cur - w).max())
        hit = per[t].month in months or (band is not None and np.abs(cur - w).max() > band) or \
              (rel is not None and (np.abs(cur[w > 0] / w[w > 0] - 1) > rel).any())
        if hit:
            tv = np.abs(cur - w).sum() / 2 * h.sum(); traded += tv / h.sum(); n += 1; h = w * (h.sum() - tv * cost)
        out.append(h.sum() / before - 1)                # 비용 차감 후 수익률
        if contrib:
            tot = h.sum() + contrib; need = np.maximum(w * tot - h, 0); c = contrib
            add = need / need.sum() * min(c, need.sum()) if need.sum() > 0 else 0; h = h + add; c -= np.sum(add)
            if c > 1e-12: h = h + w * c
    return pd.Series(out, index=per), traded / (len(r) / 12) * 2, n, dev * 100

def row(s, rfs, extra):
    c = (1 + s).cumprod(); ex = s - rfs; r12 = c.pct_change(12).dropna()
    return dict(CAGR=round((c.iloc[-1] ** (12 / len(s)) - 1) * 100, 2), Sharpe=round(ex.mean() / s.std() * np.sqrt(12), 3),
                MDD=round((c / c.cummax() - 1).min() * 100, 1), 최악12개월=round(r12.min() * 100, 1),
                회전율=round(extra[0] * 100), 횟수=extra[1], 연횟수=round(extra[1] / (len(s) / 12), 1), 최대이탈=round(extra[2], 1))

def mc(rule, idx, mu, v0, monthly=250e4, cost=.003, W=W5):
    """goal_sim.run과 같은 적립 규칙 + 리밸런싱 규칙만 바꿈 → (최종자산, 경로별 MDD, 연평균 횟수)"""
    n, M = idx.shape; g = np.log1p(np.array(mu) / 100) / 12; r = np.expm1(G.L0[idx] + g)
    h = W * v0 * np.ones((n, 5)); m0 = 10; months = rule.get('months', ()); band = rule.get('band'); rel = rule.get('rel')
    peak = np.full(n, 0.0); mdd = np.zeros(n); idxv = np.ones(n); cnt = np.zeros(n)   # 시간가중 지수로 MDD
    for t in range(M):
        before = h.sum(1); h = h * (1 + r[:, t, :]); idxv *= h.sum(1) / before
        peak = np.maximum(peak, idxv); mdd = np.minimum(mdd, idxv / peak - 1)
        c = monthly; tot = h.sum(1, keepdims=True) + c
        need = np.maximum(W * tot - h, 0); ns = need.sum(1, keepdims=True)
        add = np.where(ns > 0, need / np.maximum(ns, 1e-9) * np.minimum(c, ns), 0); h = h + add
        h = h + W * np.maximum(c - add.sum(1, keepdims=True), 0)
        S = h.sum(1, keepdims=True); cur = h / S; mon = (m0 + t) % 12 + 1
        hit = np.zeros(n, bool)
        if mon in months: hit[:] = True
        if band is not None: hit |= np.abs(cur - W).max(1) > band
        if rel is not None: hit |= (np.abs(cur[:, W > 0] / W[W > 0] - 1) > rel).any(1)
        tv = np.abs(cur - W).sum(1, keepdims=True) / 2 * S
        h = np.where(hit[:, None], W * (S - tv * cost), h); cnt += hit
    return h.sum(1), mdd * 100, cnt / (M / 12)

if __name__ == '__main__':
    pd.set_option('display.width', 220)
    for a, b in (('2003-01', '2026-09'), ('2014-10', '2026-09')):
        Rx = X[a:b]; rfs = Rx['rf'].values
        for cf, lab in ((0, '적립 없음'), (250 / 4200, '월 적립 250만원/초기 4,200만원')):
            print(f'\n[A. {a}~{b} · {lab} · 비용 0.3% · 30/20/5/25/20]')
            print(pd.DataFrame({k: row(*(lambda s: (s[0], rfs, s[1:]))(simc(Rx, contrib=cf, **p))) for k, p in RULES.items()}).T.to_string())
    # 하위기간 Sharpe
    print('\n[A-2. 하위기간 Sharpe / MDD, 적립 없음]')
    per = {'2003-2009': ('2003-01', '2009-12'), '2010-2017': ('2010-01', '2017-12'), '2018-2026': ('2018-01', '2026-09'), '2021.11-2022.12 코인 겨울': ('2021-11', '2022-12')}
    print(pd.DataFrame({nm: {k: (lambda z: f"{row(z[0], X[s:e]['rf'].values, z[1:])['Sharpe']:.2f} / {row(z[0], X[s:e]['rf'].values, z[1:])['MDD']}")(simc(X[s:e], **p))
                             for k, p in RULES.items()} for nm, (s, e) in per.items()}).to_string())
    # 비용 민감도
    print('\n[A-3. 비용 민감도 2014-10~ Sharpe (비용 0.1 / 0.3 / 0.6 / 1.0%)]')
    Rx = X['2014-10':'2026-09']; rfs = Rx['rf'].values
    print(pd.DataFrame({k: {f'{c*100:.1f}%': row(*(lambda s: (s[0], rfs, s[1:]))(simc(Rx, cost=c, **p)))['Sharpe'] for c in (.001, .003, .006, .01)} for k, p in RULES.items()}).T.to_string())
    # B. 몬테카를로
    print('\n[B-0. 블록 길이 민감도 — P(≥10억) %, 시작 0.03억 (블록이 길수록 추세·평균회귀가 과거처럼 유지됨)]')
    print(pd.DataFrame({f'{L}개월 블록': {k: (mc(p, G.paths(4000, 120, seed=3, blk=L), G.MU['base'], 0.0275e8)[0] >= G.GOAL).mean() * 100
                         for k, p in RULES.items()} for L in (1, 6, 12, 24)}).round(1).to_string())
    idx = G.paths(4000, 120, seed=2)
    for v0 in (0.0275e8, 1e8):
        out = {}
        for k, p in RULES.items():
            F, D, n = mc(p, idx, G.MU['base'], v0); F0, _, _ = mc(p, idx, G.MU['coin0'], v0)
            out[k] = {'P10억': (F >= G.GOAL).mean() * 100, 'P10억(코인0%)': (F0 >= G.GOAL).mean() * 100, '하위10': np.percentile(F, 10) / 1e8,
                      '중앙': np.median(F) / 1e8, 'MDD중앙': np.median(D), 'MDD하위10': np.percentile(D, 10), '연횟수': n.mean()}
        print(f'\n[B. 몬테카를로 4,000경로 · 10년 · 월 250만 · 시작 {v0/1e8:.2f}억 · 30/20/5/25/20]')
        print(pd.DataFrame(out).T.round(2).to_string())
