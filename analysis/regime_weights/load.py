import json, sys, os
import pandas as pd, numpy as np

D = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))

def yahoo(name):
    j = json.load(open(os.path.join(D, f'y_{name}.json')))['chart']['result'][0]
    ts = pd.to_datetime(j['timestamp'], unit='s')
    q = j['indicators']
    px = q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close']
    s = pd.Series(px, index=ts).dropna()
    s.index = s.index.to_period('M')
    return s[~s.index.duplicated(keep='last')]

def fred(id_):
    df = pd.read_csv(os.path.join(D, f'{id_}.csv'))
    df.columns = ['date', 'v']
    df['v'] = pd.to_numeric(df['v'], errors='coerce')
    df = df.dropna()
    s = df.set_index(pd.to_datetime(df['date']))['v']
    return s

def monthly_last(s):
    s = s.resample('ME').last().dropna()
    s.index = s.index.to_period('M')
    return s

def monthly(s):
    s = s.copy(); s.index = s.index.to_period('M'); return s

fx = monthly_last(fred('DEXKOUS'))
px_usd = {
    'kr': None,
    'us': yahoo('SPY'),
    'bonds': yahoo('IEF'),
    'gold': yahoo('GLD'),
    'crypto': yahoo('BTC-USD'),
}
kr = yahoo('069500.KS')
# KRW-denominated monthly prices
px = pd.DataFrame({'kr': kr})
for k in ['us', 'bonds', 'gold', 'crypto']:
    px[k] = px_usd[k] * fx
px = px.sort_index()
# last month may be partial -> drop current month (2026-10)
px = px[px.index <= pd.Period('2026-09', 'M')]
ret = px.pct_change(fill_method=None)
ret_usd = pd.DataFrame({k: px_usd[k] for k in ['us', 'bonds', 'gold', 'crypto']}).pct_change(fill_method=None)
rf = monthly(fred('TB3MS')) / 100 / 12

# indicators
retail = monthly(fred('MRTSSM44X72USS'))
retail_yoy = (retail / retail.shift(12) - 1) * 100
philly = monthly(fred('PPCDFSA066MSFRBPHI'))
ism = json.load(open(os.path.join(D, 'ismp.json')))
ism_s = None
for s in ism['series']['docs']:
    if s['series_code'] == 'in':
        ism_s = pd.Series(s['value'], index=pd.PeriodIndex(s['period'], freq='M'))
