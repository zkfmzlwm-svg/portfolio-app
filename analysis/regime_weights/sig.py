from load import *
def sig_series(x):
    x = x.dropna(); ma = x.rolling(3).mean(); up = ma.diff() > 0
    out = pd.Series('bear', index=x.index)
    out[up] = 'forming'; out[up & up.shift(1, fill_value=False)] = 'bull'
    out[ma.isna() | ma.shift(2).isna()] = None
    return out
def overall(a, b):
    idx = a.index.intersection(b.index); a, b = a[idx], b[idx]
    o = pd.Series('neutral', index=idx)
    o[(a == 'bull') & (b == 'bull')] = 'bull'; o[(a == 'bear') & (b == 'bear')] = 'bear'
    o[a.isna() | b.isna()] = None
    return o
if __name__ == '__main__':
    print(px.apply(lambda c: c.first_valid_index()))
    # proxy validation vs real ISM prices 2021-2025
    j = pd.concat([ism_s, philly], axis=1, keys=['ism', 'philly']).dropna()
    print('level corr', j.corr().iloc[0, 1].round(3), 'n', len(j))
    print('MA3 direction agreement', ((j.ism.rolling(3).mean().diff() > 0) == (j.philly.rolling(3).mean().diff() > 0))[3:].mean().round(3))
    si, sp = sig_series(ism_s), sig_series(philly)
    k = si.dropna().index.intersection(sp.dropna().index)
    print('signal agreement', (si[k] == sp[k]).mean().round(3), len(k))
    r = sig_series(retail_yoy)
    ov_p = overall(r, sp); ov_i = overall(r, si)
    k = ov_i.dropna().index
    print('overall regime agreement (ism vs philly)', (ov_i[k] == ov_p[k]).mean().round(3))
    print(ov_p['2004':].value_counts())
    print(ov_p.tail(8))
