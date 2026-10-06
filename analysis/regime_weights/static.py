"""고정 비중 최적화: 그리드 탐색 + 블록 부트스트랩(리샘플링 최적화) + 워크포워드 검증"""
import itertools, sys
from analysis import *
A = ASSETS

rf = monthly(fred('IR3TIB01KRM156N')) / 100 / 12          # 원화 무위험(한국 3개월 금리)
X = R[A].copy(); X['rf'] = rf.reindex(X.index).ffill()
STEP = 5
GRID = np.array([w for w in itertools.product(range(0, 51, STEP), repeat=4)
                 for c in [100 - sum(w)] if 0 <= c <= 20 for w in [w + (c,)]]) / 100

def metrics(W, Rm, rfm):
    """W: (k,5) weights, Rm: (T,5) monthly returns -> per-weight CAGR, vol, Sharpe(excess), MDD (월 리밸런싱)"""
    P = Rm @ W.T                                            # (T,k)
    ex = P - rfm[:, None]
    sharpe = ex.mean(0) / P.std(0) * np.sqrt(12)
    cum = np.cumprod(1 + P, axis=0)
    mdd = (cum / np.maximum.accumulate(cum, axis=0) - 1).min(0)
    cagr = cum[-1] ** (12 / len(P)) - 1
    return cagr, P.std(0) * np.sqrt(12), sharpe, mdd

def block_boot(T, L=12, rng=None):
    idx = []
    while len(idx) < T:
        s = rng.integers(0, T - L + 1); idx.extend(range(s, s + L))
    return np.array(idx[:T])

def best(W, Rm, rfm, obj='sharpe', mdd_cap=None):
    cagr, vol, sh, mdd = metrics(W, Rm, rfm)
    score = sh.copy()
    if mdd_cap is not None: score[mdd < mdd_cap] = -np.inf
    return W[np.argmax(score)]

def fmt(w): return '/'.join(f'{x*100:.0f}' for x in w)

if __name__ == '__main__':
    P5 = X['2014-10':]; Rm = P5[A].values; rfm = P5['rf'].values
    print(f'grid {len(GRID)} combos, sample {P5.index[0]}~{P5.index[-1]} ({len(P5)}m)  [국내/해외/채권/금/코인]')
    cagr, vol, sh, mdd = metrics(GRID, Rm, rfm)
    print('\n[1] in-sample max Sharpe (과최적화 참고용):', fmt(GRID[np.argmax(sh)]), f'Sharpe {sh.max():.2f}')

    # [2] 리샘플링 최적화: 12개월 블록 부트스트랩 1000회, 각 표본의 max-Sharpe 비중 평균
    rng = np.random.default_rng(0); picks = []
    haircut = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0     # 코인 기대수익 할인(연, 예: 0.4)
    Rh = Rm.copy(); Rh[:, 4] -= haircut / 12
    for _ in range(1000):
        i = block_boot(len(Rh), 12, rng); picks.append(best(GRID, Rh[i], rfm[i]))
    picks = np.array(picks)
    print(f'\n[2] 리샘플 최적 (코인 할인 {haircut*100:.0f}%/년): 평균', fmt(picks.mean(0)),
          '| 10~90% 구간', ' '.join(f'{a}:{np.percentile(picks[:,j],10)*100:.0f}-{np.percentile(picks[:,j],90)*100:.0f}' for j, a in enumerate(A)))

    # [3] 4자산 장기(2002~): 코인 0 고정 시 리샘플 최적
    P4 = X['2002-09':]; R4 = P4[A].fillna(0).values; rf4 = P4['rf'].values
    G4 = GRID[GRID[:, 4] == 0]; p4 = []
    for _ in range(1000):
        i = block_boot(len(R4), 12, rng); p4.append(best(G4, R4[i], rf4[i]))
    print('\n[3] 4자산 2002~ 리샘플 최적 (코인 제외):', fmt(np.array(p4).mean(0)))

    # [4] 워크포워드: 매년 과거 데이터(2004-12~)로 리샘플 최적 → 다음 1년 적용
    print('\n[4] 워크포워드 (매년 과거로 산정 → 다음 해 적용)')
    rets, hist_w = [], []
    for y in range(2010, 2027):
        H = X[X.index < pd.Period(f'{y}-01', 'M')]['2002-09':]; Hr = H[A].values.copy()
        has_c = ~np.isnan(Hr[:, 4]); G = GRID if has_c.sum() >= 36 else GRID[GRID[:, 4] == 0]
        if has_c.sum() >= 36: Hr, Hrf = Hr[has_c], H['rf'].values[has_c]
        else: Hr, Hrf = np.nan_to_num(Hr), H['rf'].values
        Hr[:, 4] -= haircut / 12
        rr = np.random.default_rng(y); pk = np.array([best(G, Hr[i], Hrf[i]) for i in (block_boot(len(Hr), 12, rr) for _ in range(300))])
        w = pk.mean(0); hist_w.append((y, w))
        Y = X.loc[str(y)]; rets.append(pd.Series(np.nan_to_num(Y[A].values) @ w, index=Y.index))
    wf = pd.concat(rets)
    for y, w in hist_w: print(' ', y, fmt(w))
    def st(s, rfs):
        c = (1 + s).cumprod(); return dict(CAGR=round((c.iloc[-1] ** (12 / len(s)) - 1) * 100, 1), Vol=round(s.std() * np.sqrt(12) * 100, 1),
                                           Sharpe=round((s - rfs).mean() / s.std() * np.sqrt(12), 2), MDD=round((c / c.cummax() - 1).min() * 100, 1))
    rfs = X['rf'].reindex(wf.index).values
    print('  OOS 워크포워드', st(wf, rfs))
    for nm, w in [('현행 25/25/20/20/10', [25, 25, 20, 20, 10]), ('리샘플 평균', picks.mean(0) * 100)]:
        s = pd.Series(np.nan_to_num(X.loc[wf.index, A].values) @ (np.array(w) / 100), index=wf.index); print(' ', nm, st(s, rfs))
