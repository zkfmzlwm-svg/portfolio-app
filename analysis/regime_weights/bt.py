from opt import *
import opt
OLD = {'bull': [27,30,12,13,18], 'neutral': [25,25,20,20,10], 'bear': [18,17,30,27,8]}
OLD = {k: np.array(v) / 100 for k, v in OLD.items()}
def run(Rx, wfun):
    out = []
    for t, row in Rx.iterrows():
        w = wfun(t, row.reg).copy(); r = row[A].values.astype(float)
        m = np.isnan(r)
        if m.any(): w[m] = 0; w = w / w.sum(); r = np.nan_to_num(r)
        out.append(w @ r)
    return pd.Series(out, index=Rx.index)
def stats_(s):
    c = (1 + s).cumprod(); yrs = len(s) / 12
    return dict(CAGR=round((c.iloc[-1] ** (1 / yrs) - 1) * 100, 2), Vol=round(s.std() * np.sqrt(12) * 100, 2),
                Sharpe=round(s.mean() / s.std() * np.sqrt(12), 3), MDD=round((c / c.cummax() - 1).min() * 100, 1))
def walk_forward(K, dev, start='2010-01'):
    cache = {}
    def wf(t, reg):
        y = t.year
        if y not in cache:
            hist = R[R.index < pd.Period(f'{y}-01', 'M')]
            cache[y] = wf_estimate(hist, K, dev)
        base, W = cache[y]
        return W[reg] if reg in W else base
    return wf, cache
def wf_estimate(hist, K, dev):
    X = hist[A]; cov_all = X.cov().values * 12; mu_all = X.mean().values * 12
    base = erc(cov_all); lam = 3.0; pi = lam * cov_all @ base
    W = {}
    for g in ['bull', 'neutral', 'bear']:
        d = hist[hist.reg == g][A]; n = d.count().values
        tilt = np.nan_to_num((d.mean().values * 12 - mu_all) * n / (n + K))
        cov_g = 0.5 * np.nan_to_num(d.cov().values * 12) + 0.5 * cov_all
        lb = np.maximum(opt.LB, base - dev); ub = np.minimum(opt.UB, base + dev)
        f = lambda w: -(w @ (pi + tilt) - lam / 2 * w @ cov_g @ w)
        W[g] = minimize(f, base, bounds=list(zip(lb, ub)), constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}]).x
    return base, W
if __name__ == '__main__':
    S = '2010-01'; Rt = R[S:]
    res = {}
    res['OLD static 25/25/20/20/10'] = run(Rt, lambda t, g: OLD['neutral'])
    res['OLD dynamic presets'] = run(Rt, lambda t, g: OLD[g])
    erc_cache = {}
    def erc_wf(t, g):
        if t.year not in erc_cache: erc_cache[t.year] = erc(R[R.index < pd.Period(f'{t.year}-01','M')][A].cov().values*12)
        return erc_cache[t.year]
    res['ERC static (walk-fwd)'] = run(Rt, erc_wf)
    for K in [30, 60, 120]:
        for dev in [.05, .10, .15]:
            f, _ = walk_forward(K, dev); res[f'NEW dyn K={K} dev={int(dev*100)}'] = run(Rt, f)
    tab = pd.DataFrame({k: stats_(v) for k, v in res.items()}).T
    print(f'Out-of-sample walk-forward {Rt.index[0]}~{Rt.index[-1]} ({len(Rt)}m), KRW, monthly rebal, no costs')
    print(tab.to_string())
