// v6.8.1 디버깅 회귀 테스트 — 초기화·복원 정규화, 현지 날짜, 통화 플래그 일관성, 가져오기 미리보기, 키움 주문 구분값, XSS 이스케이프
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];

// 고정 시각(기본: 한국 2026-11-09 00:30 = UTC 11-08 15:30) — today()가 UTC 전날로 나오던 문제 확인용
const FIX=Date.parse('2026-11-08T15:30:00Z');
class FDate extends Date{constructor(...a){if(a.length)super(...a);else super(FIX);}static now(){return FIX;}}

function mk(){
  const els={},modal={innerHTML:''};
  const mkEl=id=>({id,style:{},_html:'',set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},textContent:'',value:'',
    setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];}});
  const document={
    getElementById(id){
      if(id==='modal-root')return modal;
      if(/^imp(Apply|Q|C|A|Code)/.test(id)&&!modal.innerHTML.includes('id="'+id+'"'))return null;   // 모달 안 요소는 열려 있을 때만
      return els[id]=els[id]||mkEl(id);
    },
    addEventListener(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];},activeElement:null,documentElement:mkEl('root')};
  const timers=[];
  const sb={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},document,
    alert:()=>{},confirm:()=>true,setTimeout:(f,ms)=>{if(!(ms>0))timers.push(f);return timers.length;},clearTimeout(){},setInterval:()=>0,clearInterval(){},
    fetch:()=>Promise.reject(new Error('offline')),Date:FDate,Math,JSON,isNaN,isFinite,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise};
  vm.createContext(sb);vm.runInContext(code,sb);
  return{sb,modal,els,timers,run:e=>vm.runInContext(e,sb)};
}

let pass=0,fail=0;
const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('✗ FAIL:',m);}};

