# 홍춘욱 듀얼 스위칭 국면별(강세·중립·약세) 국내·해외 주식 ETF 세트 구성 + 백테스트
#  - 목표: 앱 기본 프리셋(홍춘욱 원전략) 스타일 비중 (index.html STYLE_TARGETS hong)
#  - 세 국면 모두 같은 ETF를 쓰고 비중만 바꿈(국면 전환 시 매매 최소화), 5%p 단위
#  - 핵심(KODEX 200 / VOO) 40% 고정, 위성 ETF 5%~상한(국내 30·해외 35%) — 상한·핵심은 목표오차 5%p 이내 중 회전율 최소 조합
#  - 스타일 비중은 앱과 같은 방식(태그 기준 A/(A+B), '지수'는 가치/성장 50:50)으로 계산
#  - 백테스트: 국면 신호 2개월 시차(../style_tilt와 동일), 월 리밸런싱, 비용 제외, 현지통화
import os, sys, json, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'style_tilt'))
import numpy as np, pandas as pd
from style import regime, END   # 국면 시계열(2개월 시차 반영)

def y(t):
    j = json.load(open(os.path.join(HERE, 'data', f'y_{t}.json')))['chart']['result'][0]
    q = j['indicators']; px = q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close']
    s = pd.Series(px, index=pd.to_datetime(j['timestamp'], unit='s')).dropna()
    s.index = s.index.to_period('M'); s = s[~s.index.duplicated(keep='last')]
    return s.pct_change(fill_method=None)
def splice(main, proxy):  # 상장 전 구간은 대용 지수로 채움
    return main.combine_first(proxy)

# ---- 블록 (코드, 이름, 태그, 백테스트 수익률) ----
KR = [
    ('069500', 'KODEX 200',            ['대형주'],                    y('069500.KS')),
    ('229200', 'KODEX 코스닥150',       ['소형주', '성장주'],           splice(y('229200.KS'), y('%5EKQ11') + 0.006 / 12)),
    ('091160', 'KODEX 반도체',          ['대형주', '수출주', '성장주'],  y('091160.KS')),
    ('091180', 'KODEX 자동차',          ['대형주', '수출주', '가치주'],  y('091180.KS')),
    ('161510', 'PLUS 고배당주',          ['대형주', '내수주', '가치주'],  splice(y('161510.KS'), y('091170.KS'))),  # 금융·통신·필수소비 중심, 상장 전(2012-08 이전)은 KODEX 은행
    ('157490', 'TIGER 소프트웨어',       ['대형주', '내수주', '성장주'],  y('157490.KS')),
]
US = [
    ('VOO',  'Vanguard S&P 500',        ['지수', '대형주'],    splice(y('VOO'), y('IVV'))),
    ('VTV',  'Vanguard Value',          ['대형주', '가치주'],  splice(y('VTV'), y('IWD'))),
    ('VUG',  'Vanguard Growth',         ['대형주', '성장주'],  splice(y('VUG'), y('IWF'))),
    ('AVUV', 'Avantis US Small Cap Value', ['소형주', '가치주'], splice(y('AVUV'), y('IWN'))),
    ('VBK',  'Vanguard Small-Cap Growth', ['소형주', '성장주'], splice(y('VBK'), y('IWO'))),
]
# 홍춘욱 프리셋 목표 (A쪽 %) — index.html STYLE_TARGETS.*.hong 과 동일
TGT = {
    'kr': {'size': (80, 80, 80), 'export': (75, 65, 50), 'value': (65, 50, 35)},
    'us': {'value': (65, 50, 35), 'size': (95, 90, 75)},
}
AXIS = {'size': ('대형주', '소형주'), 'export': ('수출주', '내수주'), 'value': ('가치주', '성장주')}
REG = ('bull', 'neutral', 'bear'); RLAB = {'bull': '🟢 강세', 'neutral': '🔶 중립', 'bear': '🔴 약세'}

def ratio(w, blocks, ax):
    a, b = AXIS[ax]; A = B = 0.0
    for wi, (_, _, tags, _) in zip(w, blocks):
        if a in tags: A += wi
        elif b in tags: B += wi
        elif ax == 'value' and '지수' in tags: A += wi / 2; B += wi / 2
    return 100 * A / (A + B) if A + B else np.nan

