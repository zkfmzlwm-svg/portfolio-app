// v6.9 단타 탭 지수 그래프 — 파싱·부호·차트 SVG·갱신 주기/재시도·화면 상태
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const mkEl=id=>({id,style:{},_html:'',_attr:{},set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},textContent:'',value:'',
  setAttribute(k,v){this._attr[k]=v;},getAttribute(k){return this._attr[k]??null;},addEventListener(){},focus(){},select(){},
  querySelector(){return mkEl('q');},querySelectorAll(){return[];},getBoundingClientRect(){return{left:0,top:0,width:300,height:150};}});
const els={};
const sb={console,window:{innerWidth:390},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
  document:{getElementById(id){return els[id]=els[id]||mkEl(id);},addEventListener(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];},documentElement:mkEl('r')},
  alert(){},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,clearInterval(){},Date,Math,JSON,isNaN,isFinite,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise};
vm.createContext(sb);vm.runInContext(code,sb);
const run=e=>vm.runInContext(e,sb);
let pass=0,fail=0;const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('✗ FAIL:',m);}};

(async()=>{
  // 1. 실시간 파싱 — 상승·하락·보합 부호
  const rt=run(`idxParseRt({datas:[
    {itemCode:'KOSPI',closePrice:'5,222.58',compareToPreviousClosePrice:'203.73',compareToPreviousPrice:{code:'2'},fluctuationsRatio:'4.06',openPrice:'5,247.22',highPrice:'5,300.92',lowPrice:'5,184.58',marketStatus:'OPEN',localTradedAt:'2026-11-10T11:00:02+09:00'},
    {itemCode:'KOSDAQ',closePrice:'650.00',compareToPreviousClosePrice:'12.50',compareToPreviousPrice:{code:'5'},fluctuationsRatio:'1.89',marketStatus:'CLOSE',localTradedAt:'2026-11-10T15:30:00+09:00'},
    {reutersCode:'.SOX',closePrice:'10,000.00',compareToPreviousClosePrice:'-50.00',compareToPreviousPrice:{code:'5'},fluctuationsRatio:'-0.50',marketStatus:'CLOSE',localTradedAt:'2026-11-09T17:15:59-05:00'},
    {reutersCode:'.INX',closePrice:'7,000.00',compareToPreviousClosePrice:'0.00',compareToPreviousPrice:{code:'3'},fluctuationsRatio:'0.00'},
    {itemCode:'BAD',closePrice:'-'}]})`);
  ok(Math.abs(rt.KOSPI.chg-203.73)<1e-9&&Math.abs(rt.KOSPI.prev-5018.85)<1e-6&&rt.KOSPI.pct===4.06,'상승: 전일 = 현재 − 등락');
  ok(rt.KOSDAQ.chg===-12.5&&rt.KOSDAQ.pct===-1.89&&rt.KOSDAQ.prev===662.5,'하락 코드(5) → 음수, 기호 없는 값도');
  ok(rt['.SOX'].chg===-50&&rt['.SOX'].pct===-0.5,'하락 값에 − 기호가 있어도 한 번만 음수');
  ok(rt['.INX'].chg===0&&rt['.INX'].prev===7000,'보합');
  ok(!('BAD' in rt),'가격 없는 항목 제외');
  ok(run(`idxKstHm('2026-11-09T17:15:59-05:00')`)==='07:15'&&run(`idxKstYmd('2026-11-09T17:15:59-05:00')`)==='2026-11-10','미국 시각 → 한국 시간');

  // 2. 분봉·일봉·야후 파싱
  const mn=run(`idxParseMinute([{localDateTime:'20261110090000',currentPrice:5006.87},{localDateTime:'20261110090100',currentPrice:5058.2},{localDateTime:'20261109153000',currentPrice:1},{localDateTime:'20261110153000',currentPrice:5100},{localDateTime:'20261110160000',currentPrice:5101}],'2026-11-10')`);
  ok(mn.length===3&&mn[0].x===0&&mn[1].t==='09:01'&&mn[2].x===390,'분봉: 그날 09:00~15:30만, x=분: '+JSON.stringify(mn.map(p=>p.x)));
  const dy=run(`idxParseDay([{localDate:'20261110',closePrice:5220.07},{localDate:'20261109',closePrice:5018.85},{localDate:'x',closePrice:1}])`);
  ok(dy.length===2&&dy[0].d==='2026-11-09'&&dy[1].x===1&&dy[1].t==='11-10','일봉: 날짜순·순번');
  const t0=Date.parse('2026-11-09T14:30:00Z')/1000;
  const yh=run(`idxParseYahoo({chart:{result:[{meta:{gmtoffset:-18000,chartPreviousClose:7376.86,currentTradingPeriod:{regular:{start:${t0},end:${t0+23400}}}},timestamp:[${t0},${t0+300},${t0+600}],indicators:{quote:[{close:[7400,null,7410]}]}}]}})`);
  ok(yh&&yh.pts.length===2&&yh.pts[1].x===10&&yh.xMax===390&&yh.prev===7376.86&&yh.day==='2026-11-09','야후: 빈 값 제외·정규장 분·전일 종가');
  ok(yh.pts[0].t==='23:30','야후 시각은 한국 시간');
  ok(run('idxParseYahoo({chart:{result:[]}})')===null&&run('idxParseYahoo(null)')===null,'야후 빈 응답');

  // 3. 차트 SVG
  const ser={pts:mn,xMax:390,krDay:true,prev:5018.85,src:'네이버 1분봉'};
  sb.__ser=ser;const svg=run('idxChartSvg(__ser,"1d")');
  ok(!/NaN|undefined|Infinity/.test(svg),'SVG에 NaN 없음');
  ok(svg.includes('09:00')&&svg.includes('13:00')&&svg.includes('전일 5,018.85'),'국내 당일: 장 시간 축 + 전일 기준선');
  ok(/stroke-width="2"/.test(svg)&&/fill-opacity="0.1"/.test(svg)&&!/stroke-dasharray/.test(svg),'2px 선·10% 면·점선 없음');
  sb.__ys=Object.assign({},yh,{src:'야후'});const svgUs=run('idxChartSvg(__ys,"1d")');
  ok(!svgUs.includes('09:00')&&svgUs.includes('23:30'),'미국 당일 축은 한국 시간(390분이어도 국내 축 아님)');
  sb.__big={pts:[{x:0,t:'08-03',v:9011},{x:1,t:'08-04',v:13217}],xMax:1,prev:9011};
  const svgK=run('idxChartSvg(__big,"3m")'),labs=[...svgK.matchAll(/font-family="Menlo[^>]*>([^<]+)</g)].map(m=>m[1]);
  ok(labs.length>=3&&labs.every(l=>/K$/.test(l)),'한 축에는 한 가지 표기(K): '+labs.join(','));
  sb.__flat={pts:[{x:0,t:'a',v:100},{x:1,t:'b',v:100}],xMax:1,prev:100};
  ok(!/NaN|Infinity/.test(run('idxChartSvg(__flat,"1m")')),'변동 없는 값도 그리기');
  const down=run(`idxChartSvg({pts:[{x:0,t:'a',v:110},{x:1,t:'b',v:90}],xMax:1,prev:100},"1d")`);
  ok(down.includes(run('T.red'))&&!down.includes('stroke="'+run('T.green')+'"'),'기준 아래면 빨간 선');

  // 4. 크로스헤어 — 가장 가까운 점, 기준 대비 %
  run('idxChartSvg(__ser,"1d")');
  els.idxTip=mkEl('idxTip');els.idxTip.setAttribute('data-def','코스피 5,100.00');
  run('idxHover({clientX:300,clientY:50})');
  ok(/^15:30  5,100\.00  \(\+1\.62%\)$/.test(els.idxTip.textContent),'오른쪽 끝 → 마지막 점: '+els.idxTip.textContent);
  ok(els.idxX._attr.visibility==='visible','크로스헤어 표시');
  run('idxHover(null)');ok(els.idxTip.textContent==='코스피 5,100.00'&&els.idxX._attr.visibility==='hidden','손 떼면 기본 표시');

  // 5. 선택 저장·잘못된 값
  ok(JSON.stringify(run('idxSel()'))==='{"sel":"KOSPI","rng":"1d"}','기본 코스피·당일');
  run(`Store.set('dt_idx','{"sel":".SOX","rng":"3m"}')`);ok(run('idxSel().sel')==='.SOX'&&run('idxSel().rng')==='3m','선택 복원');
  run(`Store.set('dt_idx','{"sel":"X","rng":"9y"}')`);ok(run('idxSel().sel')==='KOSPI'&&run('idxSel().rng')==='1d','잘못된 저장값은 기본');
  run(`Store.set('dt_idx','not json')`);ok(run('idxSel().sel')==='KOSPI','깨진 저장값');

  // 6. 갱신 주기·실패 재시도 (네트워크 스텁)
  run(`window.__calls=[];nativeGet=async u=>{window.__calls.push(u);
    if(/realtime\\/domestic/.test(u))return{datas:[{itemCode:'KOSPI',closePrice:'5,100.00',compareToPreviousClosePrice:'81.15',compareToPreviousPrice:{code:'2'},fluctuationsRatio:'1.62',marketStatus:'OPEN',localTradedAt:'2026-11-10T15:30:00+09:00'}]};
    if(/realtime\\/worldstock/.test(u))return{datas:[]};
    if(/KOSPI\\/minute/.test(u))return[{localDateTime:'20261110090000',currentPrice:5050},{localDateTime:'20261110090100',currentPrice:5060}];
    if(/yahoo/.test(u))throw new Error('http fail');
    return[];};Store.set('dt_idx','{"sel":"KOSPI","rng":"1d"}');tab='home';`);
  await run('idxRefresh(false)');
  ok(run('dtCache.idx.ser["KOSPI|1d"].pts.length')===2&&run('dtCache.idx.ser["KOSPI|1d"].prev')===5018.85,'코스피 당일: 분봉 + 전일 종가');
  ok(run('window.__calls.some(u=>/minute\\?startDateTime=202611100900&endDateTime=202611101530/.test(u))'),'분봉 요청 날짜 = 실시간 기준일');
  const n1=run('window.__calls.length');await run('idxRefresh(false)');
  ok(run('window.__calls.length')===n1,'15초·60초 안에는 다시 안 부름');
  await run('idxRefresh(true)');ok(run('window.__calls.length')===n1+3,'새로고침은 강제로 다시');
  run(`Store.set('dt_idx','{"sel":".INX","rng":"1d"}')`);await run('idxRefresh(false)');
  ok(run('dtCache.idx.serErr[".INX|1d"].m')==='미국 당일 차트를 불러오지 못했습니다(야후)','야후 실패 메시지');
  const n2=run('window.__calls.length');await run('idxRefresh(false)');
  ok(run('window.__calls.filter(u=>/yahoo/.test(u)).length')===1&&run('window.__calls.length')===n2,'실패한 차트는 2분 안에 다시 안 부름');
  run('dtCache.idx.serErr[".INX|1d"].at-=121000');await run('idxRefresh(false)');
  ok(run('window.__calls.filter(u=>/yahoo/.test(u)).length')===2,'2분 뒤 재시도');

  // 7. 카드 상태별 렌더 (데이터 없음 / 오류 / 정상), 단타 탭 상단 배치
  const card=run('idxCard()');
  ok(card.includes('불러오지 못했습니다')&&card.includes('1개월 보기로'),'오류 상태 안내');
  run(`Store.set('dt_idx','{"sel":"KOSPI","rng":"1d"}')`);const c2=run('idxCard()');
  ok(c2.includes('idxSvg')&&c2.includes('5,100.00')&&c2.includes('▲81.15')&&c2.includes('시가')&&!/NaN|undefined/.test(c2),'정상 상태: 값·등락·통계');
  run('dtCache.idx={rt:{},rtAt:0,ser:{},serErr:{},busy:false,err:null}');const c3=run('idxCard()');
  ok(c3.includes('앱에서 열면')&&!/NaN|undefined/.test(c3),'브라우저(브릿지 없음) 안내');
  run("tab='daytrade';render()");const app=els.app._html;
  ok(app.indexOf('idxTip')>0&&app.indexOf('idxTip')<app.indexOf('미국 밤사이 신호'),'단타 탭 맨 위에 지수 카드');
  ok(app.includes('dtRefresh(false);idxRefresh(true)'),'새로고침 버튼이 지수도 갱신');

  console.log(`\n${pass} passed, ${fail} failed`);process.exit(fail?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
