#!/usr/bin/env bash
# 분석용 원자료 다운로드 → ./data
set -e
cd "$(dirname "$0")"; mkdir -p data; cd data
for id in MRTSSM44X72USS PPIACO PPCDFSA066MSFRBPHI DEXKOUS TB3MS; do
  curl -sS -o $id.csv "https://fred.stlouisfed.org/graph/fredgraph.csv?id=$id"; done
curl -sS -o ismp.json "https://api.db.nomics.world/v22/series/ISM/prices?observations=1"
for t in %5EKS11 SPY IEF GLD GC%3DF BTC-USD; do sleep 1.5
  curl -sS -A "Mozilla/5.0" -o "y_$t.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t?period1=0&period2=9999999999&interval=1mo&events=div"; done