def solve(blocks, targets, prior, step=5, wmin=5, wmax=25, core=40):
    """5%p 격자 전수탐색: 축별 목표와의 최대 오차 최소 → 동률이면 prior(기본 배분)와의 거리 최소"""
    n = len(blocks); best = None
    for cut in itertools.combinations(range(1, 100 // step), n - 1):
        w = np.diff((0,) + cut + (100 // step,)) * step
        if w[0] != core or w[1:].min() < wmin or w[1:].max() > wmax: continue
        err = max(abs(ratio(w, blocks, ax) - t) for ax, t in targets.items())
        key = (round(err, 1), float(((w - prior) ** 2).sum()))
        if best is None or key < best[0]: best = (key, w)
    return best[1], best[0][0]

def stats(r):
    r = r.dropna(); cagr = (1 + r).prod() ** (12 / len(r)) - 1; vol = r.std() * np.sqrt(12)
    eq = (1 + r).cumprod(); mdd = (eq / eq.cummax() - 1).min()
    return cagr * 100, vol * 100, cagr / vol, mdd * 100

def backtest(blocks, W, start):
    R = pd.concat({c: r for c, _, _, r in blocks}, axis=1)
    d = R.join(regime.rename('reg'), how='inner').dropna()
    d = d[(d.index >= pd.Period(start, 'M')) & (d.index <= END)]
    codes = [c for c, *_ in blocks]
    wmat = d.reg.map(lambda g: W[g] / 100.0)
    sw = pd.Series([float(np.dot(wmat.iloc[i], d[codes].iloc[i].values)) for i in range(len(d))], index=d.index)
    neu = d[codes] @ (W['neutral'] / 100.0)
    bench = d[codes[0]]
    turn = sum(np.abs(W[a] - W[b]).sum() / 2 for a, b in zip(d.reg.iloc[:-1], d.reg.iloc[1:]) if a != b) / 100 / (len(d) / 12)
    return d, sw, neu, bench, turn

if __name__ == '__main__':
    pd.set_option('display.width', 200)
    out = {}
    for key, blocks, prior, start, bname, wmax in (
            ('kr', KR, np.array([40, 12, 12, 12, 12, 12]), '2012-05', 'KODEX 200', 30),
            ('us', US, np.array([40, 15, 15, 15, 15]), '2000-08', 'S&P500', 35)):
        W = {}
        print(f'\n===== {"🇰🇷 국내주식" if key == "kr" else "🌏 해외주식"} 세트 (버킷 안 비중 %) =====')
        print(f'{"코드":8s} {"ETF":28s} {"태그":16s} ' + ' '.join(f'{RLAB[g]:>6s}' for g in REG))
        for i, g in enumerate(REG):
            W[g], err = solve(blocks, {ax: t[i] for ax, t in TGT[key].items()}, prior, wmax=wmax)
        for j, (c, nm, tags, _) in enumerate(blocks):
            print(f'{c:8s} {nm:28s} {"·".join(tags):16s} ' + ' '.join(f'{W[g][j]:>7d}' for g in REG))
        for ax, t in TGT[key].items():
            a, b = AXIS[ax]
            print(f'  {a}:{b} 달성 ' + ' / '.join(f'{RLAB[g]} {ratio(W[g], blocks, ax):.0f} (목표 {t[i]})' for i, g in enumerate(REG)))
        d, sw, neu, bench, turn = backtest(blocks, W, start)
        print(f'\n  백테스트 {d.index[0]}~{d.index[-1]} ({len(d)}개월, 국면 강세 {(d.reg=="bull").sum()} · 중립 {(d.reg=="neutral").sum()} · 약세 {(d.reg=="bear").sum()})')
        for nm, r in (('국면 스위칭 세트', sw), ('중립 세트 고정', neu), (bname + ' 단독', bench)):
            c, v, s, m = stats(r); print(f'  {nm:16s} CAGR {c:6.2f}%  변동성 {v:5.1f}%  Sharpe {s:.3f}  MDD {m:6.1f}%')
        ex = sw - neu; print(f'  스위칭 − 중립고정: 연 {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) · 국면 전환 매매 회전율 연 {turn*100:.0f}%')
        for g in REG:
            m = d.reg == g
            print(f'    {RLAB[g]} 구간 연환산: 스위칭 {sw[m].mean()*1200:6.1f}% · 중립고정 {neu[m].mean()*1200:6.1f}% · {bname} {bench[m].mean()*1200:6.1f}%')
        out[key] = {g: dict(zip([c for c, *_ in blocks], map(int, W[g]))) for g in REG}
    json.dump(out, open(os.path.join(HERE, 'sets.json'), 'w'), ensure_ascii=False, indent=1)
    print('\n현재 국면:', regime[regime.index <= regime.index.max()].iloc[-3:].to_dict())
