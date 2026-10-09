"""1) 자산군 5개 리밸런싱 주기 비교 — 반기(6·12월) 중심
   매매비용 0.3%(거래금액 기준), 원화 무위험 차감 Sharpe. 월 적립(부족 자산군 배분) 유무 모두 시험."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'regime_weights'))
from static import *                                   # X(월수익률+rf), A
W = np.array([20, 30, 10, 30, 10]) / 100               # 앱 고정 목표 20/30/10/30/10

def sim(Rx, months=(), band=None, cost=.003, contrib=0.0, v0=1.0):
    """months: 리밸런싱 실행 월(1~12) — 해당 월말에 목표비중으로 전량 재조정
       band: 월말 점검 시 |현재−목표| 최대값이 band(비중 %p 소수) 넘으면 수시 리밸런싱
       contrib: 월 적립액(초기자산 대비) — 앱처럼 목표 대비 부족액 비례로 부족 자산군에만 투입
       반환: 시간가중 월수익률, 연평균 회전율, 리밸런싱 횟수, 최대 이탈(%p)"""
    r = Rx[A].values; per = Rx.index; m0 = ~np.isnan(r[0]); h = np.where(m0, W, 0) / W[m0].sum() * v0; out = []; traded = 0; n = 0; dev = 0
    for t in range(len(r)):
        rt = np.nan_to_num(r[t]); live = ~np.isnan(r[t]); w = np.where(live, W, 0); w = w / w.sum()
        before = h.sum(); h = h * (1 + rt); out.append(h.sum() / before - 1)
        if contrib:                                     # 적립: 부족액 비례(부족 총액 초과분은 목표비중 비례)
            tot = h.sum() + contrib; need = np.maximum(w * tot - h, 0); c = contrib
            add = need / need.sum() * min(c, need.sum()) if need.sum() > 0 else 0; h = h + add; c -= np.sum(add)
            if c > 1e-12: h = h + w * c
        cur = h / h.sum(); dev = max(dev, np.abs(cur - w).max())
        if per[t].month in months or (band is not None and np.abs(cur - w).max() > band):
            tv = np.abs(cur - w).sum() / 2 * h.sum(); traded += tv / h.sum(); n += 1
            h = w * (h.sum() - tv * cost)
    yrs = len(r) / 12
    return pd.Series(out, index=per), traded / yrs * 2, n, dev * 100

def row(s, rfs, extra):
    c = (1 + s).cumprod(); ex = s - rfs
    return dict(CAGR=round((c.iloc[-1] ** (12 / len(s)) - 1) * 100, 2), Sharpe=round(ex.mean() / s.std() * np.sqrt(12), 3),
                MDD=round((c / c.cummax() - 1).min() * 100, 1), 회전율=round(extra[0] * 100), 횟수=extra[1], 최대이탈=round(extra[2], 1))

PLANS = {'월간': dict(months=range(1, 13)), '분기(3·6·9·12)': dict(months=(3, 6, 9, 12)),
         '반기(6·12)': dict(months=(6, 12)), '연간(12)': dict(months=(12,)),
         '반기(6·12)+수시±5%p': dict(months=(6, 12), band=.05), '반기(6·12)+수시±7.5%p': dict(months=(6, 12), band=.075),
         '밴드만 ±5%p': dict(band=.05), '밴드만 ±10%p': dict(band=.10)}

if __name__ == '__main__':
    pd.set_option('display.width', 200)
    for a, b in (('2003-01', '2026-09'), ('2014-10', '2026-09')):
        Rx = X[a:b]; rfs = Rx['rf'].values
        for cf, lab in ((0, '적립 없음'), (200 / 4200, '월 적립 200만원/초기 4,200만원')):
            print(f'\n[{a}~{b} · {lab} · 비용 0.3%]  회전율=연간 매매금액/자산(%)')
            print(pd.DataFrame({k: row(*(lambda s: (s[0], rfs, s[1:]))(sim(Rx, contrib=cf, **p))) for k, p in PLANS.items()}).T.to_string())
    # 타이밍 운: 같은 주기라도 실행 월에 따라 성과가 얼마나 달라지나
    Rx = X['2003-01':'2026-09']; rfs = Rx['rf'].values
    print('\n[타이밍 운 — 반기 실행 월 6가지 / 분기 3가지 / 연간 12가지, 2003-01~, 적립 없음]')
    for nm, sets in (('반기', [(m, m + 6) for m in range(1, 7)]), ('분기', [(m, m + 3, m + 6, m + 9) for m in range(1, 4)]),
                     ('연간', [(m,) for m in range(1, 13)])):
        res = {str(s): row(*(lambda z: (z[0], rfs, z[1:]))(sim(Rx, months=s))) for s in sets}
        sh = [v['Sharpe'] for v in res.values()]; md = [v['MDD'] for v in res.values()]
        print(f'  {nm}: Sharpe {min(sh):.3f}~{max(sh):.3f}  MDD {min(md)}~{max(md)}  ',
              ' '.join(f"{k}:{v['Sharpe']:.3f}" for k, v in res.items()))
    # 반기 사이 6개월 동안 자산군별 이탈 분포 (코인 변동성 확인)
    print('\n[반기 리밸런싱 직전 자산군별 비중 이탈(%p) 분포, 2014-10~]')
    Rx = X['2014-10':'2026-09']; r = Rx[A].values; h = W.copy(); D = []
    for t in range(len(r)):
        h = h * (1 + np.nan_to_num(r[t]))
        if Rx.index[t].month in (6, 12): D.append((h / h.sum() - W) * 100); h = W * h.sum()
    D = pd.DataFrame(D, columns=A); print(D.describe(percentiles=[.1, .5, .9]).round(1).loc[['mean', 'min', '10%', '50%', '90%', 'max']].to_string())
