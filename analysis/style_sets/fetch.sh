#!/usr/bin/env bash
# 세트 백테스트 원자료 → ./data  (국면 신호는 ../regime_weights/fetch.sh, ../style_tilt/fetch.sh 먼저)
set -e
cd "$(dirname "$0")"; mkdir -p data; cd data
for t in 069500.KS 229200.KS %5EKQ11 091160.KS 091180.KS 091170.KS 161510.KS 157490.KS \
         VOO IVV VTV IWD VUG IWF AVUV IWN VBK IWO; do sleep 1
  curl -sS -A "Mozilla/5.0" -o "y_$t.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t?period1=0&period2=9999999999&interval=1mo&events=div"; done
