"""후보 고정비중 하위기간·스트레스 구간·리밸런싱 주기 비교"""
from robust import *
C = {'현행 25/25/20/20/10': [25, 25, 20, 20, 10], '후보A 25/25/5/35/10': [25, 25, 5, 35, 10],
     '후보B 25/25/10/30/10': [25, 25, 10, 30, 10], '후보C 20/30/10/30/10': [20, 30, 10, 30, 10],
     '리샘플 13/38/2/39/9': [13, 38, 2, 39, 9], 'maximin 36/11/3/33/16': [36, 11, 3, 33, 16]}
per = {'2003-2009(코인無)': ('2003-01', '2009-12'), '2010-2017': ('2010-01', '2017-12'), '2018-2026': ('2018-01', '2026-09'),
       '금 약세 2011.9-2015.12': ('2011-09', '2015-12'), '금융위기 2007.11-2009.2': ('2007-11', '2009-02'),
       '2022 긴축': ('2022-01', '2022-12'), '전체 2003-2026': ('2003-01', '2026-09')}
if __name__ == '__main__':
    for k in ['CAGR', 'Sharpe', 'MDD']:
        t = pd.DataFrame({nm: {p: st(port(X[a:b], np.array(w) / 100), X[a:b]['rf'].values)[k] for p, (a, b) in per.items()} for nm, w in C.items()})
        print(f'\n[{k}]'); print(t.to_string())
    # 리밸런싱 방식 (2014-10~, 5자산, 매매비용 0.3%)
    def sim(w, Rx, mode, cost=.003):
        w = np.array(w) / 100; h = w.copy(); v = 1; vals = []; r = Rx[A].values
        for t in range(len(r)):
            h = h * (1 + r[t]); tot = h.sum(); cur = h / tot
            m = (mode == 'M') or (mode == 'Q' and t % 3 == 2) or (mode == 'Y' and t % 12 == 11) or (isinstance(mode, float) and np.abs(cur - w).max() > mode)
            if m: tv = np.abs(cur - w).sum() / 2 * tot; tot -= tv * cost; h = w * tot
            vals.append(tot)
        s = pd.Series(vals, index=Rx.index).pct_change().fillna(vals[0] - 1); return s
    Rx = X['2014-10':]
    print('\n[리밸런싱 방식 비교, 2014-10~, 비용 0.3%]')
    for nm in ['현행 25/25/20/20/10', '후보A 25/25/5/35/10', '후보B 25/25/10/30/10', '후보C 20/30/10/30/10']:
        print(nm, {str(m): st(sim(C[nm], Rx, m), Rx['rf'].values) for m in ['M', 'Q', 'Y', .05, .10]})
