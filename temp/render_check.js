const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const pages={};
const mkEl=(name)=>({_n:name,style:{},_html:'',set innerHTML(v){this._html=v;pages[name]=v;},get innerHTML(){return this._html;},textContent:'',value:'',
  setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];}});
const els={};
const sandbox={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
 document:{getElementById(id){els[id]=els[id]||mkEl(id);return els[id];},addEventListener(){},querySelector(){return mkEl('q');},querySelectorAll(){return[];}},
 alert:()=>{},setTimeout:()=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const run=e=>vm.runInContext(e,sandbox);
let issues=0;
for(const t of['home','holdings','switching','rebal','analysis','settings']){
  run("tab='"+t+"';render()");
  const out=els.app._html;
  for(const bad of['undefined','NaN','function ','[object']){
    if(out.includes(bad)){console.log('✗',t,'contains',bad);issues++;}
  }
}
for(const ch of['kr','us','bonds','alts','watch']){run("catH='"+ch+"';render()");const out=els.app._html;
  for(const bad of['undefined','NaN']){if(out.includes(bad)){console.log('✗ holdings/'+ch,bad);issues++;}}}
// 모달들
run("showLedger()");run("closeModal()");
run("showTradeModal('kr','s4','buy')");
run("const b=showBackup()");
run("showSwitchUpdateModal()");
run("showAddModal('kr')");
run("showEditModal('kr','s1')");
const modal=els['modal-root']._html||'';
for(const bad of['undefined','NaN','[object']){if(modal.includes(bad)){console.log('✗ modal contains',bad);issues++;}}
// 리밸런싱 배분 카드 DOM 주입 확인
run("tab='rebal';render()");
// getElementById 스텁은 매번 같은 객체라 allocCards 내용 확인
console.log('allocCards filled?', (els['allocCards']&&els['allocCards']._html.includes('만원'))?'yes':'no');
if(!(els['allocCards']&&els['allocCards']._html.includes('만원')))issues++;
console.log(issues?issues+' issues':'ALL RENDERS CLEAN');
process.exit(issues?1:0);
