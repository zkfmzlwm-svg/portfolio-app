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
console.log(`smoke_import: ${pass} pass, ${fail} fail`);process.exit(fail?1:0);
