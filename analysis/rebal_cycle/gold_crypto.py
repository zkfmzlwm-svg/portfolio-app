"""3) 금·광물 : 코인 비중 — 30:10(현행) vs 25:15 vs 20:20
   앱 운영 규칙과 같게 반기(6·12월) + 목표 금액 ±25% 수시 리밸런싱, 비용 0.3%, 원화 무위험 차감 Sharpe.
   코인(BTC)의 과거 수익률은 앞으로 반복되기 어려우므로 연 수익률을 낮춘 민감도와 블록 부트스트랩을 함께 본다."""
from cycle import *
MIX = {'금30:코인10 (현행)': [20, 30, 10, 30, 10], '금25:코인15': [20, 30, 10, 25, 15], '금20:코인20': [20, 30, 10, 20, 20]}
RULE = dict(months=(6, 12), rel=.25)
rng = np.random.default_rng(11)

def run(Rx, w, **kw):
    s, to, n, dev = sim(Rx, W=np.array(w) / 100, **dict(RULE, **kw)); return s, to, n
def stats_(s, rfs):
    c = (1 + s).cumprod(); ex = s - rfs; r12 = c.pct_change(12).dropna()
    return dict(CAGR=(c.iloc[-1] ** (12 / len(s)) - 1) * 100, 변동성=s.std() * np.sqrt(12) * 100,
                Sharpe=ex.mean() / s.std() * np.sqrt(12), MDD=(c / c.cummax() - 1).min() * 100,
                최악12개월=r12.min() * 100 if len(r12) else np.nan)
def haircut(Rx, cut):
    """코인 월 로그수익률 평균을 연 cut(소수)만큼 낮춤 — 변동성·상관은 그대로"""
    R = Rx.copy(); lr = np.log1p(R['crypto']); R['crypto'] = np.expm1(lr - np.log1p(cut) / 12); return R
def risk_share(Rx, w):
    """포트폴리오 분산 중 코인 기여 비중(%) — 목표비중 기준"""
    C = Rx[A].dropna().cov().values; w = np.array(w) / 100; m = C @ w; return w[-1] * m[-1] / (w @ m) * 100
def boot(Rx, n=2000, L=12):
    """12개월 블록 부트스트랩: 현행 대비 Sharpe·MDD 차 분포"""
    T = len(Rx); out = {k: [] for k in MIX}; rfs = Rx['rf'].values
    for _ in range(n):
        idx = []
        while len(idx) < T: s0 = rng.integers(0, T - L + 1); idx.extend(range(s0, s0 + L))
        B = Rx.iloc[idx[:T]].copy(); B.index = Rx.index
        for k, w in MIX.items(): out[k].append(stats_(run(B, w)[0], rfs))
    return {k: pd.DataFrame(v) for k, v in out.items()}

if __name__ == '__main__':
    pd.set_option('display.width', 200)
    for a, b, lab in (('2014-10', '2026-09', '코인 편입 이후 전체'), ('2003-01', '2026-09', '전체(2014-09 이전은 코인 없이 재정규화)')):
        Rx = X[a:b]; rfs = Rx['rf'].values
        t = pd.DataFrame({k: dict(stats_(*(lambda z: (z[0], rfs))(run(Rx, w))), 횟수=run(Rx, w)[2], 코인위험기여=risk_share(Rx['2014-10':], w))
                          for k, w in MIX.items()}).T
        print(f'\n[{a}~{b} {lab}] 반기+±25% 수시, 비용 0.3%'); print(t.round(2).to_string())
    print('\n[구간별 누적수익률 / MDD (%)]')
    per = {'2014.10-2017.12 코인 1차 상승': ('2014-10', '2017-12'), '2018 코인 겨울(−73%)': ('2018-01', '2018-12'),
           '2019-2021 코인 2차 상승': ('2019-01', '2021-10'), '2021.11-2022.12 코인 겨울(−65%)': ('2021-11', '2022-12'),
           '2023-2026.09': ('2023-01', '2026-09'), '2011.9-2015.12 금 약세(코인 일부)': ('2011-09', '2015-12'),
           '2020.2-3 코로나 급락': ('2020-02', '2020-03')}
    rows = {}
    for nm, (a, b) in per.items():
        Rx = X[a:b]; rfs = Rx['rf'].values
        rows[nm] = {k: (lambda z: f'{((1 + z).prod() - 1) * 100:+.1f} / {stats_(z, rfs)["MDD"]:.1f}')(run(Rx, w)[0]) for k, w in MIX.items()}
    print(pd.DataFrame(rows).T.to_string())
    Rx = X['2014-10':'2026-09']; rfs = Rx['rf'].values
    bt = (1 + Rx['crypto']).prod() ** (12 / len(Rx)) - 1
    print(f'\n[코인 기대수익 민감도, 2014-10~] 실제 BTC 원화 CAGR {bt*100:.0f}%/년 → 연 수익률을 낮춰 재계산 (Sharpe / CAGR / MDD)')
    rows = {}
    for cut in (0, .2, .4, .6, .7):
        H = haircut(Rx, cut); c_ = ((1 + H['crypto']).prod() ** (12 / len(H)) - 1) * 100
        rows[f'코인 CAGR {c_:.0f}%'] = {k: '{Sharpe:.2f} / {CAGR:.1f} / {MDD:.1f}'.format(**stats_(run(H, w)[0], rfs)) for k, w in MIX.items()}
    print(pd.DataFrame(rows).T.to_string())
    print('\n[12개월 블록 부트스트랩 2,000회, 2014-10~ 표본] 중앙값 (5~95분위)')
    B = boot(Rx); base = B['금30:코인10 (현행)']
    for k, d in B.items():
        msg = ' · '.join(f"{m} {d[m].median():.2f} ({d[m].quantile(.05):.2f}~{d[m].quantile(.95):.2f})" for m in ('Sharpe', 'MDD', '최악12개월'))
        if k != '금30:코인10 (현행)':
            msg += f" | 현행보다 Sharpe 높음 {(d.Sharpe > base.Sharpe).mean()*100:.0f}% · MDD 나쁨 {(d.MDD < base.MDD).mean()*100:.0f}% · MDD −25% 초과 {(d.MDD < -25).mean()*100:.0f}%"
        print(f'  {k:14s} {msg}')
