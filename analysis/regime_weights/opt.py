from analysis import *
from scipy.optimize import minimize
from scipy import stats
A = ASSETS
LB = np.array([.05, .05, .05, .05, .02]); UB = np.array([.40, .40, .40, .35, .15])
def erc(cov):
    n = len(cov); f = lambda w: ((w * (cov @ w) / (w @ cov @ w) - 1 / n) ** 2).sum()
    r = minimize(f, np.ones(n) / n, bounds=list(zip(LB, UB)), constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}])
    return r.x
def mv(mu, cov, lam):
    f = lambda w: -(w @ mu - lam / 2 * w @ cov @ w)
    r = minimize(f, np.ones(len(mu)) / len(mu), bounds=list(zip(LB, UB)), constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}])
    return r.x
def estimate(Rw, K=60, lam=None):
    """Regime weights: shrunk regime means (n/(n+K) toward overall), shrunk cov; anchored on ERC."""
    X = Rw[A]; cov_all = X.cov().values * 12; mu_all = X.mean().values * 12
    w_erc = erc(cov_all)
    # implied returns (reverse optimisation) so neutral MV == ERC baseline
    if lam is None: lam = 3.0
    pi = lam * cov_all @ w_erc
    out = {}
    for g in ['bull', 'neutral', 'bear']:
        d = Rw[Rw.reg == g][A]; n = d.count().values
        mu_g = d.mean().values * 12
        tilt = (mu_g - mu_all) * n / (n + K)            # shrink regime deviation
        cov_g = 0.5 * d.cov().values * 12 + 0.5 * cov_all
        out[g] = mv(pi + tilt, cov_g, lam)
    return w_erc, out, lam
if __name__ == '__main__':
    w_erc, W, lam = estimate(R)
    print('ERC', dict(zip(A, (w_erc*100).round(1))))
    for g, w in W.items(): print(g, dict(zip(A, (w*100).round(1))))
