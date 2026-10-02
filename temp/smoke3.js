// v5.0 데이터수집 회귀 테스트: 실제 네이버/야후/업비트 응답 형태로 nativeGet을 스텁
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const els={};
const mkEl=()=>({style:{},_html:'',set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},textContent:'',value:'',
  setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},querySelector(){return mkEl();},querySelectorAll(){return[];}});
const calls=[];
const R={ // 2026-10 실측 응답 형태
  'm.stock.naver.com/api/stock/005930/basic':{closePrice:'276,250'},
  'm.stock.naver.com/api/stock/005930/integration':{totalInfos:[{code:'per',key:'PER',value:'12.39배'},{code:'eps',key:'EPS',value:'22,292원'},{code:'marketValue',key:'시총',value:'1,615조 345억'}],consensusInfo:{priceTargetMean:'489,762'}},
  'api.stock.naver.com/stock/NVDA/integration':null, // 접미사 없으면 400
  'api.stock.naver.com/stock/NVDA.O/integration':{corporateOverview:{},consensusInfo:{priceTargetMean:'322.11'}},
  'api.stock.naver.com/stock/AAPL.O/basic':{closePrice:'330.32'},
  'query1.finance.yahoo.com/v8/finance/chart/NVDA':{chart:{result:[{meta:{regularMarketPrice:180.5}}]}},
  'query1.finance.yahoo.com/v8/finance/chart/AAPL':null, // 429
  'api.upbit.com/v1/ticker?markets=KRW-BTC':[{market:'KRW-BTC',trade_price:150000000}],
};
const sandbox={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
 document:{getElementById(id){return els[id]=els[id]||mkEl();},addEventListener(){},querySelector(){return mkEl();},querySelectorAll(){return[];}},
 alert:()=>{},setTimeout:()=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise,encodeURIComponent,
 fetch:async(url)=>{const k=url.replace(/^https:\/\//,'').replace(/\?interval.*$/,'');calls.push(k);
   const v=Object.prototype.hasOwnProperty.call(R,k)?R[k]:null;if(v==null)throw new Error('http fail');return{json:async()=>v,text:async()=>JSON.stringify(v)};}};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const run=e=>vm.runInContext(e,sandbox);
let pass=0,fail=0;const ok=(c,m)=>{c?pass++:(fail++,console.log('✗',m));};
(async()=>{
  ok(await run("fetchKrTargetPrice('005930')")===489762,'KR 목표주가 consensusInfo');
  ok(await run("fetchUsTargetPrice('NVDA',null)")===322.11,'US 목표주가 네이버 해외 (접미사 탐색)');
  run("var hh={ticker:'NVDA'}");await run("fetchUsTargetPrice('NVDA',hh)");
  ok(run("hh.reuters")==='NVDA.O','Reuters 코드 캐시');
  ok(await run("fetchUsPrice('NVDA.O')")===180.5,'Reuters 접미사 제거 후 야후 조회');
  ok(await run("fetchUsPrice('AAPL')")===330.32,'야후 실패 시 네이버 해외 폴백');
  const info=await run("fetchStockInfo('005930',null,'kr')");
  ok(info.per===12.39&&info.eps===22292&&info.price===276250,'fetchStockInfo KR per/eps/price: '+JSON.stringify(info));
  ok(info.marketCap===1615e12+345e8,'시총 조/억 파싱: '+info.marketCap);
  ok(run("classifyTags('삼성전자','',12.39,"+info.marketCap+",'kr')").includes('대형주'),'대형주 판정');
  // 업비트: upbit 코드 없는 항목이 있어도 조회 성공
  run("portfolio.holdings.crypto=[{id:'c1',name:'BTC',upbit:'KRW-BTC',qty:1,avg:1,cur:1},{id:'c2',name:'수동',qty:1,avg:1,cur:5}]");
  run("portfolio.holdings.watchlist=[{id:'wx',name:'엔비디아',ticker:'NVDA',usd:true,cur:100,tags:[]}]");
  await run("updateAllPrices()");
  ok(run("portfolio.holdings.crypto[0].cur")===150000000,'업비트 시세 (빈 코드 필터)');
  ok(run("loadingPrice")===false,'loadingPrice 해제');
  ok(run("portfolio.holdings.watchlist[0].targetPrice")===322.11,'워치리스트 US 목표가 자동 반영');
  // 워치리스트 US 렌더: NaN 없음, USD 표기
  run("tab='holdings';catH='watch';render()");
  const out=els.app._html;
  ok(!out.includes('NaN'),'워치리스트 US 렌더 NaN 없음');
  ok(out.includes('$322.11')&&out.includes('$241.58'),'목표가/진입가 USD 표기');
  // 렌더 중 예외가 나도 loadingPrice 고착 안 됨
  run("var _r=render;render=()=>{throw new Error('boom')}");await run("updateAllPrices().catch(()=>{})");run("render=_r");
  ok(run("loadingPrice")===false,'예외 후 loadingPrice 해제');
  console.log(`\n${pass} passed, ${fail} failed`);process.exitCode=fail?1:0;
})();
