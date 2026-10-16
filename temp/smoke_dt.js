// 단타 탭(v6.1) 로직 회귀 테스트: 미국 신호 정렬·판정·모의매매 장부·야후 파싱·화면·주문 모달·마이그레이션
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const vals={};   // getElementById(id).value 스텁
const els={};
const mkEl=id=>({id,style:{},_html:'',set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},
  get value(){return vals[id]??'';},set value(v){vals[id]=v;},addEventListener(){},focus(){},blur(){},querySelector(){return mkEl('q');}});
const alerts=[];
const sandbox={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
  document:{getElementById(id){els[id]=els[id]||mkEl(id);return els[id];},addEventListener(){},querySelector:()=>mkEl('q'),querySelectorAll:()=>[]},
  alert:m=>alerts.push(m),confirm:()=>true,setTimeout:()=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const run=e=>vm.runInContext(e,sandbox);
let pass=0,fail=0;
const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('✗ FAIL:',m);}};
const near=(a,b,e=1e-12)=>Math.abs(a-b)<e;
const clean=s=>!/undefined|NaN|\[object/.test(s);

(async()=>{
// 1. 미국 신호 정렬: 한국 D의 신호 = P ≤ u < D 인 미국 세션들의 누적 등락
sandbox.__bars=[{d:'2026-10-07',c:100},{d:'2026-10-08',c:96},{d:'2026-10-09',c:95.04},{d:'2026-10-12',c:95}];
let s=run("dtUsChange(__bars,'2026-10-08','2026-10-12')");   // 한국 목(10-08) → 월(10-12, 10-09 한글날 휴장)
ok(s&&near(s.chg,95.04/100-1)&&s.n===2&&s.to==='2026-10-09','휴장 낀 월요일: 미국 목·금 2세션 누적 '+JSON.stringify(s));
s=run("dtUsChange(__bars,'2026-10-12','2026-10-13')");
ok(s&&near(s.chg,95/95.04-1)&&s.n===1,'화요일: 미국 월요일 1세션');
ok(run("dtUsChange(__bars.filter(x=>x.d!=='2026-10-12'),'2026-10-12','2026-10-13')")===null,'미국 휴장(새 세션 없음) → 신호 없음');
s=run("dtUsChange(__bars,'2026-10-12',null)");
ok(s&&s.to==='2026-10-12'&&s.from==='2026-10-09','다음 거래일 미정 → 끝난 세션 전부');
ok(run("dtUsChange(__bars,'2026-10-07','2026-10-08')")===null,'기준 종가 이전 데이터 없으면 신호 없음');

// 2. 판정
ok(run("dtHit({dir:'down',th:3},-0.03)")===true&&run("dtHit({dir:'down',th:3},-0.029)")===false,'하락 −3% 기준');
ok(run("dtHit({dir:'up',th:3},0.03)")===true&&run("dtHit({dir:'up',th:3},0.02)")===false,'상승 +3% 기준');
ok(near(run('dtNetRet(200000,206000,false,0.015)'),206000*(1-0.00015-0.002)/(200000*1.00015)-1),'개별주 순수익(거래세 0.2%)');
ok(near(run('dtNetRet(10000,10100,true,0.015)'),10100*(1-0.00015)/(10000*1.00015)-1),'ETF 순수익(세금 없음)');

// 3. 모의매매: 신호일 시가 매수 → 다음 거래일 시가 매도
sandbox.__us=[{d:'2026-10-06',c:100},{d:'2026-10-07',c:101},{d:'2026-10-08',c:97},{d:'2026-10-09',c:97.5},{d:'2026-10-12',c:98}];
sandbox.__cs=[{d:'2026-10-07',o:190000,h:192000,l:188000,c:191000},{d:'2026-10-08',o:192000,h:193000,l:190000,c:191500},
              {d:'2026-10-12',o:200000,h:206000,l:199000,c:205000},{d:'2026-10-13',o:206000,h:207000,l:203000,c:204000}];
run("__p={id:'p1',label:'반도체',us:'SOXX',dir:'down',th:3,codes:[]};__m={code:'000660',name:'SK하이닉스',etf:false}");
run("__dt={exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{}}");
let open=run("dtProcessPair(__dt,__p,__m,__cs,__us,'2026-10-14',false)");
let paper=run('__dt.paper');
ok(paper.length===1&&open.length===0,'10-12 한 건(미국 목·금 −3.47%) 확정');
ok(paper[0].d==='2026-10-12'&&paper[0].ent===200000&&paper[0].xp===206000&&paper[0].xd==='2026-10-13','시가 200,000 매수 → 다음 거래일 시가 206,000 매도');
ok(near(paper[0].ret,206000*(1-0.00015-0.002)/(200000*1.00015)-1)&&near(paper[0].chg,97.5/101-1),'순수익·신호 등락 기록');
ok(run("__dt.done['p1|000660']")==='2026-10-13','확정일 기록');
run("__p.th=1;dtProcessPair(__dt,__p,__m,__cs,__us,'2026-10-14',false);__p.th=3");
ok(run('__dt.paper.length')===1&&run('__dt.paper[0].th')===3,'재처리해도 중복 없음 · 설정 바꿔도 확정 거래 유지');
// 다음 거래일 시가가 아직 없으면 보유 중
run("__dt2={exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{}}");
open=run("dtProcessPair(__dt2,__p,__m,__cs.slice(0,3),__us,'2026-10-12',false)");
ok(open.length===1&&open[0].ent===200000&&run('__dt2.paper.length')===0&&run("__dt2.done['p1|000660']")==='2026-10-08','청산 전 → 보유 중, 확정은 전날까지');
// 당일 종가 청산
run("__dt3={exit:'close',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{}}");
open=run("dtProcessPair(__dt3,__p,__m,__cs.slice(0,3),__us,'2026-10-12',false)");
ok(open.length===1&&run('__dt3.paper.length')===0,'종가 청산: 장중엔 보유');
run("dtProcessPair(__dt3,__p,__m,__cs.slice(0,3),__us,'2026-10-12',true)");
ok(run('__dt3.paper.length')===1&&run('__dt3.paper[0].xp')===205000,'종가 청산: 마감 후 종가 205,000');
// 상승 후 매수 방향 · 미국 휴장
run("__dt4={exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{}};__pu={id:'pu',us:'SOXX',dir:'up',th:0.5,codes:[]}");
run("dtProcessPair(__dt4,__pu,__m,__cs,__us,'2026-10-14',false)");
open=run("dtProcessPair(__dt4,__pu,__m,__cs,__us,'2026-10-14',false)");
ok(JSON.stringify(run('__dt4.paper.map(x=>x.d)'))==='["2026-10-08"]'&&run("__dt4.done['pu|000660']")==='2026-10-12'&&open.length===1&&open[0].d==='2026-10-13','상승 방향: 10-08(+1%) 확정, 10-13(+0.51%)은 다음 거래일 시가 대기');
run("__dt5={exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{}}");
run("dtProcessPair(__dt5,__p,__m,__cs,__us.filter(x=>x.d<'2026-10-08'),'2026-10-14',false)");
ok(run('__dt5.paper.length')===0,'미국 데이터에 없는 구간은 신호 없음');
// 통계
const st=run(`dtStats([{ret:0.01,amt:1e6},{ret:-0.005,amt:2e6}])`);
ok(st.n===2&&st.win===0.5&&near(st.avg,0.25)&&near(st.pnl,0),'통계 '+JSON.stringify(st));

// 4. 야후 응답 파싱: 진행 중인 정규장은 끝난 세션에서 빼고 live로
const now=Math.floor(Date.now()/1000),day=86400;
const mkResp=(liveNow)=>{const st0=liveNow?now-3600:now+3600;
  return {chart:{result:[{meta:{regularMarketPrice:94,currentTradingPeriod:{regular:{start:st0,end:st0+23400}}},
    timestamp:[st0-2*day,st0-day,st0].filter(t=>liveNow||t<now),indicators:{quote:[{close:[100,98,95].slice(0,liveNow?3:2)}]}}]}};};
sandbox.__resp=mkResp(true);run("nativeGet=async()=>__resp");
let u=await run("dtFetchUs('SOXX','2026-10-01')");
ok(u.ok&&u.bars.length===2&&u.live&&u.live.c===94&&near(u.live.chg,94/98-1),'장중: 끝난 세션 2개 + live(실시간가 94, −4.08%)');
sandbox.__resp=mkResp(false);
u=await run("dtFetchUs('SOXX','2026-10-01')");
ok(u.bars.length===2&&u.live===null,'장 마감 후: live 없음');
// 야후 일봉 목록이 막 끝난 세션을 아직 싣지 않은 경우 → meta 정규장 종가로 보충 (2026-10-15 아침 실제 사례: SOXX 10-14 −4.50%)
const nextSt=now+36000;
sandbox.__resp={chart:{result:[{meta:{regularMarketPrice:519.42,regularMarketTime:Date.UTC(2026,9,14,20,0)/1000,currentTradingPeriod:{regular:{start:nextSt,end:nextSt+23400}}},
  timestamp:[Date.UTC(2026,9,12,13,30)/1000,Date.UTC(2026,9,13,13,30)/1000],indicators:{quote:[{close:[544.85,543.9]}]}}]}};
u=await run("dtFetchUs('SOXX','2026-10-01')");
ok(u.bars.length===3&&u.bars[2].d==='2026-10-14'&&u.bars[2].c===519.42&&u.live===null,'일봉에 없는 직전 세션(10-14)을 정규장 종가로 보충');
sandbox.__ub=u.bars;
ok(near(run("dtUsChange(__ub,'2026-10-14','2026-10-15')").chg,519.42/543.9-1),'보충 후 10-15 신호 = SOXX −4.50%');
sandbox.__resp.chart.result[0].timestamp.push(Date.UTC(2026,9,14,13,30)/1000);sandbox.__resp.chart.result[0].indicators.quote[0].close.push(519.5);
u=await run("dtFetchUs('SOXX','2026-10-01')");
ok(u.bars.length===3&&u.bars[2].c===519.5,'일봉에 이미 있으면 그대로 사용');

// 5. 화면 신호: 시각 고정(2026-10-13 화 08:40, 장 전) — 미국 월요일 −4% → 오늘 시가 매수
run("kstNow=()=>new Date(Date.UTC(2026,9,13,8,40))");
ok(run('kstYmd()')==='2026-10-13'&&run('kstHm()')===840,'테스트 시각 고정');
sandbox.__usA=[{d:'2026-10-08',c:100},{d:'2026-10-09',c:100},{d:'2026-10-12',c:96}];
sandbox.__usB=[{d:'2026-10-08',c:500},{d:'2026-10-09',c:500},{d:'2026-10-12',c:510}];
sandbox.__krA=[{d:'2026-10-08',o:190000,h:192000,l:188000,c:191000},{d:'2026-10-12',o:192000,h:194000,l:190000,c:193000}];
sandbox.__krB=[{d:'2026-10-08',o:100000,h:101000,l:99000,c:100500},{d:'2026-10-12',o:100500,h:101500,l:100000,c:101000}];
run(`portfolio.dt={pairs:[{id:'p1',label:'반도체',us:'SOXX',ref:'SOXL',dir:'down',th:3,codes:[{code:'000660',name:'SK하이닉스',etf:false}]},
  {id:'p2',label:'지수',us:'SPY',ref:'',dir:'down',th:1.5,codes:[{code:'069500',name:'KODEX 200',etf:true}]}],
  exit:'nextopen',amt:1000000,fee:0.015,start:'2026-10-13',paper:[],done:{},orders:[]}`);
run(`dtCache.us={SOXX:{bars:__usA,live:null,ok:true},SOXL:{bars:__usA.map(x=>({d:x.d,c:x.c*0.9})),live:null,ok:true},SPY:{bars:__usB,live:null,ok:true}};
  dtCache.kr={'000660':__krA,'069500':__krB};dtCache.rt={'000660':{o:0,h:0,l:0,cur:193000,status:'CLOSE',t:'2026-10-12T15:30:00+09:00'}};dtCompute()`);
let v=run("dtCache.sig.p1");
ok(v&&v.when==='preopen'&&v.hit===true&&near(v.s.chg,-0.04)&&v.ref,'장 전: SOXX −4% → 오늘 시가 매수 신호 '+JSON.stringify(v&&{when:v.when,hit:v.hit}));
ok(run("dtCache.sig.p2.hit")===false&&run("dtCache.sig.p2.contra")===true,'SPY +2% → 신호 없음 · 급등 매수 보류');
run("tab='daytrade';dtSub='signal';render()");
let out=els.app._html;
ok(clean(out)&&out.includes('오늘 매수 ✓')&&out.includes('⚡ 매매')&&out.includes('08:30~09:00 시장가 매수')&&out.includes('급등 · 매수 보류')&&out.includes('SOXL'),'신호 화면(장 전)');
// 장중(10:00): 오늘 봉 생김 → 같은 신호, 모의 보유 1건, 매도 대상 표시
run("kstNow=()=>new Date(Date.UTC(2026,9,13,10,0))");
run("dtCache.rt={'000660':{o:186000,h:189000,l:185000,cur:188000,status:'OPEN',t:'2026-10-13T10:00:00+09:00'}};dtCompute()");
v=run("dtCache.sig.p1");
ok(v.when==='today'&&v.hit===true,'장중: 오늘 신호 유지');
ok(run("dtCache.open['p1|000660'].length")===1&&run("dtCache.open['p1|000660'][0].ent")===186000,'모의 보유: 오늘 시가 186,000');
ok(run("portfolio.dt.done['p2|069500']")==='2026-10-13'||run("portfolio.dt.done['p2|069500']")===undefined,'SPY 쌍: 오늘 신호 없음 처리');
run("render()");out=els.app._html;
ok(clean(out)&&out.includes('시가 이후 진입은')&&out.includes('매도 대상')&&out.includes('시가 186,000'),'신호 화면(장중): 시가 이후 안내·매도 대상');
// 다음 날 시가가 생기면 확정
run("kstNow=()=>new Date(Date.UTC(2026,9,14,9,5))");
run("dtCache.kr['000660']=__krA.concat([{d:'2026-10-13',o:186000,h:189000,l:185000,c:188500}]);dtCache.rt={'000660':{o:190000,h:190500,l:189000,cur:190200,status:'OPEN',t:'2026-10-14T09:05:00+09:00'}};dtCache.us.SOXX.bars=__usA.concat([{d:'2026-10-13',c:96.5}]);dtCompute()");
ok(run('portfolio.dt.paper.length')===1&&run('portfolio.dt.paper[0].xp')===190000,'다음 거래일 시가 190,000 청산 확정');
// 상승 방향 경고 · 데이터 없음
run("portfolio.dt.pairs.push({id:'p3',label:'원래안',us:'SOXL',ref:'',dir:'up',th:3,codes:[{code:'005930',name:'삼성전자',etf:false}]});dtCompute();render()");
out=els.app._html;
ok(clean(out)&&out.includes('백테스트상 손실')&&out.includes('데이터 없음'),'상승 방향 경고 · 데이터 없는 쌍');
// 모의매매·설정 화면
for(const sub of['paper','cfg']){run(`dtSub='${sub}';render()`);out=els.app._html;ok(clean(out),'단타/'+sub+' 렌더');
  if(sub==='paper')ok(out.includes('거래당')&&out.includes('반도체 (SOXX)'),'모의매매: 성과·쌍별');
  if(sub==='cfg')ok(out.includes('하락 후 매수 (권장)')&&out.includes('기본 5쌍 합산')&&out.includes('LLY ≤ −4%')&&out.includes('dtPU_p1'),'설정: 쌍 편집·백테스트 표(5쌍)');}

// 6. 설정 편집
vals.dtPL_p2='지수2';vals.dtPU_p2='qqq';vals.dtPR_p2='';vals.dtPT_p2='2';
run("dtSavePair('p2')");
ok(run("JSON.stringify(dtPair('p2'))").includes('"us":"QQQ"')&&run("dtPair('p2').th")===2&&run("dtPair('p2').label")==='지수2','쌍 저장: 티커 대문자·기준·이름');
vals.dtPT_p2='0';alerts.length=0;run("dtSavePair('p2')");
ok(alerts.length===1&&run("dtPair('p2').th")===2,'기준 0 이하 거부');
run("dtPairDir('p2','up')");ok(run("dtPair('p2').dir")==='up','방향 전환(확인 후)');
const n0=run('portfolio.dt.pairs.length');run("dtAddPair()");ok(run('portfolio.dt.pairs.length')===n0+1,'쌍 추가');
run("dtRemovePair(portfolio.dt.pairs[portfolio.dt.pairs.length-1].id)");ok(run('portfolio.dt.pairs.length')===n0,'쌍 삭제');
run("dtRemoveCode('p3','005930')");ok(run("dtPair('p3').codes.length")===0,'종목 삭제');

// 7. 주문 모달 (B)
run("kstNow=()=>new Date(Date.UTC(2026,9,14,8,40))");   // 장 전
alerts.length=0;run("dtOrder('000660','buy')");
ok(alerts.length===1&&/API 키/.test(alerts[0]),'증권사 키 없으면 안내');
sandbox.window.KisBridge.hasKeys=()=>true;
run("dtCache.rt={'000660':{o:0,h:0,l:0,cur:188500,status:'CLOSE',t:'2026-10-13T15:30:00+09:00'}}");
run("dtOrder('000660','buy')");
ok(run('window._dtOrder.type')==='market'&&run('window._dtOrder.qty')===Math.floor(1000000/188500),'장 전 매수: 시장가 · 5주');
let modal=els['modal-root']._html;
ok(clean(modal)&&modal.includes('09:00 시가에 체결')&&!modal.includes('id="dtPrice"'),'장 전 모달: 시가 체결 안내·가격 입력 없음');
run("kstNow=()=>new Date(Date.UTC(2026,9,14,10,0))");
run("dtOrder('000660','buy')");
ok(run('window._dtOrder.type')==='limit'&&els['modal-root']._html.includes('시가 이후 매수는'),'장중 매수: 지정가 + 안내');
run("sendBrokerOrder=async(...a)=>{__sent=a;return 'A1';}");
vals.dtQty='5';vals.dtPrice='188550';alerts.length=0;
await run('confirmDtOrder()');
ok(alerts.some(a=>/호가단위/.test(a))&&run('portfolio.dt.orders.length')===0,'호가단위(100원) 위반 가격은 전송 안 함');
vals.dtPrice='188500';
await run('confirmDtOrder()');
ok(run('portfolio.dt.orders.length')===1&&run('portfolio.dt.orders[0].orderNo')==='A1'&&JSON.stringify(run('__sent'))===JSON.stringify(['kis','buy','000660',false,5,188500]),'주문 전송·기록 '+JSON.stringify(run('__sent')));
run("dtOrder('000660','sell')");
ok(run('window._dtOrder.qty')===5&&run('window._dtOrder.type')==='market','매도 기본값: 최근 매수 5주 · 시장가');

// 9. 내 보유현황(증권사 잔고) + ⚡ 매매 (v6.2)
{const kb=run('dtBalRows')('kis',{rt_cd:'0',rows:[{pdno:'000660',prdt_name:'SK하이닉스',hldg_qty:'2',ord_psbl_qty:'2',pchs_avg_pric:'190000.0000',prpr:'188500'},
   {pdno:'069500',prdt_name:'KODEX 200',hldg_qty:'0',ord_psbl_qty:'0',pchs_avg_pric:'0',prpr:'40000'}]});
 ok(kb.length===1&&kb[0].code==='000660'&&kb[0].qty===2&&kb[0].avg===190000&&kb[0].cur===188500&&kb[0].broker==='kis','한투 잔고 파싱(0주 제외) '+JSON.stringify(kb));
 const wb=run('dtBalRows')('kiwoom',{return_code:0,acnt_evlt_remn_indv_tot:[{stk_cd:'A005930',stk_nm:'삼성전자',rmnd_qty:'000000000000005',trde_able_qty:'000000000000003',pur_pric:'000000000095000',cur_prc:'-97000'}]});
 ok(wb.length===1&&wb[0].code==='005930'&&wb[0].qty===5&&wb[0].sellable===3&&wb[0].avg===95000&&wb[0].cur===97000,'키움 잔고 파싱(A 접두·0 채움·부호) '+JSON.stringify(wb));}
run("dtRefresh=async()=>{}");
sandbox.window.KisBridge.balance=(demo,id)=>{sandbox.window.KisBridge.fetch=()=>JSON.stringify({rt_cd:'0',rows:[
  {pdno:'000660',prdt_name:'SK하이닉스',hldg_qty:'2',ord_psbl_qty:'2',pchs_avg_pric:'190000',prpr:'188000'},
  {pdno:'005930',prdt_name:'삼성전자',hldg_qty:'5',ord_psbl_qty:'5',pchs_avg_pric:'95000',prpr:'97000'},
  {pdno:'360750',prdt_name:'TIGER 미국S&P500',hldg_qty:'3',ord_psbl_qty:'1',pchs_avg_pric:'20000',prpr:'21000'}]});sandbox.window.KisBridge._deliver(id);};
await run('dtLoadBalance()');
ok(run('portfolio.dt.bal.rows.length')===3&&/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(run('portfolio.dt.bal.at.kis'))&&JSON.parse(sandbox.localStorage._d.porto).dt.bal.rows.length===3,'보유 불러오기 → 저장');
run("dtCache.rt={'000660':{o:0,h:0,l:0,cur:188500,status:'OPEN',t:''}}");
run("tab='daytrade';dtSub='signal';render()");
out=els.app._html;
ok(clean(out)&&out.includes('내 보유현황')&&out.includes('보유수량')&&out.includes('평균단가')&&out.includes('2주')&&out.includes('매도가능 1주'),'보유현황 카드 렌더');
ok(out.includes('color:#FF4D67">-3,000')&&out.includes('color:#22D07A">+10,000'),'손익금액: 손해 빨강(실시간가 188,500 반영)/이익 초록');
ok(out.includes('보유 2주')&&(out.match(/⚡ 매매/g)||[]).length>=5,'종목쌍 행·보유 카드 모두 ⚡ 매매');
run("dtOrder('000660','sell')");
ok(run('window._dtOrder.qty')===2&&run('window._dtOrder.type')==='market'&&els['modal-root']._html.includes('보유 2주'),'매도 기본값: 잔고 매도가능 2주 우선');
run("dtOrdSet('side','buy')");
ok(run('window._dtOrder.side')==='buy'&&run('window._dtOrder.qty')===Math.floor(1000000/188500)&&run('window._dtOrder.type')==='limit','매수로 전환 → 1회 금액 수량·지정가(장중)');
run("dtOrdSet('side','sell')");ok(run('window._dtOrder.qty')===2,'다시 매도 → 잔고 수량');
run("dtOrder('360750','sell')");
ok(run("dtFindCode('360750').name")==='TIGER 미국S&P500'&&run("dtFindCode('360750').etf")===true&&run('window._dtOrder.qty')===1,'종목쌍 밖 보유 종목: 이름·ETF·매도가능 1주');
run("closeModal()");

// 8. 마이그레이션: v6.0(변동성 돌파 구조) → 새 기본 쌍, 주문 기록만 유지
const mig=run(`migratePortfolio({ver:'6.0',targets:{kr:20,us:30,bonds:10,gold:25,crypto:15},holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],watchlist:[]},txns:[],
  dt:{codes:[{code:'069500'}],k:0.7,filt:'none',exit:'nextopen',amt:1000000,fee:0.015,start:'2026-10-01',paper:[{key:'old'}],done:{'069500':'2026-10-10'},obs:{},orders:[{d:'2026-10-12',code:'069500'}]}})`);
ok(mig.ver==='6.1'&&mig.dt.pairs.length===6&&mig.dt.pairs[0].us==='SOXX'&&mig.dt.pairs[0].th===3&&mig.dt.pairs[1].us==='SPY'&&mig.dt.pairs[1].th===1.5&&mig.dt.pairs.map(p=>p.us).slice(2).join()==='LLY,ALB,XOM,QQQ','v6.0 → 기본 6쌍(SOXX −3%, SPY −1.5%, LLY·ALB·XOM −4%, QQQ +2% 역추세)');
ok(mig.dt.paper.length===0&&mig.dt.orders.length===1&&mig.dt.start===run('kstYmd()')&&!mig.dt.codes,'모의매매 새로 시작 · 주문 기록 유지');
const kept=run(`migratePortfolio({ver:'6.1',targets:{kr:20,us:30,bonds:10,gold:25,crypto:15},holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],watchlist:[]},txns:[],
  dt:{pairs:[{id:'x',us:'QQQ',dir:'down',th:2,codes:[]}],exit:'close',amt:500000,fee:0.01,start:'2026-09-01',paper:[{key:'a'}]}})`);
ok(kept.dt.pairs.length===5&&kept.dt.pairs[0].us==='QQQ'&&kept.dt.pairs.slice(1).map(p=>p.id).join()==='bio,bat,eng,fade'&&kept.dt.sectorsV1===true&&kept.dt.start==='2026-09-01'&&kept.dt.paper.length===1&&Array.isArray(kept.dt.orders)&&typeof kept.dt.done==='object','v6.1 설정·기록 유지 + 누락 필드 보완');

// v6.3: 바이오·2차전지·에너지 쌍 — 1회만 추가, 지운 쌍은 다시 안 넣음, 근거 약함 표시
{const once=run(`migratePortfolio({ver:'6.1',targets:{kr:20,us:30,bonds:10,gold:25,crypto:15},holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],watchlist:[]},txns:[],
   dt:{pairs:[{id:'p1',us:'SOXX',dir:'down',th:3,codes:[]},{id:'bio',us:'LLY',dir:'down',th:5,codes:[]}],start:'2026-09-01'}})`);
 ok(once.dt.pairs.length===5&&once.dt.pairs.find(p=>p.id==='bio').th===5,'같은 id 쌍(사용자 수정)은 덮어쓰지 않음');
 once.dt.pairs=once.dt.pairs.filter(p=>p.id!=='eng');sandbox.__once=once;
 const again=run('migratePortfolio(__once)');ok(again.dt.pairs.length===4&&!again.dt.pairs.some(p=>p.id==='eng'),'지운 쌍은 다시 추가 안 함');
 const d=run('DT_DEFAULT');ok(d.pairs.find(p=>p.id==='bat').codes.map(c=>c.code).join()==='305720,086520'&&d.pairs.find(p=>p.id==='bio').codes.every(c=>c.etf)&&d.pairs.find(p=>p.id==='eng').weak===true,'기본 쌍 구성');
 run("portfolio.dt=JSON.parse(JSON.stringify(DT_DEFAULT));portfolio.dt.start=kstYmd();dtCache.sig={eng:{s:{chg:-0.05,n:1,to:'2026-10-15'},hit:true,when:'preopen'}};dtCache.rt={};dtCache.series={}");
 const c=run("dtPairCard(dtPair('eng'),portfolio.dt)");
 ok(clean(c)&&c.includes('근거 약함')&&c.includes('(근거 약함)')&&c.includes('color:#FFB020'),'에너지 쌍 카드: 근거 약함 메모·주황 배지');}

// v6.3: 급등 역추세 — 시가 매수 → 시가 +tp% 지정가 익절, 못 닿으면 당일 종가 / 인버스·레버리지 차익과세
{ok(run('dtTpPrice(10000,0.5,true)')===10050&&run('dtTpPrice(1990,0.5,true)')===2000&&run('dtTpPrice(188500,0.5,false)')===189500,'익절 목표가 호가단위 올림');
 ok(near(run('dtNetRet(10000,10050,true,0.015,true)'),(1+0.005*(1-0.154))*(1-0.00015)/1.00015-1)&&near(run('dtNetRet(10000,9900,true,0.015,true)'),(1-0.01)*(1-0.00015)/1.00015-1),'인버스 ETF: 이익에만 15.4% 과세');
 const fp=run("JSON.parse(JSON.stringify(DT_DEFAULT.pairs.find(p=>p.id==='fade')))");
 ok(fp.dir==='up'&&fp.th===2&&fp.exit==='tp'&&fp.tp===0.5&&fp.codes.every(c=>c.etf&&c.gtax)&&fp.codes.map(c=>c.code).join()==='114800,251340','기본 역추세 쌍 구성');
 sandbox.__fp=fp;
 sandbox.__ub=[{d:'2026-10-06',c:100},{d:'2026-10-07',c:103},{d:'2026-10-08',c:103.5},{d:'2026-10-09',c:106}];
 sandbox.__ic=[{d:'2026-10-07',o:3000,h:3010,l:2980,c:3000},{d:'2026-10-08',o:2950,h:2970,l:2930,c:2940},{d:'2026-10-12',o:2900,h:2905,l:2880,c:2890},{d:'2026-10-13',o:2880,h:2890,l:2860,c:2870}];
 run("__dt={start:'2026-10-01',exit:'nextopen',fee:0.015,amt:1000000,paper:[],done:{},orders:[]}");
 const op=run("dtProcessPair(__dt,__fp,__fp.codes[0],__ic,__ub,'2026-10-13',false)");
 const pp=run('__dt.paper');
 // 10-08: QQQ +3%(10-07) → 시가 2950, 목표 2965(호가 5) ≤ 고가 2970 → 익절 / 10-12: +2.4%(10-09) → 목표 2915 > 고가 2905 → 종가 2890
 ok(pp.length===2&&pp[0].d==='2026-10-08'&&pp[0].xp===2965&&pp[0].xd==='2026-10-08'&&pp[0].exit==='tp'&&pp[1].d==='2026-10-12'&&pp[1].xp===2890,'익절 체결 / 못 닿으면 당일 종가 '+JSON.stringify(pp.map(x=>[x.d,x.xp])));
 ok(pp[0].ret>0&&pp[1].ret<0&&op.length===0,'수익·손실 기록, 미결 없음');
 // 오늘 장중(목표 미도달) → 미결 + 목표가 / 장 마감 후 → 종가 확정
 sandbox.__ic2=[{d:'2026-10-09',o:3000,h:3000,l:2990,c:3000},{d:'2026-10-12',o:2900,h:2905,l:2880,c:2895}];
 run("__dt2={start:'2026-10-01',exit:'nextopen',fee:0.015,amt:1000000,paper:[],done:{},orders:[]}");
 const op2=run("dtProcessPair(__dt2,__fp,__fp.codes[0],__ic2,__ub,'2026-10-12',false)");
 ok(op2.length===1&&op2[0].tgt===2915&&run('__dt2.paper.length')===0,'장중 미도달 → 미결(목표가 2,915)');
 run("dtProcessPair(__dt2,__fp,__fp.codes[0],__ic2,__ub,'2026-10-12',true)");
 ok(run('__dt2.paper.length')===1&&run('__dt2.paper[0].xp')===2895,'장 마감 후 → 당일 종가 확정');
 // 화면: 역추세 카드는 손실 경고 없음, 규칙에 익절 표시 / 매도 카드는 익절 지정가
 run("portfolio.dt=JSON.parse(JSON.stringify(DT_DEFAULT));portfolio.dt.start=kstYmd();dtCache.sig={fade:{s:{chg:0.025,n:1,to:'2026-10-15'},hit:true,when:'preopen'}};dtCache.rt={};dtCache.series={}");
 const fc=run("dtPairCard(dtPair('fade'),portfolio.dt)");
 ok(clean(fc)&&fc.includes('+0.5% 익절')&&fc.includes('시가 +0.5% 지정가 익절, 못 닿으면 당일 종가 매도')&&!fc.includes('백테스트상 손실')&&fc.includes('차익과세 15.4%'),'역추세 카드: 익절 규칙·차익과세, 손실 경고 없음');
 const sc=run("dtPairCard(dtPair('p1'),portfolio.dt)");ok(sc.includes('다음 거래일 시가 매도')||!sc.includes('익절'),'다른 쌍은 공통 매도 방식');
 run("dtCache.open={'fade|114800':[{key:'k',d:kstYmd(),pair:'fade',us:'QQQ',chg:0.025,code:'114800',name:'KODEX 인버스',etf:true,ent:2900,tgt:2915}]};dtSub='signal';render()");
 out=els.app._html;ok(out.includes('익절 지정가 매도 (2,915원)')&&out.includes("dtOrder('114800','sell',2915)"),'매도 대상: 익절 지정가 버튼');
 sandbox.window.KisBridge.hasKeys=()=>true;run("dtOrder('114800','sell',2915)");
 ok(run('window._dtOrder.type')==='limit'&&run('window._dtOrder.price')===2915,'익절 주문: 지정가 2,915원 미리 채움');run('closeModal()');
 // 설정: 매도 방식 전환·익절 % 저장
 run("dtPairExit('p1','tp')");ok(run("dtPair('p1').exit")==='tp'&&run("dtPair('p1').tp")===0.5,'쌍 매도 방식 → 당일 익절(기본 0.5%)');
 run("dtSub='cfg';render()");ok(els.app._html.includes('id="dtPP_p1"'),'익절 % 입력칸');
 vals.dtPL_p1='반도체';vals.dtPU_p1='SOXX';vals.dtPR_p1='SOXL';vals.dtPT_p1='3';vals.dtPP_p1='0.8';run("dtRefresh=async()=>{}");run("dtSavePair('p1')");
 ok(run("dtPair('p1').tp")===0.8,'익절 % 저장');
 run("dtPairExit('p1','')");ok(run("dtPair('p1').exit")===undefined,'공통 설정으로 복귀');}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
