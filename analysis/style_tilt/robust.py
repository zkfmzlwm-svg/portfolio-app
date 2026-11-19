# 주식 버킷 내부 스타일 목표 재산정 (v7.1) — weights.py(구판) 문제 보완
#  구판 문제
#   1) 두 자산 Sharpe 최대화는 0%/100% 코너해가 나와, 전체·전반·후반 코너해를 평균한 기준비중이 임의적
#      (US 대형:소형 100/0/100 → 65 → 소형주 35%: 시가총액 비중 ~7%의 5배)
#   2) KODEX200(배당 포함 수정주가) vs 코스닥 지수(가격지수, 배당 제외) → 대형주 쪽에 연 ~1.1%p 유리한 편향
#   3) 국면 틸트를 같은 표본에서 고르고 같은 표본으로 평가(인샘플) → 아웃오브샘플 검증 없음
#  신규 방법
#   기준(중립) = 시장 앵커(시가총액·지수 집계 기준) + 0.5 × (블록 부트스트랩 Sharpe 최적 평균 − 앵커), 5%p 반올림
#   국면 틸트 = 국면별 스프레드 초과분을 평균분산 크기로 환산 후 증거 강도(t²/(1+t²))로 축소, ±20%p 상한
#   검증 = 2010~ 워크포워드(매년 1월 그 이전 데이터만으로 재추정) 아웃오브샘플 Sharpe/초과수익 t
from tilt_bt import *
rng = np.random.default_rng(42)
G = np.arange(0, 1.0001, 0.05)
def sharpe(r): return r.mean() / r.std() * np.sqrt(12)

# ---- 데이터 보정 ----
KQ_DIV = 0.006 / 12          # 코스닥 배당수익률 ~0.6%/년 (KODEX 코스닥150 수정-종가 차이 0.62%/년, 2015~)
kr_large, kr_small = y('069500.KS'), y('%5EKQ11') + KQ_DIV
small = p6[['SMALL LoBM', 'ME1 BM2', 'SMALL HiBM']].mean(axis=1)   # FF 2x3: 소형 3개 동일가중
big = p6[['BIG LoBM', 'ME2 BM2', 'BIG HiBM']].mean(axis=1)
# 축: (이름, A, B, 시장 앵커 A%, 앵커 근거)
AXES = [
    ('kr.size',   '국내 대형:소형 (KODEX200 : 코스닥+배당)', kr_large, kr_small, 0.80, 'KOSPI200 ≈ 국내 시총 80%'),
    ('kr.export', '국내 수출:내수 (섹터ETF 5:5)',          kr_exp,   kr_dom,   0.65, '수출 섹터(반도체·자동차·조선·화학·철강) ≈ KOSPI 시총 65%'),
    ('kr.value',  '국내 가치:시장 (고배당 : KODEX200)',     y('161510.KS'), y('069500.KS'), 0.50, '참고(신규 축 후보)'),
    ('us.value',  '해외 가치:성장 (IWD : IWF)',            y('IWD'), y('IWF'), 0.50, '지수 ETF를 50:50 집계하는 앱 규칙과 일치'),
    ('us.size',   '해외 대형:소형 (IWB : IWM)',            y('IWB'), y('IWM'), 0.90, 'Russell 1000 ≈ Russell 3000 시총 93%'),
    ('us.value.ff', '[검증] FF 대형 가치:성장 (BIG HiBM : LoBM)', p6['BIG HiBM'], p6['BIG LoBM'], 0.50, '1993~ 장기표본'),
    ('us.size.ff',  '[검증] FF 대형:소형 (BIG 3 : SMALL 3)',     big, small, 0.90, '1993~ 장기표본'),
]

def frame(a, b, end=END):
    d = pd.DataFrame({'a': a, 'b': b, 'reg': regime}).dropna(); return d[d.index <= end]

