// 단타 탭(v5.6) 로직 회귀 테스트: 호가단위·돌파 판정·모의매매 장부·감지가·주문 모달
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

(async()=>{
// 1. 호가단위 (ETF 2천원 이상 5원, 주식 가격대별)
ok(run('krTick(1999,true)')===1&&run('krTick(95000,true)')===5,'ETF 호가단위');
ok(run('krTick(4999,false)')===5&&run('krTick(19990,false)')===10&&run('krTick(49950,false)')===50&&run('krTick(199900,false)')===100&&run('krTick(250000,false)')===500&&run('krTick(600000,false)')===1000,'주식 호가단위');
ok(run('ceilTick(101017.5,true)')===101020&&run('ceilTick(101020,true)')===101020,'ETF 목표가 호가 올림');
ok(run('ceilTick(49990,false)')===50000&&run('ceilTick(250001,false)')===250500,'주식 목표가 호가 올림');

// 2. 돌파 판정: 목표가 = 시가 + k × 전일 범위
const cs=[{d:'2026-10-01',o:10000,h:10200,l:9900,c:10100},{d:'2026-10-02',o:10050,h:10300,l:10000,c:10280},{d:'2026-10-05',o:10400,h:10450,l:10350,c:10420}];
sandbox.__cs=cs;
const s1=run("dtSignalAt(__cs,1,{k:0.7,filt:'none'},true)");
ok(s1.tgt===10260&&s1.hit===true&&s1.pass===true,'목표가 10050+0.7×300=10260, 고가 10300 돌파: '+JSON.stringify(s1));
ok(run("dtSignalAt(__cs,1,{k:0.9,filt:'none'},true)").hit===false,'k 0.9 → 목표가 10320 미돌파');
ok(run("dtSignalAt(__cs,1,{k:0.7,filt:'ma5'},true)")===null,'MA5 계산 불가(이력 부족) → 신호 없음');
ok(run("dtSignalAt(__cs,0,{k:0.7,filt:'none'},true)")===null,'첫 봉은 전일 없음');

// 3. 순수익: 수수료 양방향 + 개별주만 거래세 0.20%
ok(near(run('dtNetRet(10000,10100,true,0.015)'),10100*(1-0.00015)/(10000*1.00015)-1),'ETF 순수익(세금 없음)');
ok(near(run('dtNetRet(10000,10100,false,0.015)'),10100*(1-0.00015-0.002)/(10000*1.00015)-1),'개별주 순수익(거래세 0.2%)');

// 4. 모의매매: 다음날 시가 청산 → 확정·멱등·설정 변경 후에도 유지
run("__dt={k:0.7,filt:'none',exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{},obs:{}};__m={code:'069500',name:'KODEX 200',etf:true}");
let open=run("dtProcessPaper(__dt,__m,__cs,'2026-10-06',false)");
let paper=run('__dt.paper');
ok(paper.length===1&&open.length===0,'거래 1건 확정, 보유 없음');
ok(paper[0].ent===10265&&paper[0].xp===10400&&paper[0].xd==='2026-10-05','진입 = 목표가+1호가 10265, 청산 = 다음날 시가 10400');
ok(near(paper[0].ret,10400*(1-0.00015)/(10265*1.00015)-1),'모의 순수익 계산');
ok(run("__dt.done['069500']")==='2026-10-05','확정일 기록');
run("__dt.k=0.3");run("dtProcessPaper(__dt,__m,__cs,'2026-10-06',false)");
ok(run('__dt.paper.length')===1&&run('__dt.paper[0].k')===0.7,'재처리해도 중복 없음 · 설정 바꿔도 확정 거래 유지');
// 다음날 시가가 아직 없으면 보유 중
run("__dt2={k:0.7,filt:'none',exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-01',paper:[],done:{},obs:{}}");
open=run("dtProcessPaper(__dt2,__m,__cs.slice(0,2),'2026-10-02',false)");
ok(open.length===1&&open[0].ent===10265&&run('__dt2.paper.length')===0,'청산 전 → 보유 중 1건');
ok(!run("__dt2.done['069500']")||run("__dt2.done['069500']")<'2026-10-02','미청산일은 확정 표시 안 함');
// 당일 종가 청산: 장 마감 확정 전에는 보유, 확정 후 종가 청산
run("__dt3={k:0.7,filt:'none',exit:'close',fee:0.015,amt:1000000,start:'2026-10-02',paper:[],done:{},obs:{}}");
open=run("dtProcessPaper(__dt3,__m,__cs.slice(0,2),'2026-10-02',false)");
ok(open.length===1&&run('__dt3.paper.length')===0,'종가 청산: 장중엔 보유');
open=run("dtProcessPaper(__dt3,__m,__cs.slice(0,2),'2026-10-02',true)");
ok(open.length===0&&run('__dt3.paper.length')===1&&run('__dt3.paper[0].xp')===10280,'종가 청산: 마감 후 종가 10280 청산');
// 시작일 이전 돌파는 무시, 미돌파 장중 날은 대기
run("__dt4={k:0.7,filt:'none',exit:'nextopen',fee:0.015,amt:1000000,start:'2026-10-05',paper:[],done:{},obs:{}}");
run("dtProcessPaper(__dt4,__m,__cs,'2026-10-05',false)");
ok(run('__dt4.paper.length')===0&&!run("__dt4.done['069500']"),'시작일 이전 무시 · 오늘 미돌파(장중)는 미확정');

// 5. 통계
const st=run(`dtStats([{ret:0.01,amt:1e6,obs:10030,tgt:10000},{ret:-0.005,amt:2e6,obs:null,tgt:10000}])`);
ok(st.n===2&&st.win===0.5&&near(st.avg,0.25)&&near(st.pnl,0)&&near(st.slip,0.3,1e-9)&&st.nObs===1,'통계: 건수·승률·평균·손익·실측 슬리피지 '+JSON.stringify(st));

// 6. 실시간 병합: 오늘 날짜일 때만 오늘 봉으로 사용
const today=run('kstYmd()'),y1=run(`dtAddDays('${today}',-1)`),y2=run(`dtAddDays('${today}',-2)`);
sandbox.__base=[{d:y2,o:10000,h:10200,l:9900,c:10100},{d:y1,o:10100,h:10300,l:10000,c:10200}];
ok(run(`dtMergeToday(__base,{o:10150,h:10180,l:10120,cur:10170,t:'${today}T10:00:00+09:00'},'${today}')`).length===3,'오늘 시세 → 오늘 봉 추가');
ok(run(`dtMergeToday(__base,{o:10150,h:10180,l:10120,cur:10170,t:'${y1}T15:30:00+09:00'},'${today}')`).length===2,'휴장(시세 날짜≠오늘) → 추가 안 함');
ok(run(`dtMergeToday(__base,{o:0,h:0,l:0,cur:10200,t:'${today}T08:40:00+09:00'},'${today}')`).length===2,'장 시작 전(시가 0) → 추가 안 함');

// 7. 감지가: 이번 실행 중 '대기'를 본 뒤 돌파한 것만 기록 (오늘 목표가 = 10150 + 0.7×300 = 10360)
run(`portfolio.dt={k:0.7,filt:'none',exit:'nextopen',fee:0.015,amt:1000000,start:'${today}',paper:[],done:{},obs:{},orders:[],codes:[{code:'069500',name:'KODEX 200',etf:true}]}`);
run(`dtCache.candles={'069500':__base};dtCache.seenWait={};dtCache.newHit=null`);
run(`dtCache.rt={'069500':{o:10150,h:10340,l:10120,cur:10330,status:'OPEN',t:'${today}T10:00:00+09:00'}};dtCompute()`);
ok(run("dtCache.sig['069500'].tgt")===10360&&run("dtCache.sig['069500'].hit")===false,'장중 대기: 목표가 10360');
ok(Object.keys(run('portfolio.dt.obs')).length===0,'대기 중엔 감지가 없음');
run(`dtCache.rt={'069500':{o:10150,h:10380,l:10120,cur:10375,status:'OPEN',t:'${today}T10:01:00+09:00'}};dtCompute()`);
ok(run(`portfolio.dt.obs['${today}|069500'].px`)===10375,'대기 → 돌파 감지가 10375 기록');
ok(run('dtCache.newHit.names[0]')==='KODEX 200','돌파 알림');
ok(run("dtCache.open['069500'].length")===1&&run("dtCache.open['069500'][0].obs")===10375,'모의 보유에 감지가 연결');
// 앱을 늦게 열어 이미 돌파된 경우는 감지가 없음
run(`portfolio.dt.obs={};dtCache.seenWait={};dtCompute()`);
ok(Object.keys(run('portfolio.dt.obs')).length===0,'처음 본 시점에 이미 돌파 → 감지가 기록 안 함');

// 8. 화면 렌더 (신호·모의매매·설정) — undefined/NaN 없음
run(`dtCache.seenWait={'069500':'${today}'};dtCompute()`);
run(`portfolio.dt.paper=[{key:'x',d:'${y2}',code:'069500',name:'KODEX 200',etf:true,k:0.7,filt:'none',exit:'nextopen',amt:1000000,tgt:10000,ent:10005,xd:'${y1}',xp:10100,ret:0.0093,obs:10020}]`);
run(`portfolio.dt.orders=[{d:'${today}',hm:'10:02',code:'069500',name:'KODEX 200',side:'buy',qty:96,price:10380,broker:'kis',orderNo:'1'}]`);
for(const sub of['signal','paper','cfg']){
  run(`tab='daytrade';dtSub='${sub}';render()`);
  const out=els.app._html;
  ok(!/undefined|NaN|\[object/.test(out),'단타/'+sub+' 렌더 깨짐 없음');
  if(sub==='signal')ok(out.includes('돌파 ✓')&&out.includes('⚡ 매수 주문')&&out.includes('청산 대상')&&out.includes('최근 주문'),'신호 화면: 돌파·매수 버튼·청산 대상·최근 주문');
  if(sub==='paper')ok(out.includes('거래당')&&out.includes('실측 슬리피지'),'모의매매 화면: 성과·실측 슬리피지');
  if(sub==='cfg')ok(out.includes('0.7 권장')&&out.includes('KODEX 200'),'설정 화면');
}
// 필터 제외·시가 대기·데이터 없음 상태
run(`portfolio.dt.filt='ma20';portfolio.dt.codes.push({code:'005930',name:'삼성전자',etf:false});dtCompute();dtSub='signal';render()`);
let out=els.app._html;
ok(!/undefined|NaN/.test(out)&&out.includes('데이터 없음')&&out.includes('개별주·거래세'),'MA20(이력 부족)·데이터 없음·개별주 표시');
run(`portfolio.dt.filt='none';portfolio.dt.codes.pop();dtCache.rt={};dtCompute();render()`);
out=els.app._html;
ok(out.includes('시가 대기')&&!/undefined|NaN/.test(out),'장 시작 전 → 시가 대기 + 다음 목표가');
run(`dtCache.rt={'069500':{o:10150,h:10380,l:10120,cur:10375,status:'OPEN',t:'${today}T10:01:00+09:00'}};dtCompute()`);

// 9. 주문 모달 (B): 키 없으면 안내, 있으면 지정가 = max(현재가, 목표가), 수량 = 1회 금액 ÷ 가격
alerts.length=0;run("dtOrder('069500','buy')");
ok(alerts.length===1&&/API 키/.test(alerts[0]),'증권사 키 없으면 안내');
sandbox.window.KisBridge.hasKeys=()=>true;
run("dtOrder('069500','buy')");
ok(run('window._dtOrder.price')===10375&&run('window._dtOrder.qty')===Math.floor(1000000/10375)&&run('window._dtOrder.type')==='limit','매수 기본값: 지정가 10375 · 96주');
const modal=els['modal-root']._html;
ok(modal.includes('매수 주문 전송')&&modal.includes('목표가 10,360')&&!/undefined|NaN/.test(modal),'주문 모달 렌더');
run("dtOrdSet('type','market')");
ok(!els['modal-root']._html.includes('id="dtPrice"'),'시장가 → 가격 입력 숨김');
run("dtOrdSet('type','limit')");
// 호가단위 위반 → 전송 안 함
run("sendBrokerOrder=async(...a)=>{__sent=a;return 'A1';}");
vals.dtQty='96';vals.dtPrice='10377';alerts.length=0;
await run('confirmDtOrder()');
ok(alerts.some(a=>/호가단위/.test(a))&&run('portfolio.dt.orders.length')===1,'호가단위 위반 가격은 전송 안 함');
vals.dtPrice='10375';
await run('confirmDtOrder()');
ok(run('portfolio.dt.orders.length')===2&&run('portfolio.dt.orders[1].orderNo')==='A1','주문 전송 후 기록');
ok(JSON.stringify(run('__sent'))===JSON.stringify(['kis','buy','069500',false,96,10375]),'증권사 전송 인자: '+JSON.stringify(run('__sent')));
// 매도: 최근 매수 수량을 기본값으로, 시장가
run("dtOrder('069500','sell')");
ok(run('window._dtOrder.qty')===96&&run('window._dtOrder.type')==='market','매도 기본값: 최근 매수 96주 · 시장가');

// 10. 마이그레이션: 단타 상태 기본값, 기존 값 유지
const mig=run(`migratePortfolio({ver:'5.5',targets:{kr:20,us:30,bonds:10,gold:25,crypto:15},holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],watchlist:[]},txns:[]})`);
ok(mig.ver==='5.6'&&mig.dt.k===0.7&&mig.dt.exit==='nextopen'&&mig.dt.codes.length===4&&mig.dt.codes.every(c=>c.etf)&&mig.dt.start===today,'v5.5 → 단타 기본값(ETF 4종, k 0.7, 다음날 시가) · 시작일 오늘');
const kept=run(`migratePortfolio({ver:'5.6',targets:{kr:20,us:30,bonds:10,gold:25,crypto:15},holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],watchlist:[]},txns:[],dt:{k:0.5,filt:'ma20',exit:'close',amt:500000,fee:0.01,start:'2026-09-01',codes:[{code:'069500',name:'KODEX 200',etf:true}],paper:[{key:'a'}]}})`);
ok(kept.dt.k===0.5&&kept.dt.start==='2026-09-01'&&kept.dt.paper.length===1&&Array.isArray(kept.dt.orders)&&typeof kept.dt.obs==='object','기존 단타 설정·기록 유지 + 누락 필드 보완');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
