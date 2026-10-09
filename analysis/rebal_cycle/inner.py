"""2) 주식 버킷 내부 리밸런싱 — 반기(6·12월)에 종목·스타일까지 맞출 가치가 있나
   A. 개별 종목: 유니버스에서 무작위 N종목 포트폴리오 3,000개 → 6·12월 동일비중 복원 vs 방치(드리프트) vs 상한 트림
   B. 6·12월 시점 모멘텀: 직전 6개월 승자가 다음 6개월에도 이기나(=리밸런싱이 승자를 파는 비용)
   C. 생존편향 없는 보조검증: Ken French 49산업(1927~)
   D. 스타일 축(대형/소형·가치/성장): 반기 복원 vs 방치, 5년 롤링
   주식 버킷 자체 크기는 자산군 리밸런싱이 맞춘다고 보고, 버킷 내부 수익률만 비교(현지통화)."""
import os, sys, json, glob
import numpy as np, pandas as pd
np.seterr(all='ignore')                                # 상폐 주입 시 전 종목 소멸 표본은 NaN → 중앙값 계산에서 제외
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'data'); SD = os.path.join(HERE, '..', 'style_tilt', 'data')
rng = np.random.default_rng(7)

def y(path):
    j = json.load(open(path))['chart']['result'][0]; q = j['indicators']
    px = q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close']
    s = pd.Series(px, index=pd.to_datetime(j['timestamp'], unit='s')).dropna(); s.index = s.index.to_period('M')
    return s[~s.index.duplicated(keep='last')].pct_change(fill_method=None)
def universe(pattern, start, end='2026-09'):
    R = pd.DataFrame({os.path.basename(f)[2:-5]: y(f) for f in glob.glob(os.path.join(D, pattern))}).sort_index()
    R = R[(R.index >= pd.Period(start, 'M')) & (R.index <= pd.Period(end, 'M'))]
    R = R.loc[:, R.notna().all()]                       # 기간 내내 상장된 종목만
    return R.clip(-0.95, 3.0)                           # 액면분할 오류 등 극단치 방어

def with_delist(r, hazard):
    """생존편향 보정 민감도: 종목마다 연 hazard 확률로 '12개월 월 −15% 하락(−86%) 후 상장폐지(−100%)' 경로를 덮어씀"""
    r = r.copy(); T, N = r.shape; p = 1 - (1 - hazard) ** (1 / 12)
    for j in range(N):
        hit = np.nonzero(rng.random(T) < p)[0]
        if len(hit):
            s0 = hit[0]; e = min(T, s0 + 12); r[s0:e, j] = -0.15
            if e < T: r[e, j] = -1.0; r[e + 1:, j] = 0.0
    return r

def sim(r, idx, mode, cost=.003, cap=2.0):
    """r: (T,N) 월수익률. mode: 'drift' | 'semi'(6·12월 동일비중) | 'annual'(12월) | 'trim'(6·12월 2/N 초과분만 잘라 나머지에 현재비중 비례 배분)
       반환: 월수익률, 연 회전율, 종료 시 최대 종목 비중, 실현이익(연평균, 버킷 대비)"""
    T, N0 = r.shape; w0 = np.ones(N0) / N0; h = w0.copy(); basis = w0.copy(); out = np.empty(T); traded = 0; real = 0
    alive = np.ones(N0, bool)                           # 상장폐지(수익률 −100%) 종목은 이후 목표에서 제외
    for t in range(T):
        v0 = h.sum(); h = h * (1 + r[t]); out[t] = h.sum() / v0 - 1; m = idx[t].month; tot = h.sum(); cur = h / tot
        alive &= r[t] > -1; N = alive.sum()
        if mode == 'semi' and m in (6, 12) or mode == 'annual' and m == 12: tgt = alive / N
        elif mode == 'trim' and m in (6, 12) and cur.max() > cap / N:
            tgt = np.minimum(cur, cap / N); free = 1 - tgt.sum(); room = (cur < cap / N) & alive
            for _ in range(5):                          # 재배분으로 상한 넘으면 반복
                add = np.where(room, tgt, 0); tgt = tgt + free * add / add.sum(); over = tgt > cap / N
                free = (tgt[over] - cap / N).sum(); tgt[over] = cap / N; room = (tgt < cap / N - 1e-12) & alive
                if free < 1e-12: break
        else: continue
        new = tgt * tot; dlt = new - h; sell = np.maximum(-dlt, 0)
        real += np.sum(np.where(h > 0, sell / h * (h - basis), 0))              # 평균단가 기준 실현손익
        basis = np.where(h > 0, basis * (1 - sell / np.where(h > 0, h, 1)), 0) + np.maximum(dlt, 0)
        tv = sell.sum(); traded += tv / tot; h = new * (1 - tv / new.sum() * cost)
    yrs = T / 12
    return out, traded / yrs * 2, (h / h.sum()).max(), real / yrs / np.mean(np.cumprod(1 + out))

