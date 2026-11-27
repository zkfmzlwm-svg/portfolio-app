// v7.9.1 보유종목 반영 회귀 테스트 — 구분자(| , 탭 공백) 파싱, 티커 trim, 렌더 시 입력 보존, 적용
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const els={},modal={innerHTML:''};
const mkEl=id=>({id,tagName:id==='importText'?'TEXTAREA':'DIV',style:{},_html:'',set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},textContent:'',value:'',
  setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},setSelectionRange(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];}});
const document={getElementById(id){if(id==='modal-root')return modal;
  if(/^imp(Apply|Q|C|A|Code)/.test(id)&&!modal.innerHTML.includes('id="'+id+'"'))return null;
  return els[id]=els[id]||mkEl(id);},addEventListener(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];},activeElement:null,documentElement:mkEl('root')};
const sb={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},document,
  alert:()=>{},confirm:()=>true,setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,clearInterval(){},
  fetch:()=>Promise.reject(new Error('offline')),Date,Math,JSON,isNaN,isFinite,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise};
vm.createContext(sb);vm.runInContext(code,sb);
const run=e=>vm.runInContext(e,sb);
let pass=0,fail=0;const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('✗ FAIL:',m);}};
(async()=>{
const P=t=>run(`parseSnapshotText(${JSON.stringify(t)}).rows.map(r=>({n:r.name,q:r.qty,c:r.cur,a:r.avg,cat:r.cat,code:r.code}))`);
for(const t of['JNJ | 2 | 22','JNJ|2|22','JNJ,2,22','JNJ, 2, 22','JNJ\t2\t22','JNJ 2 22',' JNJ  |  2  |  22 ','JNJ ｜ 2 ｜ 22','JNJ | 2주 | $22']){
  const r=P(t);ok(r.length===1&&r[0].n==='JNJ'&&r[0].q===2&&r[0].a===22,'"'+t+'" → '+JSON.stringify(r));
  ok(r[0]&&r[0].cat==='us'&&r[0].code==='JNJ','"'+t+'" us/JNJ');}
{const r=P('비트코인 | 0.07898433 | 89,952,000 | 122,291,612');ok(r.length===1&&r[0].cat==='crypto'&&r[0].q===0.07898433&&r[0].c===89952000&&r[0].a===122291612,'천단위+파이프 '+JSON.stringify(r));}
{const r=P('삼성전자 9 257,500 295,790');ok(r[0].n==='삼성전자'&&r[0].c===257500,'기존 공백 형식 유지 '+JSON.stringify(r));}
{const r=P('JNJ | 2 | 22\nAAPL | 3 | 180.5 | 150.25');ok(r.length===2&&r[1].n==='AAPL'&&r[1].q===3,'여러 줄 '+JSON.stringify(r));}
// 렌더 시 붙여넣은 텍스트 보존
run("tab='settings';render()");
run("importTextDraft='JNJ | 2 | 22'");run('render()');
ok(document.getElementById('app').innerHTML.includes('>JNJ | 2 | 22</textarea>'),'render 후 textarea 내용 유지');
// 적용 → 해외 보유에 JNJ로 추가
run(`document.getElementById('importText').value='JNJ | 2 | 22';parseHoldingsText();`);
const before=run('portfolio.holdings.us.length');
run('applyImport()');
const us=run('JSON.stringify(portfolio.holdings.us.slice(-1)[0])');
ok(run('portfolio.holdings.us.length')===before+1,'해외 보유 1건 추가');
ok(/"name":"JNJ"/.test(us)&&/"ticker":"JNJ"/.test(us)&&/"qty":2/.test(us),'JNJ 저장값 '+us);
// v7.9.1b 해외 종목이 국내로 반영되던 문제
{const r=P('aapl 3 180 150');ok(r[0].cat==='us'&&r[0].code==='AAPL'&&r[0].n==='AAPL','소문자 티커 → 해외 '+JSON.stringify(r));}
{const r=P('Johnson & Johnson | 2 | 22');ok(r[0].cat==='us','영문 이름 → 해외 '+JSON.stringify(r));}
{const r=P('ETH 0.5 4000000 3500000');ok(r[0].cat==='crypto','코인 심볼은 코인 '+JSON.stringify(r));}
// 짧은 티커가 국내 ETF 이름에 부분 매칭되지 않음 (KO ⊂ KODEX)
run("portfolio.holdings.kr_etfs.push({id:'tkx',name:'KODEX 200',code:'069500',qty:1,avg:1,cur:1,tags:[]})");
{const r=P('KO 5 60 55');ok(r[0].cat==='us'&&r[0].n==='KO','KO는 KODEX에 매칭 안 됨 '+JSON.stringify(r));}
// 예전 버전이 국내로 잘못 저장한 'JNJ |' → 해외로 이동
run("portfolio.holdings.us=portfolio.holdings.us.filter(h=>h.ticker!=='JNJ');portfolio.holdings.kr_stocks.push({id:'bad1',name:'JNJ |',code:'',qty:2,avg:22,cur:22,tags:[]})");
run(`document.getElementById('importText').value='JNJ | 2 | 23 | 22';parseHoldingsText();`);
ok(run("importDraft.rows[0].moveTo")==='us','잘못 저장된 국내 JNJ → 이동 표시');
run('applyImport()');
ok(!run("portfolio.holdings.kr_stocks.some(h=>h.id==='bad1')"),'국내 목록에서 제거');
const mv=run("JSON.stringify(portfolio.holdings.us.find(h=>h.id==='bad1'))");
ok(/"name":"JNJ"/.test(mv)&&/"ticker":"JNJ"/.test(mv)&&/"usd":true/.test(mv)&&!/"code"/.test(mv),'해외로 이동(id 유지) '+mv);
// 네이버 결과에 국내 ETF가 먼저 와도 이름이 정확한 해외 종목 선택
await run(`searchCoin=async()=>[];searchNaver=async q=>[{type:'kr',code:'123456',name:'TIGER 미국테슬라채권혼합',market:'ETF'},{type:'us',code:'TSLA.O',ticker:'TSLA',name:'테슬라',market:'NASDAQ'}];
  importDraft={rows:[{name:'테슬라',action:'new',cat:'kr',code:''}],missing:[]};resolveNewRows(-1)`);
ok(run('importDraft.rows[0].cat')==='us'&&run('importDraft.rows[0].code')==='TSLA','테슬라 → 해외 TSLA '+run('JSON.stringify(importDraft.rows[0])'));
await run(`searchNaver=async q=>[{type:'kr',code:'005930',name:'삼성전자',market:'KOSPI'}];importDraft={rows:[{name:'삼성전자',action:'new',cat:'kr',code:''}],missing:[]};resolveNewRows(-1)`);
ok(run('importDraft.rows[0].cat')==='kr'&&run('importDraft.rows[0].code')==='005930','국내 종목은 국내');
console.log(`smoke_import: ${pass} pass, ${fail} fail`);process.exit(fail?1:0);
})();