def boot_w(d, n=400, block=12):
    """12개월 블록 부트스트랩 → 표본별 Sharpe 최적 w의 평균 (Michaud 리샘플링: 코너해 완화)"""
    a, b = d.a.values, d.b.values; T = len(d); ws = []
    for _ in range(n):
        idx = np.concatenate([np.arange(s, s + block) % T for s in rng.integers(0, T, T // block + 1)])[:T]
        ra, rb = a[idx], b[idx]
        sh = [(w * ra + (1 - w) * rb).mean() / (w * ra + (1 - w) * rb).std() for w in G]
        ws.append(G[int(np.argmax(sh))])
    return float(np.mean(ws))

def fit(d, anchor, lam=0.5, gamma=None, cap=0.20):
    """기준 w0과 국면별 w 추정 (d: 학습 구간)"""
    wb = boot_w(d)
    w0 = round((anchor + lam * (wb - anchor)) * 20) / 20
    s = d.a - d.b; mu = s.mean(); var = s.var()
    # 위험회피계수: 버킷 전체 변동성 기준 시장 균형 (γ≈3, 월 단위)
    g = 3.0 if gamma is None else gamma
    port_var = ((w0 * d.a + (1 - w0) * d.b)).var()
    out = {}
    for r in ('bull', 'neutral', 'bear'):
        x = s[d.reg == r]
        if len(x) < 12: out[r] = w0; continue
        diff = x.mean() - mu
        se = np.sqrt(x.var() / len(x) + var / len(s))
        t = diff / se if se > 0 else 0
        shrink = t * t / (1 + t * t)
        dw = diff / (g * var) * shrink
        dw = float(np.clip(dw, -cap, cap))
        out[r] = float(np.clip(round((w0 + dw) * 20) / 20, 0.05, 0.95))
    return w0, wb, out

def perf(r):
    cagr = (1 + r).prod() ** (12 / len(r)) - 1; return cagr * 100, sharpe(r)

def walk_forward(a, b, anchor, start='2010-01', use_tilt=True):
    d = frame(a, b); rows = []
    years = sorted(set(p.year for p in d.index if p >= pd.Period(start, 'M')))
    for yv in years:
        tr = d[d.index < pd.Period(f'{yv}-01', 'M')]; te = d[(d.index >= pd.Period(f'{yv}-01', 'M')) & (d.index <= pd.Period(f'{yv}-12', 'M'))]
        if len(tr) < 60 or not len(te): continue
        w0, _, wr = fit(tr, anchor)
        w = te.reg.map(wr) if use_tilt else pd.Series(w0, index=te.index)
        rows.append(pd.DataFrame({'r': w * te.a + (1 - w) * te.b, 'w0': w0, 'w': w,
                                  'anc': anchor * te.a + (1 - anchor) * te.b, 'a': te.a, 'b': te.b, 'reg': te.reg}))
    return pd.concat(rows)

OLD = {'kr.size': (0.95, 0.90, 0.75), 'kr.export': (0.65, 0.65, 0.65), 'us.value': (0.75, 0.60, 0.45), 'us.size': (0.80, 0.65, 0.80)}

if __name__ == '__main__':
    pd.set_option('display.width', 200)
    print('국면 분포', regime[regime.index <= END].value_counts().to_dict())
    print('\n[1] 전체표본 추정 — 앵커 / 부트스트랩 최적 / 기준 / 국면 틸트 (A%)')
    res = {}
    for key, nm, a, b, anc, why in AXES:
        d = frame(a, b); w0, wb, wr = fit(d, anc); res[key] = (w0, wr)
        s = d.a - d.b; ann = s.groupby(d.reg).mean() * 1200
        print(f'{nm:42s} {d.index[0]}~ 앵커 {anc:.0%} 부트 {wb:.0%} → 기준 {w0:.0%} | 강세/중립/약세 '
              f'{wr["bull"]:.0%}/{wr["neutral"]:.0%}/{wr["bear"]:.0%} | 스프레드 %/년 강세 {ann.get("bull",0):.1f} 중립 {ann.get("neutral",0):.1f} 약세 {ann.get("bear",0):.1f}')
        for nm2, (h0, h1) in (('전반', (None, 0.5)), ('후반', (0.5, None))):
            n = len(d); part = d.iloc[int(n * (h0 or 0)):int(n * (h1 or 1))]
            p0, pb, pr = fit(part, anc)
            print(f'{"":42s}   {nm2} {part.index[0]}~{part.index[-1]}: 부트 {pb:.0%} 기준 {p0:.0%} 틸트 {pr["bull"]:.0%}/{pr["neutral"]:.0%}/{pr["bear"]:.0%}')

    print('\n[2] 워크포워드 아웃오브샘플 (2010~, 매년 재추정) — CAGR % / Sharpe')
    for key, nm, a, b, anc, why in AXES:
        wf = walk_forward(a, b, anc); wfs = walk_forward(a, b, anc, use_tilt=False)
        line = f'{nm:42s} 앵커고정 {perf(wf.anc)[0]:5.2f}/{perf(wf.anc)[1]:.3f} · 기준고정 {perf(wfs.r)[0]:5.2f}/{perf(wfs.r)[1]:.3f} · 기준+틸트 {perf(wf.r)[0]:5.2f}/{perf(wf.r)[1]:.3f}'
        ex = wf.r - wfs.r; line += f' · 틸트 초과 t {ex.mean()/ex.std()*np.sqrt(len(ex)) if ex.std()>0 else 0:.2f}'
        if key in OLD:
            ob, on, oe = OLD[key]; w = wf.reg.map({'bull': ob, 'neutral': on, 'bear': oe}); r = w * wf.a + (1 - w) * wf.b
            line += f' | 구판(인샘플) {perf(r)[0]:5.2f}/{perf(r)[1]:.3f}'
        print(line)
        print(f'{"":42s}   기준 추이 {wfs.groupby(wfs.index.year).w0.first().iloc[[0, len(set(wfs.index.year))//2, -1]].to_dict()}')

# ---- [3] 최종 규칙: 시장 앵커 고정 + '부호 일관' 국면만 소폭 틸트 (워크포워드로 규칙 자체를 검증) ----
def sign_rule(d, anchor, k):
    """학습구간을 전/후반으로 나눠 (국면 스프레드 − 전체 평균)의 부호가 두 구간 모두 같고,
       전체 학습구간 t≥1 인 국면에만 앵커 ±k 틸트. 그 외 국면은 앵커."""
    n = len(d); halves = (d.iloc[:n // 2], d.iloc[n // 2:]); out = {}
    for r in ('bull', 'neutral', 'bear'):
        sg = []
        for h in halves:
            s = h.a - h.b; x = s[h.reg == r]
            sg.append(np.sign(x.mean() - s.mean()) if len(x) >= 6 else 0)
        s = d.a - d.b; x = s[d.reg == r]
        t = (x.mean() - s.mean()) / np.sqrt(x.var() / len(x) + s.var() / len(s)) if len(x) >= 6 else 0
        out[r] = anchor + k * sg[0] if (sg[0] == sg[1] != 0 and abs(t) >= 1.0) else anchor
        out[r] = float(np.clip(out[r], 0.05, 0.95))
    return out
def wf_rule(a, b, anchor, k, start='2010-01'):
    d = frame(a, b); rows = []
    for yv in sorted(set(p.year for p in d.index if p >= pd.Period(start, 'M'))):
        tr = d[d.index < pd.Period(f'{yv}-01', 'M')]; te = d[(d.index.year == yv)]
        if len(tr) < 60 or not len(te): continue
        wr = sign_rule(tr, anchor, k); w = te.reg.map(wr)
        rows.append(pd.DataFrame({'r': w * te.a + (1 - w) * te.b, 'anc': anchor * te.a + (1 - anchor) * te.b, 'reg': te.reg, 'w': w}))
    return pd.concat(rows)
if __name__ == '__main__':
    print('\n[3] 앵커 + 부호일관 틸트 (워크포워드 2010~) — Sharpe 앵커 → 규칙, 초과 t | 전체표본 규칙')
    for key, nm, a, b, anc, why in AXES:
        for k in (0.05, 0.10, 0.15):
            wf = wf_rule(a, b, anc, k); ex = wf.r - wf.anc
            t = ex.mean() / ex.std() * np.sqrt(len(ex)) if ex.std() > 0 else 0
            full = sign_rule(frame(a, b), anc, k)
            print(f'{nm:42s} k={k:.2f} Sharpe {perf(wf.anc)[1]:.3f} → {perf(wf.r)[1]:.3f} 초과 {ex.mean()*1200:+.2f}%/년 t {t:+.2f} | 전체표본 규칙 강세/중립/약세 {full["bull"]:.0%}/{full["neutral"]:.0%}/{full["bear"]:.0%}')