(async()=>{
  // 1. 현지 날짜 (KST 00:30) — 기존 toISOString()은 2026-11-08
  {const {run}=mk();
   process.env.TZ;   // 테스트는 TZ=Asia/Seoul로 실행 (아래 package 스크립트 참고)
   const d=new FDate(),local=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
   ok(run('today()')===local,'today()는 기기 현지 날짜, got '+run('today()')+' / '+local);
   if(process.env.TZ==='Asia/Seoul')ok(run('today()')==='2026-11-09','KST 00:30 → 2026-11-09');
   ok(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(run("localDT('2026-11-08T15:30:00Z')")),'localDT 형식');}

  // 2. 초기화·복원 뒤 입금 기록 추가가 오류 없이 동작 (deposits 배열 보장)
  {const {run,els}=mk();
   run('_doReset()');
   ok(Array.isArray(run('portfolio.deposits')),'초기화 후 deposits 배열');
   ok(run('portfolio.dt&&Array.isArray(portfolio.dt.pairs)')===true,'초기화 후 단타 상태 마이그레이션');
   els.depAmt={value:'100'};els.depDate={value:'2026-11-09'};els.depMemo={value:''};
   let err=null;try{run('addDeposit()');}catch(e){err=e;}
   ok(!err&&run('portfolio.deposits.length')===1,'초기화 후 입금 기록 추가 '+(err&&err.message));
   run(`window._restoreData={ver:'6.1',goalTargetsV1:true,goalTargetsV2:true,targets:{kr:20,us:35,bonds:5,gold:25,crypto:15},holdings:{kr_stocks:[],us:[]},txns:[],switching:{retail:[{ym:'2026-01',val:1}]}}`);
   run('_doRestoreConfirm()');
   ok(Array.isArray(run('portfolio.deposits')),'구버전 백업(입금 기록 없음) 복원 후 deposits 배열');
   ok(Array.isArray(run('portfolio.switching.ism'))&&run('portfolio.switching.retail.length')===1,'복원 시 없는 지표만 기본값, 있는 지표 유지');
   err=null;try{run('addDeposit()');}catch(e){err=e;}
   ok(!err,'복원 후 입금 기록 추가 '+(err&&err.message));
   ok(run('Array.isArray(portfolio.holdings.gold)&&Array.isArray(portfolio.holdings.watchlist)'),'복원 시 빠진 보유 목록 채움');}

  // 3. 통화 플래그 일관성: 원화로 지정한 해외주식 / 달러로 지정한 금 ETF
  {const {run,modal}=mk();
   run(`portfolio.exRate=1400;portfolio.holdings={kr_stocks:[],kr_etfs:[],us:[{id:'uk',name:'애플(원화)',ticker:'AAPL',qty:2,avg:300000,cur:350000,usd:false},{id:'uu',name:'MSFT',ticker:'MSFT',qty:1,avg:400,cur:500}],
     bonds:[{id:'bb',name:'BND',ticker:'BND',qty:1,avg:70,cur:72,usd:true}],gold:[{id:'gg',name:'GLD',code:'',qty:1,avg:200,cur:250,usd:true}],crypto:[],watchlist:[]}`);
   const c=run('calc()');
   ok(Math.abs(c.us-(2*350000+500*1400))<1,'원화 지정 해외주식은 환율 미적용, 달러 기본은 적용: '+c.us);
   ok(Math.abs(c.gold-250*1400)<1,'달러 지정 금은 환율 적용: '+c.gold);
   ok(Math.abs(c.bonds-72*1400)<1,'채권은 항상 USD');
   ok(Math.abs(c.cost-(2*300000+400*1400+70*1400+200*1400))<1,'원가도 같은 기준');
   ok(run("priceSpec('us',portfolio.holdings.us[0]).ccy")==='KRW'&&run("priceSpec('us',portfolio.holdings.us[1]).ccy")==='USD'&&run("priceSpec('gold',portfolio.holdings.gold[0]).ccy")==='USD','priceSpec = 카드 표시 통화');
   ok(Math.abs(run("entryValue({h:portfolio.holdings.us[0],cat:'us'})")-700000)<1,'entryValue 원화 지정 해외주식');
   ok(Math.abs(run("styleBuckets().us[0].ev")-700000)<1,'스타일 버킷도 같은 기준');
   ok(run("fromNative('us',portfolio.holdings.us[0],200,true)")===280000,'USD 시세 → 원화 지정 종목은 원화로 환산');
   ok(run("fromNative('us',portfolio.holdings.us[1],200,true)")===200,'USD 시세 → USD 종목 그대로');
   ok(Math.abs(run("fromNative('gold',portfolio.holdings.gold[0],14000,false)")-10)<1e-9,'원화 시세 → 달러 지정 종목은 달러로');
   run("showEditModal('us','uk')");
   ok(/id="eCurrency" value="KRW"/.test(modal.innerHTML),'수정 모달이 원화 지정 해외주식을 원화로 표시(저장 시 USD로 되돌아가지 않음)');
   run("showEditModal('us','uu')");
   ok(/id="eCurrency" value="USD"/.test(modal.innerHTML),'플래그 없는 해외주식은 USD');}

  // 4. 업비트 시세는 기존 객체에 직접 반영(객체 교체 X)
  {const {run}=mk();
   run(`portfolio.holdings.crypto=[{id:'c1',name:'BTC',upbit:'KRW-BTC',qty:1,avg:1,cur:1}];window.__o=portfolio.holdings.crypto[0];
        nativeGet=async(u)=>{window.__u=u;return[{market:'KRW-BTC',trade_price:123}];};`);
   const n=await run('updateCryptoPrices()');
   ok(n===1&&run('window.__o===portfolio.holdings.crypto[0]&&window.__o.cur===123'),'코인 시세 갱신 시 객체 유지');
   run(`portfolio.holdings.crypto=[];window.__u=null`);
   ok(await run('updateCryptoPrices()')===0&&run('window.__u')===null,'코인 없으면 요청 안 함');}

  // 5. 키움 주문 구분값: 0 보통(지정가) · 3 시장가
  {const {run,timers}=mk();
   run(`window.KiwoomBridge.placeOrder=function(mock,side,code,tp,qty,price,id){window.__k=[mock,side,code,tp,qty,price];window.KiwoomBridge.fetch=()=>'{"return_code":0,"ord_no":"0001"}';setTimeout(()=>window.KiwoomBridge._deliver(id),0);};`);
   const p1=run(`sendBrokerOrder('kiwoom','buy','005930',true,3,0)`);timers.splice(0).forEach(f=>f());
   ok(await p1==='0001'&&run('window.__k[3]')==='3','키움 시장가 trde_tp=3, got '+run('window.__k[3]'));
   const p2=run(`sendBrokerOrder('kiwoom','sell','005930',false,3,70000)`);timers.splice(0).forEach(f=>f());
   await p2;ok(run('window.__k[3]')==='0'&&run('window.__k[5]')==='70000','키움 지정가 trde_tp=0·가격 전달');}

  // 6. 늦게 온 브릿지 응답도 네이티브 맵에서 비움
  {const {run}=mk();
   run(`window.__f=[];window.HttpBridge.fetch=id=>{window.__f.push(id);return null;};window.HttpBridge._deliver('late1')`);
   ok(run('window.__f[0]')==='late1','타임아웃 뒤 응답도 fetch로 비움');}

  // 7. 가져오기 미리보기: 입력값 유지, 닫은 뒤 다시 열리지 않음
  {const {run,modal}=mk();
   run(`importDraft={rows:[{raw:'x',name:'새종목',entry:null,action:'new',qty:1,cur:2,avg:3,cat:'kr',code:'',resolved:false}],missing:[]};importSeq++;showImportPreview()`);
   ok(modal.innerHTML.includes('impRowEdit(0,\'qty\''),'수량 입력이 행 데이터에 바인딩됨');
   run(`impRowEdit(0,'qty','7')`);ok(run('importDraft.rows[0].qty')===7,'impRowEdit 반영');
   run('showImportPreview()');ok(run('importDraft.rows[0].qty')===7,'재렌더 후에도 입력값 유지');
   run('closeModal()');
   await run('resolveNewRows(importSeq)');
   ok(modal.innerHTML==='','취소로 닫은 미리보기가 자동 검색 후 다시 열리지 않음');}

  // 8. XSS: 로그·검색 결과 문자열 이스케이프
  {const {run,els}=mk();
   run(`logs=['<img src=x onerror=alert(1)>'];render()`);
   ok(!els.app._html.includes('<img src=x')&&els.app._html.includes('&lt;img'),'로그 이스케이프');}

  // 9. FRED 결측값('.')은 건너뜀
  {const {run}=mk();
   const o=run(`parseFredCsv('observation_date,X\\n2025-01-01,.\\n2025-02-01,123.4\\n')`);
   ok(!('2025-01' in o)&&o['2025-02']===123.4,'FRED 결측 제외: '+JSON.stringify(o));}

  // 10. 수정 모달: 수량 0 저장 가능
  {const {run,els}=mk();
   const id=run('portfolio.holdings.kr_stocks[0].id');
   els.eQty={value:'0'};els.eAvg={value:''};els.eCur={value:''};els.eCurrency={value:'KRW'};
   const avg0=run('portfolio.holdings.kr_stocks[0].avg');
   run(`saveEdit('kr','${id}')`);
   ok(run('portfolio.holdings.kr_stocks[0].qty')===0&&run('portfolio.holdings.kr_stocks[0].avg')===avg0,'수량 0 저장, 빈 칸은 기존 값 유지');}

  // 11. 종목 선택 시 직전 종목 정보 초기화
  {const {run,els}=mk();
   run(`searchResults=[{name:'A',code:'000001',type:'kr'}];selectedStockInfo={price:999,eps:1};fetchStockInfo=()=>new Promise(()=>{});`);
   els.selName={textContent:''};els.selCode={textContent:''};els.addForm={style:{},setAttribute(){},getAttribute(){return null;}};
   run('selectStock(0)');
   ok(JSON.stringify(run('selectedStockInfo'))==='{}','조회 중에는 직전 종목 정보를 쓰지 않음');}

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
