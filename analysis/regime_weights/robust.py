"""고정 비중의 강건성: 위험기반 방식 워크포워드 + 하위기간 maximin 그리드"""
from static import *
from opt import erc
def st(s, rfs):
    c = (1 + s).cumprod(); return dict(CAGR=round((c.iloc[-1] ** (12 / len(s)) - 1) * 100, 1), Vol=round(s.std() * np.sqrt(12) * 100, 1),
        Sharpe=round((s - rfs).mean() / s.std() * np.sqrt(12), 2), MDD=round((c / c.cummax() - 1).min() * 100, 1))
def port(Rx, w):
    r = Rx[A].values; m = np.isnan(r); W = np.where(m, 0, w); W = W / W.sum(1, keepdims=True)
    return pd.Series((np.nan_to_num(r) * W).sum(1), index=Rx.index)
def minvar(cov):
    from scipy.optimize import minimize
    n = len(cov); b = [(0, .5)] * 4 + [(0, .15)]
    return minimize(lambda w: w @ cov @ w, np.ones(n) / n, bounds=b, constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}]).x
def wf_risk(fn):
    out = []
    for y in range(2010, 2027):
        H = X[X.index < pd.Period(f'{y}-01', 'M')]; C = H[A].cov().values * 12
        w = fn(C); Y = X.loc[str(y)]; out.append(port(Y, w))
    return pd.concat(out)
if __name__ == '__main__':
    O = X['2010-01':]; rfs = O['rf'].values
    print('OOS 2010-01~2026-09 (위험기반 방식은 매년 과거 공분산만으로 산정)')
    rows = {'ERC 리스크패리티': wf_risk(erc), '최소분산': wf_risk(minvar),
            '역변동성': wf_risk(lambda C: (lambda v: np.minimum(v / v.sum(), [1, 1, 1, 1, .15]) / np.minimum(v / v.sum(), [1, 1, 1, 1, .15]).sum())(1 / np.sqrt(np.diag(C))))}
    for nm, w in [('현행 25/25/20/20/10', [25, 25, 20, 20, 10]), ('균등 20x5', [20] * 5), ('주식60 채권금30 코인10', [30, 30, 15, 15, 10])]:
        rows[nm] = port(O, np.array(w) / 100)
    print(pd.DataFrame({k: st(v, rfs) for k, v in rows.items()}).T.to_string())

    # maximin: 3개 하위기간 모두에서의 최저 Sharpe를 최대화 (코인 없는 기간은 나머지로 재정규화)
    periods = [('2003-01', '2009-12'), ('2010-01', '2017-12'), ('2018-01', '2026-09')]
    SH = []
    for a, b in periods:
        Px = X[a:b]; r = Px[A].values; rf_ = Px['rf'].values
        Ws = np.repeat(GRID[None], len(r), 0); Ws = np.where(np.isnan(r)[:, None, :], 0, Ws); Ws = Ws / Ws.sum(2, keepdims=True)
        P = (np.nan_to_num(r)[:, None, :] * Ws).sum(2)
        SH.append((P - rf_[:, None]).mean(0) / P.std(0) * np.sqrt(12))
    SH = np.array(SH); mn = SH.min(0)
    order = np.argsort(-mn)
    print('\nmaximin 상위 10 (하위기간 최저 Sharpe 기준)  [국내/해외/채권/금/코인]  P1 P2 P3')
    for i in order[:10]: print(' ', fmt(GRID[i]), f'min {mn[i]:.2f} |', ' '.join(f'{s:.2f}' for s in SH[:, i]))
    top = GRID[order[:int(len(GRID) * .02)]]
    print('상위 2% 평균:', fmt(top.mean(0)), '| 범위', ' '.join(f'{a}:{top[:,j].min()*100:.0f}-{top[:,j].max()*100:.0f}' for j, a in enumerate(A)))
    cur = np.where((GRID == np.array([.25, .25, .2, .2, .1])).all(1))[0][0]
    print('현행 25/25/20/20/10 순위', int(np.where(order == cur)[0][0]) + 1, '/', len(GRID), '| Sharpe', ' '.join(f'{s:.2f}' for s in SH[:, cur]))
