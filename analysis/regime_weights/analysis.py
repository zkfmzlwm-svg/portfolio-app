from sig import *
from scipy import stats
# ---- assets (KRW, total-return approx) ----
ks = yahoo('%5EKS11'); kr_tr = ks.pct_change() + 0.018/12          # KOSPI + ~1.8%/yr dividend
gc = yahoo('GC%3DF').resample('M').last().ffill(); gl = yahoo('GLD')
gold_r = pd.concat([gc.pct_change()[:'2004-12'], gl.pct_change()['2005-01':]])
fxr = fx.pct_change()
def krw(s): r = s.pct_change(); return (1 + r) * (1 + fxr) - 1
R = pd.DataFrame({'kr': kr_tr, 'us': krw(yahoo('SPY')), 'bonds': krw(yahoo('IEF')),
                  'gold': (1 + gold_r) * (1 + fxr) - 1, 'crypto': krw(yahoo('BTC-USD'))})
R = R['2002-09':'2026-09']
# ---- regime: retail YoY + ISM prices (PPI 3m% proxy before 2021, real ISM after) ----
ppi = monthly(fred('PPIACO')); m3 = (ppi / ppi.shift(3) - 1) * 100
s_ism = pd.concat([sig_series(m3)[:'2020-12'], sig_series(ism_s)['2021-01':]])
s_ism = s_ism[~s_ism.index.duplicated()]
reg = overall(sig_series(retail_yoy), s_ism).dropna()
reg_ext = pd.concat([reg, sig_series(m3)['2026-01':].pipe(lambda s: overall(sig_series(retail_yoy), s)).dropna()]) # after DBnomics ends use PPI
reg_ext = reg_ext[~reg_ext.index.duplicated()]
LAG = 2   # data month t -> known by end of t+1 -> applied to returns in t+2
regime = reg_ext.copy(); regime.index = regime.index + LAG
R = R.join(regime.rename('reg'), how='left').dropna(subset=['reg'])
ASSETS = ['kr', 'us', 'bonds', 'gold', 'crypto']
