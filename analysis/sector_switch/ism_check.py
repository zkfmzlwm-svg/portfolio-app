# ISM 제조업 가격지수를 신호에 다시 넣으면 나아지는지 검증 (한국 1990~, kr_long 데이터)
#  ISM 가격지수 무료 장기 데이터가 없어 1968~ 필라델피아 연준 제조업 가격지수(PPCDFSA066MSFRBPHI, 같은 설문 확산지수)로 대신하고,
#  2021~ 실제 ISM(DBnomics) + 2026 앱 수집값을 이어 붙임. ISM은 다음 달 1일 발표 → 1개월 시차, 소매판매는 2개월 시차
from kr_long import *
RW = os.path.join(HERE, '..', 'regime_weights', 'data')
ph = pd.read_csv(os.path.join(RW, 'PPCDFSA066MSFRBPHI.csv')); ph.columns = ['d', 'v']
ph = pd.Series(ph.v.astype(float).values, index=pd.PeriodIndex(pd.to_datetime(ph.d), freq='M'))
j = json.load(open(os.path.join(RW, 'ismp.json')))['series']['docs']; s_in = next(x for x in j if x['series_code'] == 'in')
ism = pd.Series(s_in['value'], index=pd.PeriodIndex(s_in['period'], freq='M'))
app = pd.Series({'2026-01': 59.0, '2026-02': 70.5, '2026-03': 78.3, '2026-04': 84.6, '2026-05': 82.1, '2026-06': 73.0,
                 '2026-07': 71.1, '2026-08': 71.1, '2026-09': 77.9, '2026-10': 75.2}); app.index = pd.PeriodIndex(app.index, freq='M')
ismx = pd.concat([ph[:'2020-12'], ism, app]); ismx = ismx[~ismx.index.duplicated(keep='last')].sort_index()
def lagged(sig, k): sig = sig.copy(); sig.index = sig.index + k; return sig
s_ret = sig_e                                             # 소매판매 YoY 3개월 연속 (2개월 시차, 앱 기본)
s_ism = lagged(state_rule(ismx.rolling(3).mean(), 2), 1)  # ISM MA3 2회 연속 (홍춘욱 방식)
s_retma = lagged(state_rule(yoy.rolling(3).mean(), 2), 2) # 소매판매 MA3 2회 연속
def both(a, b):  # 원 듀얼 규칙: 둘 다 ↑ 수출, 둘 다 ↓ 내수, 그 외 직전 유지
    x = pd.concat([a, b], axis=1).dropna(); st, out = 0, []
    for u, v in x.values:
        st = 1 if (u > 0 and v > 0) else -1 if (u < 0 and v < 0) else st; out.append(st)
    return pd.Series(out, index=x.index)
SIGS = {'소매판매만 (현재 앱)': s_ret, 'ISM만': s_ism, '듀얼: 소매판매 MA3 + ISM 둘 다 (원 홍춘욱)': both(s_retma, s_ism),
        '듀얼: 소매판매 3개월 + ISM 둘 다': both(s_ret, s_ism)}
if __name__ == '__main__':
    base = d.copy()
    print('[수출/내수 신호별 — 수출 75/30 · 가치/성장은 금리 65/30 고정 규칙] 4칸 고정 대비 %p/년, 10년대별')
    for nm, sg in SIGS.items():
        x = base.copy(); x['e'] = sg.reindex(x.index).fillna(0)
        r = mix(x, .75, .30, .65, .30); b = mix(x, .5, .5, .5, .5); ex = r - b
        dec = ' '.join(f'{(mix(sub2:=x[(x.index>=pd.Period(a,"M"))&(x.index<=pd.Period(c,"M"))],.75,.30,.65,.30)-mix(sub2,.5,.5,.5,.5)).mean()*1200:+.1f}' for _, a, c in PER[:4])
        sp = ew(x['수출×가치'], x['수출×성장']) - ew(x['내수×가치'], x['내수×성장'])
        print(f'  {nm:34s} {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) | 10년대 {dec} | 수출−내수: 수출국면 {sp[x.e>0].mean()*1200:+.1f} / 내수국면 {sp[x.e<0].mean()*1200:+.1f} | 수출 {(x.e>0).mean()*100:.0f}% 내수 {(x.e<0).mean()*100:.0f}% 전환 {int((x.e.diff().abs()>0).sum())}회')
    print('\n[ISM을 가치/성장 신호로 쓰면? (인플레 ↑ → 가치)] 수출/내수는 소매판매 고정')
    for nm, sg in (('금리 3개월 변화 (현재 앱)', sig_v), ('ISM MA3 2회 연속', s_ism)):
        x = base.copy(); x['v'] = sg.reindex(x.index).fillna(0)
        va = ew(x['수출×가치'], x['내수×가치']) - ew(x['수출×성장'], x['내수×성장'])
        ex = mix(x, .75, .30, .65, .30) - mix(x, .75, .30, .5, .5)
        print(f'  {nm:24s} 가치−성장: 신호↑ {va[x.v>0].mean()*1200:+.1f} / 신호↓ {va[x.v<0].mean()*1200:+.1f} | 가치/성장 틸트 효과 {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f})')
    print('\n현재 상태: 소매판매', int(s_ret.iloc[-1]), '· ISM', int(s_ism.iloc[-1]), '· 원 듀얼', int(both(s_retma, s_ism).iloc[-1]), '(+1 수출/강세)')