def stats_(s):
    c = np.cumprod(1 + s); cagr = c[-1] ** (12 / len(s)) - 1
    return cagr, s.mean() / s.std() * np.sqrt(12), (c / np.maximum.accumulate(c) - 1).min()

def random_test(name, R, n=6, draws=3000, hazard=0.0, brief=False):
    r_all = R.values; idx = R.index; res = []
    for _ in range(draws):
        pick = rng.choice(R.shape[1], n, replace=False); r = r_all[:, pick]; row = {}
        if hazard: r = with_delist(r, hazard)
        for mode in ('drift', 'semi', 'annual', 'trim'):
            s, to, mxw, rl = sim(r, idx, mode); cg, sh, md = stats_(s)
            row.update({f'{mode}_cagr': cg, f'{mode}_sh': sh, f'{mode}_mdd': md, f'{mode}_to': to, f'{mode}_mx': mxw, f'{mode}_real': rl})
        res.append(row)
    d = pd.DataFrame(res); out = {}
    for mode, lab in (('drift', '방치(드리프트)'), ('semi', '반기 동일비중'), ('annual', '연1회 동일비중'), ('trim', '반기 상한트림(2/N)')):
        out[lab] = {'CAGR 중앙': d[f'{mode}_cagr'].median() * 100, 'Sharpe 중앙': d[f'{mode}_sh'].median(),
                    'MDD 중앙': d[f'{mode}_mdd'].median() * 100, '종료 최대비중 중앙': d[f'{mode}_mx'].median() * 100,
                    '회전율%/년': d[f'{mode}_to'].median() * 100, '실현이익%/년': d[f'{mode}_real'].median() * 100}
        if mode != 'drift':
            out[lab]['CAGR 차 중앙(vs 방치)'] = (d[f'{mode}_cagr'] - d.drift_cagr).median() * 100
            out[lab]['CAGR 우위 비율'] = (d[f'{mode}_cagr'] > d.drift_cagr).mean() * 100
            out[lab]['Sharpe 우위 비율'] = (d[f'{mode}_sh'] > d.drift_sh).mean() * 100
            out[lab]['MDD 개선 비율'] = (d[f'{mode}_mdd'] > d.drift_mdd).mean() * 100
    if brief:
        print(f'  {name:26s} 상폐확률 연 {hazard:.0%}: ' + ' | '.join(f"{k} CAGR차 {v['CAGR 차 중앙(vs 방치)']:+.2f}%p·우위 {v['CAGR 우위 비율']:.0f}%·MDD개선 {v['MDD 개선 비율']:.0f}%"
                                                         for k, v in out.items() if k != '방치(드리프트)' and k != '연1회 동일비중')); return
    print(f'\n[{name}] {R.index[0]}~{R.index[-1]}, 유니버스 {R.shape[1]}종목, 무작위 {n}종목 × {draws}회, 비용 0.3%')
    print(pd.DataFrame(out).T.round(2).to_string())

def momentum_6m(name, R):
    """6·12월말 기준 직전 6개월 수익률 상위절반 − 하위절반의 다음 6개월 수익률 차 (%p)"""
    lr = np.log1p(R); s6 = lr.rolling(6).sum(); f6 = lr[::-1].rolling(6).sum()[::-1].shift(-1); out = []
    for p in R.index:
        if p.month not in (6, 12): continue
        a, b = s6.loc[p], f6.loc[p]
        if a.isna().any() or b.isna().any(): continue
        hi = a >= a.median(); out.append((np.expm1(b[hi]).mean() - np.expm1(b[~hi]).mean()) * 100)
    o = pd.Series(out); t = o.mean() / o.std() * np.sqrt(len(o))
    print(f'  {name:32s} 승자−패자 다음 6개월 {o.mean():+.2f}%p (t={t:.2f}, 승자 우위 {(o > 0).mean() * 100:.0f}%, n={len(o)})')

def ff_table(fname, after):
    lines = open(os.path.join(D, fname), encoding='latin-1').read().splitlines()
    k = next(i for i, l in enumerate(lines) if after in l)
    while not lines[k].startswith(','): k += 1
    hdr = [h.strip() for h in lines[k].split(',')][1:]; rows = []
    for l in lines[k + 1:]:
        p = [x.strip() for x in l.split(',')]
        if not (p[0].isdigit() and len(p[0]) == 6): break
        rows.append(p)
    df = pd.DataFrame([r[1:] for r in rows], columns=hdr, dtype=float,
                      index=pd.PeriodIndex([r[0][:4] + '-' + r[0][4:] for r in rows], freq='M'))
    return df.where(df > -99) / 100

