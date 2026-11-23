#!/usr/bin/env bash
# 업종 ETF·스타일 ETF·미국 금리/소매판매 → ./data  (FF 6분위는 ../style_tilt/fetch.sh)
set -e
cd "$(dirname "$0")"; mkdir -p data; cd data
for t in 139260.KS 139250.KS 139240.KS 139290.KS 227550.KS 139270.KS 139280.KS 143860.KS 315270.KS 139220.KS \
         325010.KS 275290.KS 069500.KS IWD IWF IVV; do sleep 1
  curl -sS -A "Mozilla/5.0" -o "y_$t.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t?period1=0&period2=9999999999&interval=1mo&events=div"; done
for id in GS10 MRTSSM44X72USS; do curl -sS -o $id.csv "https://fred.stlouisfed.org/graph/fredgraph.csv?id=$id"; done