def style_axis(name, a, b, w, start=None, horizon=60):
    """A:B = w:(1−w). 6·12월 시작점마다 5년 보유: 반기 복원 vs 방치. 연환산 차·Sharpe 차·5년 후 A비중"""
    d = pd.concat([a, b], axis=1, keys=['a', 'b']).dropna()
    if start: d = d[d.index >= pd.Period(start, 'M')]
    d = d[d.index <= pd.Period('2026-09', 'M')]; r = d.values; idx = d.index; res = []
    for i, p in enumerate(idx):
        if p.month not in (6, 12) or i + 1 + horizon > len(idx): continue
        rr = r[i + 1:i + 1 + horizon]; ii = idx[i + 1:i + 1 + horizon]; o = {}
        for mode in ('drift', 'semi'):
            h = np.array([w, 1 - w]); s = []
            for t in range(horizon):
                v0 = h.sum(); h = h * (1 + rr[t]); s.append(h.sum() / v0 - 1)
                if mode == 'semi' and ii[t].month in (6, 12): h = np.array([w, 1 - w]) * h.sum() * (1 - abs(h[0] / h.sum() - w) * .003)
            s = np.array(s); o[mode] = (stats_(s)[0], stats_(s)[1], h[0] / h.sum())
        res.append((o['semi'][0] - o['drift'][0], o['semi'][1] - o['drift'][1], o['drift'][2]))
    x = np.array(res)
    print(f'  {name:30s} 목표 {w:.0%}  반기복원−방치 CAGR {np.median(x[:, 0]) * 100:+.2f}%p (우위 {(x[:, 0] > 0).mean() * 100:.0f}%) · '
          f'Sharpe {np.median(x[:, 1]):+.3f} (우위 {(x[:, 1] > 0).mean() * 100:.0f}%) · 5년 방치 후 A비중 {np.percentile(x[:, 2], 10) * 100:.0f}~{np.percentile(x[:, 2], 90) * 100:.0f}% (10~90분위), n={len(x)}')

if __name__ == '__main__':
    pd.set_option('display.width', 220)
    KR = universe('y_*.K?.json', '2010-01'); KRL = universe('y_*.KS.json', '2010-01'); KQ = universe('y_*.KQ.json', '2010-01')
    US = universe('y_[A-Z]*.json', '2000-01'); US10 = universe('y_[A-Z]*.json', '2010-01')
    print('# A. 개별 종목 — 반기 동일비중 복원 vs 방치')
    random_test('국내 전체(KOSPI 대형+코스닥)', KR); random_test('국내 KOSPI 대형', KRL); random_test('국내 코스닥 중소형', KQ, n=5)
    random_test('미국 대형 2000~', US); random_test('미국 대형 2010~', US10)
    print('\n# A2. 생존편향 민감도 — 연 1~3% 상장폐지 경로 주입 (2024·2025 코스닥 상폐 결정 20·38사 ≈ 상장사의 1~2%)')
    for nm, R, n in (('국내 전체', KR, 6), ('국내 코스닥 중소형', KQ, 5)):
        for hz in (.01, .02, .03): random_test(nm, R, n=n, draws=1500, hazard=hz, brief=True)
    print('\n# B. 6·12월 시점 종목 모멘텀 (양수 = 직전 승자가 계속 이김 → 승자 매도·패자 매수형 리밸런싱이 불리)')
    for nm, R in (('국내 전체 2010~', KR), ('국내 코스닥 2010~', KQ), ('미국 대형 2000~', US)): momentum_6m(nm, R)
    ind = ff_table('49_Industry_Portfolios.csv', 'Average Value Weighted Returns -- Monthly')
    momentum_6m('FF 49산업 1927~', ind['1927-01':].dropna(axis=1))
    mom = ff_table('F-F_Momentum_Factor.csv', 'Mom')
    m6 = []
    for p in mom.index:
        if p.month in (6, 12):
            nxt = mom.loc[p + 1:p + 6]
            if len(nxt) == 6: m6.append(np.prod(1 + nxt.iloc[:, 0].values) - 1)
    m6 = pd.Series(m6) * 100
    print(f'  {"FF 개별주 모멘텀(UMD) 1927~":32s} 다음 6개월 평균 {m6.mean():+.2f}%p (t={m6.mean() / m6.std() * np.sqrt(len(m6)):.2f}, 양수 {(m6 > 0).mean() * 100:.0f}%, n={len(m6)})'
          f' · 1990~ {m6[-len(mom["1990":]) // 6:].mean():+.2f}%p')
    print('\n# C. 생존편향 없는 보조검증 — FF 49산업(시가가중, 상폐 포함) 무작위 6산업')
    I = ind['1927-01':'2026-08'].dropna(axis=1); random_test('FF 49산업 1927~', I, draws=1000)
    I2 = ind['2000-01':'2026-08'].dropna(axis=1); random_test('FF 49산업 2000~', I2, draws=1000)
    print('\n# D. 스타일 축(ETF·지수) — 6·12월 시작, 5년 보유: 반기 복원 vs 방치 (앱 중립 목표)')
    ys = lambda t: y(os.path.join(SD, f'y_{t}.json'))
    style_axis('국내 대형:소형 (KODEX200:코스닥)', ys('069500.KS'), ys('%5EKQ11'), .90)
    style_axis('미국 가치:성장 (IWD:IWF)', ys('IWD'), ys('IWF'), .60)
    style_axis('미국 대형:소형 (IWB:IWM)', ys('IWB'), ys('IWM'), .65)
