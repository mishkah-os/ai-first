"""
MAS Core V2 admin dashboard.

The admin UI is intentionally a thin shell: project state, preview links,
domains, syntax checks, and AI context packets are all loaded through protocol
endpoints rather than baked into static HTML.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["Dashboard UI"])


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI-First Platform</title>
<script src="/core-assets/mas.core.v2.js"></script>
<link rel="stylesheet" href="/admin/style.css">
</head>
<body><div id="app"></div><script src="/admin/app.js"></script></body>
</html>"""


@router.get("/admin/style.css")
async def admin_style():
    return Response(ADMIN_CSS, media_type="text/css")


@router.get("/admin/app.js")
async def admin_app():
    return Response(ADMIN_JS, media_type="application/javascript")


ADMIN_CSS = r"""
:root{--bg:#f5f7fb;--panel:#fff;--ink:#161923;--muted:#667085;--line:#d9dee9;--soft:#edf1f7;--brand:#0f766e;--blue:#2563eb;--bad:#dc2626;--ok:#16a34a;--warn:#d97706;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 Inter,system-ui,-apple-system,sans-serif}button,input,select,textarea{font:inherit}button{cursor:pointer}
.shell{display:grid;grid-template-columns:260px minmax(0,1fr);height:100vh}.side{background:#111827;color:#d1d5db;padding:16px;display:flex;flex-direction:column;gap:12px}.brand{font-weight:800;color:#fff;font-size:18px}.sub{font-size:12px;color:#9ca3af}.nav{display:grid;gap:4px;margin-top:12px}.nav button{border:0;background:transparent;color:#d1d5db;text-align:left;padding:10px;border-radius:7px}.nav button.active,.nav button:hover{background:#1f2937;color:#fff}
.main{min-width:0;overflow:auto}.top{height:58px;background:rgba(255,255,255,.9);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 22px;position:sticky;top:0;z-index:2;backdrop-filter:blur(12px)}.top h1{font-size:18px;margin:0}.content{padding:22px}
.grid{display:grid;gap:14px}.cols2{grid-template-columns:minmax(0,1fr) minmax(360px,.7fr)}.cols3{grid-template-columns:repeat(3,minmax(0,1fr))}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:15px}.card h2,.card h3{margin:0 0 10px}.card h2{font-size:16px}.card h3{font-size:14px}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.stat{background:#fff;border:1px solid var(--line);border-radius:8px;padding:13px}.stat b{display:block;font-size:22px}.stat span{font-size:12px;color:var(--muted)}
.btn{border:1px solid var(--line);background:#fff;color:var(--ink);padding:8px 11px;border-radius:7px;font-weight:650}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.blue{background:var(--blue);border-color:var(--blue);color:#fff}.btn.danger{background:#fff1f2;border-color:#fecdd3;color:var(--bad)}.btn.ghost{background:transparent}.btn:disabled{opacity:.55;cursor:not-allowed}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.field{display:grid;gap:5px;margin-bottom:10px}.field label{font-size:12px;color:var(--muted);font-weight:650}.field input,.field select,.field textarea{width:100%;border:1px solid var(--line);background:#fff;border-radius:7px;padding:9px;color:var(--ink)}.field textarea{min-height:86px;resize:vertical}
.project{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:8px;align-items:center;border-bottom:1px solid var(--line);padding:9px 0}.project:last-child{border-bottom:0}.muted{color:var(--muted);font-size:12px}.badge{display:inline-flex;border-radius:999px;padding:2px 7px;font-size:11px;background:var(--soft);color:var(--muted)}.badge.ok{background:#dcfce7;color:var(--ok)}.badge.bad{background:#fee2e2;color:var(--bad)}.badge.warn{background:#fef3c7;color:var(--warn)}
.tree{max-height:55vh;overflow:auto}.mod{margin:10px 0}.mod-title{font-weight:800;font-size:12px;color:var(--muted);text-transform:uppercase}.comp{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:7px;align-items:center;padding:7px;border-radius:7px}.comp:hover{background:var(--soft)}.code-tabs{display:flex;gap:6px;margin-bottom:8px}.editor{width:100%;height:48vh;border:1px solid var(--line);border-radius:8px;padding:12px;background:#0b1020;color:#dbeafe;font:12px/1.5 var(--mono);resize:vertical}.pre{white-space:pre-wrap;background:#0b1020;color:#dbeafe;border-radius:8px;padding:12px;font:12px/1.5 var(--mono);overflow:auto;max-height:52vh}.links a{display:inline-flex;margin:3px 5px 3px 0;color:var(--blue);text-decoration:none}
.vibe{display:grid;grid-template-columns:minmax(310px,.36fr) minmax(0,1fr);gap:14px}.vibe-tree{max-height:calc(100vh - 220px);overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}.tree-node{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:7px;align-items:center;padding:7px 8px;border-bottom:1px solid #edf1f7}.tree-node:hover{background:#f8fafc}.tree-node .title{font-weight:750}.tree-node .tiny{font-size:11px;color:var(--muted)}.bang{border:1px solid #fbbf24;background:#fffbeb;color:#92400e;border-radius:999px;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-weight:800}.prompt-box{min-height:130px}.raw-prompt{max-height:42vh}.bulk-row{border:1px solid var(--line);border-radius:8px;margin:8px 0;padding:10px;background:#fff}.bulk-row h3{display:flex;justify-content:space-between;gap:8px;margin:0 0 8px;font-size:13px}.test-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;border-bottom:1px solid var(--line);padding:8px 0}
.tree-toggle{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:5px;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-weight:800}.tree-node{grid-template-columns:22px 22px minmax(0,1fr) auto}.vibe-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.vibe-tabs button{border:1px solid var(--line);background:#fff;border-radius:7px;padding:8px 10px;font-weight:650}.vibe-tabs button.active{background:#ecfdf5;border-color:#99f6e4;color:#0f766e}.edit-grid{display:grid;grid-template-columns:260px minmax(0,1fr);gap:10px}.edit-list{border:1px solid var(--line);border-radius:8px;overflow:auto;max-height:58vh;background:#fff}.edit-list button{display:block;width:100%;border:0;border-bottom:1px solid #edf1f7;background:#fff;text-align:left;padding:9px;color:var(--ink)}.edit-list button.active{background:#eff6ff;color:#1d4ed8;font-weight:750}.edit-area{width:100%;min-height:45vh;border:1px solid var(--line);border-radius:8px;padding:10px;font:12px/1.5 var(--mono);resize:vertical}.modal-backdrop{position:fixed;inset:0;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;padding:18px;z-index:20}.modal{background:#fff;border-radius:8px;border:1px solid var(--line);width:min(920px,100%);max-height:86vh;overflow:auto;padding:18px}.modal h2{margin:0 0 10px}.md-body h1,.md-body h2,.md-body h3{margin:14px 0 8px}.md-body p{line-height:1.6}.md-body code{font-family:var(--mono);background:#eef2f7;padding:1px 4px;border-radius:4px}.md-body pre{white-space:pre-wrap;background:#101827;color:#dbeafe;border-radius:8px;padding:12px}
@media(max-width:980px){.shell{grid-template-columns:1fr}.side{position:static}.cols2,.cols3,.stats{grid-template-columns:1fr}.top{position:static}}
@media(max-width:1100px){.vibe{grid-template-columns:1fr}.vibe-tree{max-height:52vh}}
"""


ADMIN_JS = r"""
const {D, app} = MAS;

const api = async (path, opts={}) => {
  const res = await fetch(path, Object.assign({headers:{'Content-Type':'application/json'}}, opts));
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};
const post = (path, body) => api(path, {method:'POST', body:JSON.stringify(body||{})});

const state = {
  page:'overview', loading:true, error:'', projects:[], domains:{base_domains:[],hosts:[]},
  deps:{checks:[]}, tasks:[], pages:{}, runtimeHealth:{}, selectedProject:'mas-erp', selected:{}, codeMode:'mini',
  activeCode:'', activeComponent:null, activeBulk:'main', context:null, syntax:null,
  taskTitle:'', taskPrompt:'',
  protocolTree:{projects:[]}, protocolTests:{tests:[],auth_scripts:[]}, treeSelected:{}, treeOpen:{}, treeSearch:'', bulkSearch:'',
  vibeMode:'mini', vibeMaxChars:80000, vibePrompt:'', executionMode:'planner', agentSlug:'quantum-core',
  promptPacket:null, plannerRun:null, nodeMd:null, lastTestRun:null, vibeTab:'prompt', infoModal:false,
  editableBulks:[], editStatus:'', selectedEditIndex:0, instructions:[], selectedInstruction:'', instructionStatus:'',
  form:{name:'',slug:'',description:'',base_domain:'ai-auto.cloud',subdomain:'',port:'',service_type:'node',docs_en_md:'',docs_ar_md:''}
};

async function loadAll(ctx){
  ctx.set({loading:true,error:''});
  try{
    const [projects, domains, deps, tasks] = await Promise.all([
      api('/api/platform/projects'),
      api('/api/platform/domains'),
      api('/api/platform/health/dependencies'),
      api('/api/platform/tasks?limit=30')
    ]);
    const pagePairs = await Promise.all((projects||[]).map(async p=>{
      try{return [p.slug,(await api(`/api/platform/projects/${p.slug}/pages`)).pages||[]];}
      catch(e){return [p.slug,[]];}
    }));
    const pages={}; pagePairs.forEach(([slug,items])=>pages[slug]=items);
    const healthPairs = await Promise.all((projects||[]).map(async p=>{
      try{return [p.slug,(await api(`/api/platform/projects/${p.slug}/runtime-health`)).health||{}];}
      catch(e){return [p.slug,{ok:false,health_error:e.message}];}
    }));
    const runtimeHealth={}; healthPairs.forEach(([slug,item])=>runtimeHealth[slug]=item);
    const current=(ctx.db || (ctx.getState?ctx.getState():{}) || {});
    const preferred=(projects||[]).some(p=>p.slug==='mas-erp')?'mas-erp':((projects||[]).some(p=>p.slug==='mostamal-hawaa')?'mostamal-hawaa':((projects[0]||{}).slug));
    const selectedProject=(current.selectedProject&&(projects||[]).some(p=>p.slug===current.selectedProject))?current.selectedProject:preferred;
    ctx.set({projects, domains, deps, tasks:tasks.tasks||[], pages, runtimeHealth, selectedProject, loading:false});
    await loadProtocol(ctx, selectedProject);
  }catch(e){ctx.set({error:e.message,loading:false});}
}

async function loadProtocol(ctx, project){
  if(!project) return;
  try{
    const [tree, tests] = await Promise.all([
      api(`/api/platform/projects/${project}/protocol-tree`),
      api(`/api/platform/projects/${project}/tests`).catch(()=>({tests:[],auth_scripts:[]}))
    ]);
    ctx.set({protocolTree:tree, protocolTests:tests});
  }catch(e){ctx.set({error:e.message});}
}

function stat(label, value){return D.div({class:'stat'},[D.b(String(value||0)),D.span(label)]);}
function selectedList(db){
  const out=[];
  Object.keys(db.selected||{}).forEach(k=>{if(db.selected[k]){
    if(k.includes('::page::')){const [project,page]=k.split('::page::'); out.push({project,page});}
    else {const [project,component]=k.split('/'); out.push({project,component});}
  }});
  return out;
}
function selectedCount(db){return selectedList(db).length;}
function currentProject(db){return db.projects.find(p=>p.slug===db.selectedProject)||db.projects[0];}
function walk(nodes, fn){
  (nodes||[]).forEach(n=>{fn(n); walk(n.children||[], fn);});
}
function findNode(db,id){
  let found=null; walk((db.protocolTree.projects||[]), n=>{if(n.id===id) found=n;}); return found;
}
function markNode(selected,node,value){
  selected[node.id]=value;
  (node.children||[]).forEach(child=>markNode(selected,child,value));
}
function protocolSelection(db){
  const out=[];
  walk((db.protocolTree.projects||[]), n=>{if(db.treeSelected[n.id]&&n.select) out.push(n.select);});
  return out;
}
function downloadText(filename,text){
  const blob=new Blob([text||''],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),800);
}
function escapeHtml(text){return String(text||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function mdToHtml(md){
  const lines=String(md||'').split('\n');
  let inCode=false,out=[];
  lines.forEach(raw=>{
    if(raw.trim().startsWith('```')){inCode=!inCode; out.push(inCode?'<pre><code>':'</code></pre>'); return;}
    if(inCode){out.push(escapeHtml(raw)+'\n'); return;}
    const line=escapeHtml(raw);
    if(/^###\s+/.test(raw)) out.push('<h3>'+line.replace(/^###\s+/,'')+'</h3>');
    else if(/^##\s+/.test(raw)) out.push('<h2>'+line.replace(/^##\s+/,'')+'</h2>');
    else if(/^#\s+/.test(raw)) out.push('<h1>'+line.replace(/^#\s+/,'')+'</h1>');
    else if(/^\s*-\s+/.test(raw)) out.push('<p>• '+line.replace(/^\s*-\s+/,'')+'</p>');
    else if(line.trim()) out.push('<p>'+line+'</p>');
  });
  return out.join('');
}
function vibeHelpMd(){
  return `# AI-First Vibe Coding

## English
1. Pick a project, page, module, component, or exact bulk from the tree.
2. Parent selection selects all children. Use +/- to collapse or expand.
3. Use mini mode for planning, full mode for exact patching.
4. Search can filter names, classifications, and code content.
5. Dry Prompt shows the exact raw prompt sent to the planner.
6. Edit Bulks lets a human patch selected source bulks and save them back into QDML.
7. Instructions edits the classification/system guidance used by planner and specialist agents.

## العربية
اختر من الشجرة على مستوى المشروع أو الصفحة أو الموديول أو المكون أو bulk محدد.
اختيار الأب يختار أبناءه. استخدم + و - للطي والفرد.
زر Dry Prompt يعرض النص الخام قبل إرساله للذكاء.
تبويب Edit Bulks يسمح بتعديل الكود بشرياً وحفظه.
تبويب Instructions يحرر تعليمات التصنيف والوكلاء.

## Protocol
MCP here means Model Context Protocol at the project level: selected tree nodes, docs, mini/full code, tests, service health, and tool contracts.
A2A means Planner to Agent assignments: planner receives the request first, removes noise, then assigns micro tasks to mas-ui, mas-store, backend-api, postgres, quantum-core, or qa-browser.`;
}
function packetText(packet, mode){
  if(!packet) return '';
  if(mode==='raw') return packet.raw_prompt||'';
  return ((packet.code_context&&packet.code_context.items)||[]).map(i=>`# ${i.label}\n${i.content}`).join('\n\n');
}
function editableFromPacket(packet){
  const seen={};
  return ((packet&&packet.code_context&&packet.code_context.items)||[]).filter(item=>{
    if(!item.project||!item.component||!item.bulk) return false;
    const key=`${item.project}/${item.component}/${item.bulk}`;
    if(seen[key]) return false; seen[key]=true; return true;
  });
}

const orders = {
  init:{on:'click',do:(e,$)=>loadAll($)},
  nav:{on:'click',do:(e,$)=>$.set({page:e.target.dataset.page})},
  refresh:{on:'click',do:(e,$)=>loadAll($)},
  input:{on:['input','change'],do:(e,$)=>{
    const form=Object.assign({},$.db.form); form[e.target.name]=e.target.value; $.set({form});
  }},
  taskInput:{on:['input','change'],do:(e,$)=>{
    const u={}; u[e.target.name]=e.target.value; $.set(u);
  }},
  vibeInput:{on:['input','change'],do:(e,$)=>{
    const u={}; u[e.target.name]=e.target.value; $.set(u);
  }},
  saveProject:{on:'click',do:async(e,$)=>{
    const f=$.db.form; if(!f.name&&!f.slug) return;
    const project=await post('/api/platform/projects', f);
    await loadAll($);
    $.set({selectedProject:project.project.slug, form:Object.assign({}, state.form)});
  }},
  chooseProject:{on:'click',do:async(e,$)=>{
    const project=e.target.closest('[data-project]').dataset.project;
    $.set({selectedProject:project, activeCode:'', activeComponent:null, treeSelected:{}, treeOpen:{}, promptPacket:null, plannerRun:null, nodeMd:null, editableBulks:[], editStatus:''});
    await loadProtocol($, project);
  }},
  toggleComp:{on:'change',do:(e,$)=>{
    const selected=Object.assign({},$.db.selected); selected[e.target.value]=e.target.checked; $.set({selected});
  }},
  toggleNode:{on:'change',do:(e,$)=>{
    const node=findNode($.db,e.target.dataset.node); if(!node) return;
    const selected=Object.assign({},$.db.treeSelected||{});
    markNode(selected,node,e.target.checked);
    $.set({treeSelected:selected});
  }},
  toggleTreeOpen:{on:'click',do:(e,$)=>{
    const id=e.target.closest('[data-node]').dataset.node;
    const open=Object.assign({},$.db.treeOpen||{});
    open[id]=!(open[id]!==false);
    $.set({treeOpen:open});
  }},
  vibeTab:{on:'click',do:(e,$)=>$.set({vibeTab:e.target.dataset.tab})},
  openVibeInfo:{on:'click',do:(e,$)=>$.set({infoModal:true})},
  closeVibeInfo:{on:'click',do:(e,$)=>$.set({infoModal:false})},
  downloadPacket:{on:'click',do:(e,$)=>{
    const mode=e.target.dataset.mode||'raw';
    const project=($.db.protocolTree.projects&&$.db.protocolTree.projects[0]&&$.db.protocolTree.projects[0].slug)||'selection';
    downloadText(`${project}-${mode}.txt`, packetText($.db.promptPacket, mode));
  }},
  loadEditableBulks:{on:'click',do:async(e,$)=>{
    const refs=editableFromPacket($.db.promptPacket);
    const editable=[];
    for(const item of refs){
      const base=`/api/platform/projects/${encodeURIComponent(item.project)}/components/${encodeURIComponent(item.component)}/bulks/${encodeURIComponent(item.bulk)}`;
      const [bulk,meta]=await Promise.all([api(base),api(base+'/meta').catch(()=>({meta:{}}))]);
      editable.push({project:item.project,component:item.component,bulk:item.bulk,label:item.label,content:(bulk.data&&bulk.data.content)||'',meta:meta.meta||{},metaText:JSON.stringify(meta.meta||{},null,2),dirty:false});
    }
    $.set({editableBulks:editable,selectedEditIndex:0,editStatus:`loaded ${editable.length} bulks`,vibeTab:'edit'});
  }},
  selectEditBulk:{on:'click',do:(e,$)=>$.set({selectedEditIndex:Number(e.target.dataset.index||0),editStatus:''})},
  editBulkContent:{on:'input',do:(e,$)=>{
    const list=($.db.editableBulks||[]).slice(); const idx=$.db.selectedEditIndex||0;
    if(!list[idx]) return; list[idx]=Object.assign({},list[idx],{content:e.target.value,dirty:true});
    $.set({editableBulks:list,editStatus:'unsaved code'});
  }},
  editBulkMeta:{on:'input',do:(e,$)=>{
    const list=($.db.editableBulks||[]).slice(); const idx=$.db.selectedEditIndex||0;
    if(!list[idx]) return; list[idx]=Object.assign({},list[idx],{metaText:e.target.value,dirty:true});
    $.set({editableBulks:list,editStatus:'unsaved metadata'});
  }},
  saveEditableBulk:{on:'click',do:async(e,$)=>{
    const list=($.db.editableBulks||[]).slice(); const idx=$.db.selectedEditIndex||0; const item=list[idx];
    if(!item) return;
    const base=`/api/platform/projects/${encodeURIComponent(item.project)}/components/${encodeURIComponent(item.component)}/bulks/${encodeURIComponent(item.bulk)}`;
    let meta={};
    try{meta=JSON.parse(item.metaText||'{}');}catch(err){$.set({editStatus:'metadata JSON error: '+err.message});return;}
    await post(base,{content:item.content,changed_by:'human',reason:'vibe editable bulk'});
    await post(base+'/meta',meta);
    list[idx]=Object.assign({},item,{dirty:false,meta,metaText:JSON.stringify(meta,null,2)});
    $.set({editableBulks:list,editStatus:`saved ${item.label}`});
  }},
  loadInstructions:{on:'click',do:async(e,$)=>{
    const res=await api('/api/platform/instructions');
    $.set({instructions:res.instructions||[],selectedInstruction:((res.instructions||[])[0]||{}).id||'',instructionStatus:'loaded',vibeTab:'instructions'});
  }},
  selectInstruction:{on:'click',do:(e,$)=>$.set({selectedInstruction:e.target.dataset.id,instructionStatus:''})},
  instructionInput:{on:'input',do:(e,$)=>{
    const list=($.db.instructions||[]).slice(); const idx=list.findIndex(x=>String(x.id)===String($.db.selectedInstruction));
    if(idx<0) return; list[idx]=Object.assign({},list[idx],{[e.target.name]:e.target.value});
    $.set({instructions:list,instructionStatus:'unsaved'});
  }},
  saveInstruction:{on:'click',do:async(e,$)=>{
    const item=($.db.instructions||[]).find(x=>String(x.id)===String($.db.selectedInstruction));
    if(!item) return;
    const res=await post('/api/platform/instructions',item);
    const list=($.db.instructions||[]).map(x=>String(x.id)===String(res.instruction.id)?res.instruction:x);
    $.set({instructions:list,instructionStatus:'saved'});
  }},
  selectAllProject:{on:'click',do:(e,$)=>{
    const root=($.db.protocolTree.projects||[])[0]; if(!root) return;
    const selected={}; markNode(selected,root,true); $.set({treeSelected:selected});
  }},
  clearTreeSelection:{on:'click',do:(e,$)=>$.set({treeSelected:{},promptPacket:null,nodeMd:null})},
  showNodeMd:{on:'click',do:(e,$)=>{
    const node=findNode($.db,e.target.closest('[data-node]').dataset.node); if(node) $.set({nodeMd:node});
  }},
  dryPrompt:{on:'click',do:async(e,$)=>{
    const packet=await post('/api/platform/prompt-packet',{
      selection:protocolSelection($.db),
      mode:$.db.vibeMode||'mini',
      max_chars:Number($.db.vibeMaxChars||80000),
      content_query:$.db.bulkSearch||'',
      prompt:$.db.vibePrompt||'',
      execution_mode:$.db.executionMode||'planner',
      agent_slug:$.db.agentSlug||'quantum-core'
    });
    $.set({promptPacket:packet});
  }},
  simulatePlanner:{on:'click',do:async(e,$)=>{
    const run=await post('/api/platform/planner/simulate',{
      selection:protocolSelection($.db),
      mode:$.db.vibeMode||'mini',
      max_chars:Number($.db.vibeMaxChars||80000),
      content_query:$.db.bulkSearch||'',
      prompt:$.db.vibePrompt||'',
      execution_mode:$.db.executionMode||'planner',
      agent_slug:$.db.agentSlug||'quantum-core'
    });
    $.set({plannerRun:run,promptPacket:run.prompt_packet});
  }},
  runProtocolTest:{on:'click',do:async(e,$)=>{
    const id=e.target.closest('[data-test]').dataset.test;
    const run=await post('/api/platform/tests/run',{test_id:id});
    $.set({lastTestRun:run});
  }},
  ensurePages:{on:'click',do:async(e,$)=>{
    const p=currentProject($.db); if(!p) return;
    await post(`/api/platform/projects/${p.slug}/ensure-page-links`,{});
    await loadAll($);
  }},
  openCode:{on:'click',do:async(e,$)=>{
    const el=e.target.closest('[data-component]'); const project=el.dataset.project; const component=el.dataset.component;
    const mode=el.dataset.mode||$.db.codeMode||'mini';
    const res=await api(`/api/platform/projects/${project}/components/${component}/code?mode=${mode}`);
    $.set({activeCode:res.code, activeComponent:{project,component,bulks:res.bulks}, codeMode:mode, activeBulk:(res.bulks[0]&&res.bulks[0].name)||'main'});
  }},
  codeMode:{on:'click',do:async(e,$)=>{
    if(!$.db.activeComponent) return;
    const mode=e.target.dataset.mode;
    const {project,component}= $.db.activeComponent;
    const res=await api(`/api/platform/projects/${project}/components/${component}/code?mode=${mode}`);
    $.set({activeCode:res.code, codeMode:mode});
  }},
  bulkSelect:{on:['change','click'],do:async(e,$)=>{
    if(!$.db.activeComponent) return;
    const bulk=e.target.value || $.db.activeBulk;
    const {project,component}= $.db.activeComponent;
    const res=await api(`/api/platform/projects/${project}/components/${component}/bulks/${bulk}`);
    $.set({activeBulk:bulk, activeCode:res.data.content||'', codeMode:'bulk'});
  }},
  editCode:{on:'input',do:(e,$)=>$.set({activeCode:e.target.value})},
  saveCode:{on:'click',do:async(e,$)=>{
    if(!$.db.activeComponent || $.db.codeMode!=='bulk') return;
    const {project,component}= $.db.activeComponent;
    await post(`/api/platform/projects/${project}/components/${component}/bulks/${$.db.activeBulk}`, {content:$.db.activeCode, reason:'human edit from admin'});
    const res=await api(`/api/platform/projects/${project}/components/${component}/code?mode=full`);
    $.set({activeCode:res.code, codeMode:'full'});
  }},
  context:{on:'click',do:async(e,$)=>{
    const selection=selectedList($.db);
    const res=await post('/api/platform/context',{selection,mode:$.db.codeMode,max_chars:60000});
    $.set({context:res,page:'context'});
  }},
  createTask:{on:'click',do:async(e,$)=>{
    const p=currentProject($.db); if(!p) return;
    const selection=selectedList($.db);
    const res=await post('/api/platform/tasks',{project:p.slug,title:$.db.taskTitle||'AI task',prompt:$.db.taskPrompt||'Study selected context and propose the next code action.',selection,mode:$.db.codeMode,max_chars:60000});
    const tasks=(await api('/api/platform/tasks?limit=30')).tasks||[];
    $.set({tasks,context:res.context,page:'tasks'});
  }},
  syntax:{on:'click',do:async(e,$)=>{
    const p=currentProject($.db); if(!p) return;
    const res=await post(`/api/platform/syntax/${p.slug}`,{});
    $.set({syntax:res,page:'syntax'});
  }},
  ensureLinks:{on:'click',do:async(e,$)=>{
    const p=currentProject($.db); if(!p) return;
    await post(`/api/platform/projects/${p.slug}/ensure-preview-links`,{});
    await loadAll($);
  }},
  normalize:{on:'click',do:async(e,$)=>{
    const p=currentProject($.db); if(!p) return;
    await post(`/api/platform/normalize/${p.slug}`,{});
    await loadAll($);
  }}
};

function Overview(db){
  const totals={projects:db.projects.length,pages:0,modules:0,components:0,bulks:0,lines:0};
  Object.values(db.pages||{}).forEach(items=>totals.pages+=(items||[]).length);
  db.projects.forEach(p=>(p.modules||[]).forEach(m=>{totals.modules++;(m.components||[]).forEach(c=>{totals.components++;totals.bulks+=c.bulks||0;totals.lines+=c.lines||0;});}));
  return D.div({class:'grid'},[
    D.div({class:'stats'},[stat('Projects',totals.projects),stat('Pages',totals.pages),stat('Modules',totals.modules),stat('Components',totals.components),stat('Lines',totals.lines)]),
    D.div({class:'grid cols2'},[
      D.section({class:'card'},[D.h2('Project Runtime Profiles'),ProjectList(db)]),
      D.section({class:'card'},[D.h2('Create / Update Project'),ProjectForm(db)])
    ])
  ]);
}

function ProjectList(db){
  return D.div((db.projects||[]).map(p=>{
    const health=(db.runtimeHealth&&db.runtimeHealth[p.slug])||{};
    return D.div({class:'project','data-project':p.slug},[
    D.input({type:'radio',name:'project',checked:p.slug===db.selectedProject,gkey:'chooseProject'}),
    D.div([D.strong(p.name),D.div({class:'muted'},`${p.slug} | ${p.subdomain||'no domain'} | ${p.port||'no port'} | ${health.systemd_status||health.health_error||''}`),D.div({class:'links'},[
      D.a({href:`/api/platform/projects/${p.slug}/inventory`,target:'_blank'},'inventory'),
      D.a({href:p.test_url||`/preview/${p.slug}/${((p.modules[0]||{}).components||[])[0]?.slug||''}`,target:'_blank'},'runtime'),
      D.a({href:`/api/platform/projects/${p.slug}/runtime-health`,target:'_blank'},'health'),
      ...((db.pages[p.slug]||[]).slice(0,4).map(pg=>D.a({href:pg.url,target:'_blank'},pg.slug)))
    ])]),
    D.span({class:'badge '+(health.ok?'ok':'bad')},health.ok?'live':'service down')
  ]);
  }));
}

function ProjectForm(db){
  const domains=db.domains.base_domains||[];
  return D.div([
    D.div({class:'grid cols2'},[
      field('Name',D.input({name:'name',value:db.form.name,gkey:'input',placeholder:'Mostamal Hawaa'})),
      field('Slug',D.input({name:'slug',value:db.form.slug,gkey:'input',placeholder:'mostamal-hawaa'}))
    ]),
    field('Description',D.textarea({name:'description',gkey:'input',value:db.form.description,placeholder:'What this project really is'})),
    D.div({class:'grid cols3'},[
      field('Base domain',D.select({name:'base_domain',gkey:'input',value:db.form.base_domain},domains.map(d=>D.option({value:d,selected:d===db.form.base_domain},d)))),
      field('Subdomain',D.input({name:'subdomain',gkey:'input',value:db.form.subdomain,placeholder:'project.ai-auto.cloud'})),
      field('Port',D.input({name:'port',gkey:'input',value:db.form.port,placeholder:'9001'}))
    ]),
    field('Service type',D.select({name:'service_type',gkey:'input',value:db.form.service_type},['node','python','docker','static'].map(x=>D.option({value:x,selected:x===db.form.service_type},x)))),
    field('Docs EN',D.textarea({name:'docs_en_md',gkey:'input',value:db.form.docs_en_md,placeholder:'# Project\nReal architecture, modules, services, tests'})),
    field('Docs AR',D.textarea({name:'docs_ar_md',gkey:'input',value:db.form.docs_ar_md,placeholder:'# المشروع\nشرح عربي كامل'})),
    D.button({class:'btn primary',gkey:'saveProject'},'Save Project Profile')
  ]);
}
function field(label,node){return D.label({class:'field'},[D.span(label),node]);}

function TreePage(db){
  const p=currentProject(db);
  if(!p) return D.div({class:'card'},'No project selected');
  return D.div({class:'grid cols2'},[
    D.section({class:'card'},[
      D.div({class:'row'},[D.h2(`${p.name} Tree`),D.span({class:'badge'},`${selectedCount(db)} selected`),D.button({class:'btn',gkey:'ensurePages'},'Ensure page links'),D.button({class:'btn',gkey:'ensureLinks'},'Ensure component links'),D.button({class:'btn',gkey:'normalize'},'Normalize fences'),D.button({class:'btn blue',gkey:'context'},'Build AI context'),D.button({class:'btn',gkey:'syntax'},'Syntax check')]),
      PageLinks(db,p),
      D.div({class:'tree'},(p.modules||[]).map(m=>D.div({class:'mod'},[
        D.div({class:'mod-title'},`${m.tier} / ${m.slug}`),
        ...(m.components||[]).map(c=>D.div({class:'comp'},[
          D.input({type:'checkbox',value:`${p.slug}/${c.slug}`,checked:!!db.selected[`${p.slug}/${c.slug}`],gkey:'toggleComp'}),
          D.div([D.strong(c.slug),D.div({class:'muted'},`${c.kind} | ${c.target} | ${c.bulks} bulks | ${c.lines} lines`)]),
          D.div({class:'row'},[
            D.a({class:'btn',href:c.preview_url,target:'_blank'},'Preview'),
            D.button({class:'btn','data-project':p.slug,'data-component':c.slug,'data-mode':'mini',gkey:'openCode'},'Mini'),
            D.button({class:'btn','data-project':p.slug,'data-component':c.slug,'data-mode':'full',gkey:'openCode'},'Full')
          ])
        ]))
      ])))
    ]),
    CodePanel(db)
  ]);
}

function PageLinks(db,p){
  const pages=(db.pages&&db.pages[p.slug])||[];
  if(!pages.length) return D.div({class:'card'},[D.h3('Pages'),D.p({class:'muted'},'No page routes registered for this project yet.')]);
  return D.div({class:'mod'},[
    D.div({class:'mod-title'},'pages / full screen previews'),
    ...pages.map(pg=>D.div({class:'comp'},[
      D.input({type:'checkbox',value:`${p.slug}::page::${pg.slug}`,checked:!!db.selected[`${p.slug}::page::${pg.slug}`],gkey:'toggleComp'}),
      D.div([D.strong(pg.title||pg.slug),D.div({class:'muted'},`${pg.route_path} | ${pg.subdomain}`)]),
      D.div({class:'row'},[D.a({class:'btn',href:pg.url,target:'_blank'},'Open page'),D.a({class:'btn',href:pg.runtime_url,target:'_blank'},'Runtime')])
    ]))
  ]);
}

function CodePanel(db){
  if(!db.activeComponent) return D.section({class:'card'},[D.h2('Code'),D.p({class:'muted'},'Open a component to inspect mini/full code and edit a bulk.')]);
  return D.section({class:'card'},[
    D.h2(`${db.activeComponent.project}/${db.activeComponent.component}`),
    D.div({class:'code-tabs'},[
      D.button({class:'btn '+(db.codeMode==='mini'?'primary':''),'data-mode':'mini',gkey:'codeMode'},'Mini code'),
      D.button({class:'btn '+(db.codeMode==='full'?'primary':''),'data-mode':'full',gkey:'codeMode'},'Full code'),
      D.button({class:'btn '+(db.codeMode==='bulk'?'primary':''),gkey:'bulkSelect',value:db.activeBulk},'Edit bulk'),
      D.a({class:'btn',href:`/preview/${db.activeComponent.project}/${db.activeComponent.component}`,target:'_blank'},'Preview')
    ]),
    field('Bulk to save',D.select({name:'activeBulk',gkey:'bulkSelect',value:db.activeBulk},(db.activeComponent.bulks||[]).map(b=>D.option({value:b.name,selected:b.name===db.activeBulk},`${b.name} (${b.lang})`)))),
    D.textarea({class:'editor',gkey:'editCode',value:db.activeCode}),
    D.div({class:'row'},[D.button({class:'btn primary',gkey:'saveCode',disabled:db.codeMode!=='bulk'},'Save human edit'),D.span({class:'muted'},'Select a bulk first. Mini/full tabs are read-only review modes.')])
  ]);
}

function nodeMatches(node, query){
  if(!query) return true;
  const q=String(query).toLowerCase();
  let ok=String(node.slug||'').toLowerCase().includes(q)||String(node.title||'').toLowerCase().includes(q)||String(node.type||'').toLowerCase().includes(q);
  (node.children||[]).forEach(child=>{ if(nodeMatches(child,q)) ok=true; });
  return ok;
}
function TreeNode(db,node,level){
  if(!nodeMatches(node, db.treeSearch||'')) return null;
  const meta=[node.type,node.classification,node.lang,node.lines?`${node.lines} lines`:null].filter(Boolean).join(' | ');
  const hasChildren=(node.children||[]).length>0;
  const open=!hasChildren || db.treeOpen[node.id]!==false;
  return D.div([
    D.div({class:'tree-node','data-node':node.id,style:`padding-inline-start:${8+(level||0)*14}px`},[
      hasChildren?D.button({class:'tree-toggle','data-node':node.id,gkey:'toggleTreeOpen',title:open?'collapse':'expand'},open?'−':'+'):D.span({}),
      node.select?D.input({type:'checkbox','data-node':node.id,checked:!!db.treeSelected[node.id],gkey:'toggleNode'}):D.span({}),
      D.div([D.div({class:'title'},node.title||node.slug),D.div({class:'tiny'},meta)]),
      D.button({class:'bang','data-node':node.id,gkey:'showNodeMd',title:'MD'},'!')
    ]),
    ...(open?(node.children||[]).map(child=>TreeNode(db,child,(level||0)+1)).filter(Boolean):[])
  ]);
}
function VibeTab(db,key,label){
  return D.button({class:db.vibeTab===key?'active':'','data-tab':key,gkey:'vibeTab'},label);
}
function VibeInfoModal(db){
  if(!db.infoModal) return null;
  return D.div({class:'modal-backdrop'},[
    D.div({class:'modal'},[
      D.div({class:'row'},[D.h2('Vibe Coding Protocol'),D.button({class:'btn',gkey:'closeVibeInfo'},'Close')]),
      D.div({class:'md-body',_html:mdToHtml(vibeHelpMd())})
    ])
  ]);
}
function EditableBulksPanel(db){
  const list=db.editableBulks||[];
  const idx=db.selectedEditIndex||0;
  const item=list[idx];
  if(!list.length) return D.section({class:'card'},[
    D.div({class:'row'},[D.h2('Editable Bulks'),D.button({class:'btn blue',gkey:'loadEditableBulks',disabled:!db.promptPacket},'Load selected bulks')]),
    D.p({class:'muted'},'Run Dry prompt first, then load editable selected bulks.')
  ]);
  return D.section({class:'card'},[
    D.div({class:'row'},[D.h2('Editable Bulks'),D.button({class:'btn blue',gkey:'loadEditableBulks'},'Reload'),D.button({class:'btn primary',gkey:'saveEditableBulk'},'Save current'),db.editStatus?D.span({class:'badge'},db.editStatus):null]),
    D.div({class:'edit-grid'},[
      D.div({class:'edit-list'},list.map((b,i)=>D.button({class:i===idx?'active':'','data-index':i,gkey:'selectEditBulk'},[D.strong(b.label),D.div({class:'muted'},b.dirty?'unsaved':'clean')]))),
      item?D.div({class:'stack'},[
        field('Full code',D.textarea({class:'edit-area',gkey:'editBulkContent',value:item.content})),
        field('Bulk metadata JSON',D.textarea({class:'edit-area',gkey:'editBulkMeta',value:item.metaText}))
      ]):D.p({class:'muted'},'Select a bulk')
    ])
  ]);
}
function InstructionsPanel(db){
  const list=db.instructions||[];
  const item=list.find(x=>String(x.id)===String(db.selectedInstruction))||list[0];
  if(!list.length) return D.section({class:'card'},[
    D.div({class:'row'},[D.h2('Classification Instructions'),D.button({class:'btn blue',gkey:'loadInstructions'},'Load instructions')]),
    D.p({class:'muted'},'Edit AI MD, human MD, schema hints, and specialist agent binding.')
  ]);
  return D.section({class:'card'},[
    D.div({class:'row'},[D.h2('Classification Instructions'),D.button({class:'btn',gkey:'loadInstructions'},'Reload'),D.button({class:'btn primary',gkey:'saveInstruction'},'Save instruction'),db.instructionStatus?D.span({class:'badge'},db.instructionStatus):null]),
    D.div({class:'edit-grid'},[
      D.div({class:'edit-list'},list.map(i=>D.button({class:String(i.id)===String((item||{}).id)?'active':'','data-id':i.id,gkey:'selectInstruction'},[D.strong(`${i.classification}/${i.code_kind}`),D.div({class:'muted'},i.agent_slug||'planner')]))),
      item?D.div({class:'stack'},[
        D.div({class:'grid cols3'},[
          field('classification',D.input({name:'classification',gkey:'instructionInput',value:item.classification||''})),
          field('code_kind',D.input({name:'code_kind',gkey:'instructionInput',value:item.code_kind||''})),
          field('agent_slug',D.input({name:'agent_slug',gkey:'instructionInput',value:item.agent_slug||''}))
        ]),
        field('AI MD',D.textarea({class:'edit-area',name:'ai_md',gkey:'instructionInput',value:item.ai_md||''})),
        field('Human MD EN',D.textarea({class:'edit-area',name:'human_md_en',gkey:'instructionInput',value:item.human_md_en||''})),
        field('Human MD AR',D.textarea({class:'edit-area',name:'human_md_ar',gkey:'instructionInput',value:item.human_md_ar||''})),
        field('Schema MD',D.textarea({class:'edit-area',name:'schema_md',gkey:'instructionInput',value:item.schema_md||''}))
      ]):null
    ])
  ]);
}
function VibePage(db){
  const project=(db.protocolTree.projects||[])[0];
  const selected=protocolSelection(db);
  const packet=db.promptPacket;
  const planner=db.plannerRun;
  const tests=(db.protocolTests&&db.protocolTests.tests)||[];
  return D.div({class:'vibe'},[
    VibeInfoModal(db),
    D.section({class:'card'},[
      D.div({class:'row'},[
        D.h2('Project Tree'),
        D.span({class:'badge'},`${selected.length} selected`),
        D.button({class:'btn',gkey:'selectAllProject'},'Select all'),
        D.button({class:'btn',gkey:'clearTreeSelection'},'Clear'),
        D.button({class:'btn blue',gkey:'openVibeInfo'},'Info')
      ]),
      field('Search tree',D.input({name:'treeSearch',gkey:'vibeInput',value:db.treeSearch,placeholder:'component, page, bulk, classification'})),
      D.div({class:'vibe-tree'},project?TreeNode(db,project,0):D.div({class:'muted'},'No protocol tree loaded')),
      db.nodeMd?D.div({class:'bulk-row'},[D.h3([D.span(`${db.nodeMd.type}: ${db.nodeMd.slug}`),D.span({class:'badge'},'MD')]),D.pre({class:'pre'},JSON.stringify(db.nodeMd.md||{},null,2))]):null
    ]),
    D.div({class:'grid'},[
      D.div({class:'vibe-tabs'},[
        VibeTab(db,'prompt','Prompt'),
        VibeTab(db,'planner','Planner'),
        VibeTab(db,'selected','Selected Bulks'),
        VibeTab(db,'edit','Edit Bulks'),
        VibeTab(db,'instructions','Instructions'),
        VibeTab(db,'tests','Tests')
      ]),
      db.vibeTab==='prompt'?D.section({class:'card'},[
        D.div({class:'row'},[
          D.h2('Prompt Packet'),
          D.select({name:'executionMode',gkey:'vibeInput',value:db.executionMode},['planner','direct'].map(x=>D.option({value:x,selected:x===db.executionMode},x))),
          db.executionMode==='direct'?D.select({name:'agentSlug',gkey:'vibeInput',value:db.agentSlug},['quantum-core','mas-ui','mas-store','backend-api','postgres','qa-browser'].map(x=>D.option({value:x,selected:x===db.agentSlug},x))):null,
          D.select({name:'vibeMode',gkey:'vibeInput',value:db.vibeMode},['mini','full'].map(x=>D.option({value:x,selected:x===db.vibeMode},x))),
          D.input({name:'vibeMaxChars',gkey:'vibeInput',value:db.vibeMaxChars,style:'width:110px',title:'max chars'}),
          D.button({class:'btn primary',gkey:'dryPrompt',disabled:!selected.length},'Dry prompt'),
          D.button({class:'btn blue',gkey:'simulatePlanner',disabled:!selected.length},'Simulate planner'),
          D.button({class:'btn',gkey:'downloadPacket','data-mode':'raw',disabled:!packet},'Download raw'),
          D.button({class:'btn',gkey:'downloadPacket','data-mode':'code',disabled:!packet},'Download code'),
          D.button({class:'btn',gkey:'loadEditableBulks',disabled:!packet},'Load edit')
        ]),
        field('Search inside selected bulks',D.input({name:'bulkSearch',gkey:'vibeInput',value:db.bulkSearch,placeholder:'filters by bulk/component name and code content'})),
        field('Developer request',D.textarea({class:'prompt-box',name:'vibePrompt',gkey:'vibeInput',value:db.vibePrompt,placeholder:'اكتب طلبك هنا؛ سيذهب أولا للـ planner'})),
        packet?D.div([
          D.div({class:'row'},[D.span({class:'badge ok'},`${packet.chars} chars`),D.span({class:'badge'},`${packet.code_context.items.length} code bulks`),D.span({class:'badge'},`${packet.code_context.selection_count||0}/${packet.code_context.original_selection_count||0} selected`),D.span({class:'badge'},`${packet.code_context.excluded.length} excluded`)]),
          D.pre({class:'pre raw-prompt'},packet.raw_prompt)
        ]):D.p({class:'muted'},'Dry prompt shows the exact system/project/classification/code/user packet before sending to Bedrock.')
      ]):null,
      db.vibeTab==='planner'?(planner?D.section({class:'card'},[
        D.h2('Planner Simulation'),
        D.div({class:'row'},[D.span({class:'badge ok'},planner.plan.protocol),D.span({class:'badge'},`${(planner.plan.micro_tasks||[]).length} tasks`),D.span({class:'badge '+((planner.plan.gaps||[]).length?'warn':'ok')},`${(planner.plan.gaps||[]).length} gaps`)]),
        D.div((planner.plan.micro_tasks||[]).map(t=>D.div({class:'bulk-row'},[
          D.h3([D.span(`${t.order}. ${t.title}`),D.span({class:'badge'},t.agent_slug)]),
          D.pre({class:'pre'},JSON.stringify({classifications:t.classifications,input_refs:t.input_refs,prompt:t.prompt},null,2))
        ]))),
        (planner.plan.gaps||[]).length?D.pre({class:'pre'},JSON.stringify(planner.plan.gaps,null,2)):null
      ]):D.section({class:'card'},[D.h2('Planner Simulation'),D.p({class:'muted'},'Run Simulate planner from Prompt tab.')])):null,
      db.vibeTab==='selected'?D.section({class:'card'},[
        D.h2('Selected Bulks'),
        packet?(packet.code_context.items||[]).map(item=>D.div({class:'bulk-row'},[
          D.h3([D.span(item.label),D.span({class:'badge'},`${item.chars} chars`)]),
          D.pre({class:'pre'},item.content)
        ])):D.p({class:'muted'},'Run Dry prompt to expand selected pages/components into mini/full bulks.')
      ]):null,
      db.vibeTab==='edit'?EditableBulksPanel(db):null,
      db.vibeTab==='instructions'?InstructionsPanel(db):null,
      db.vibeTab==='tests'?D.section({class:'card'},[
        D.h2('Playwright / Curl Tests'),
        D.div(tests.map(t=>D.div({class:'test-row','data-test':t.id},[
          D.div([D.strong(t.slug),D.div({class:'muted'},`${t.runner_type} | ${t.target_kind}:${t.target_slug} | ${t.url}`)]),
          D.button({class:'btn blue',gkey:'runProtocolTest'},'Run')
        ]))),
        db.lastTestRun?D.pre({class:'pre'},JSON.stringify({ok:db.lastTestRun.ok,run_id:db.lastTestRun.run_id,result:db.lastTestRun.result},null,2)):null
      ]):null
    ])
  ]);
}

function ContextPage(db){
  const ctx=db.context;
  return D.div({class:'grid cols2'},[
    D.section({class:'card'},[D.h2('AI Context Packet'),ctx?D.div([D.p(`${ctx.items.length} items | ${ctx.chars}/${ctx.max_chars} chars | excluded ${ctx.excluded.length}`),D.pre({class:'pre'},JSON.stringify(ctx.items.map(i=>({label:i.label,chars:i.chars})),null,2))]):D.p({class:'muted'},'Select components from Tree, then Build AI context.'),
      field('Task title',D.input({name:'taskTitle',gkey:'taskInput',value:db.taskTitle,placeholder:'Review selected modules'})),
      field('AI prompt',D.textarea({name:'taskPrompt',gkey:'taskInput',value:db.taskPrompt,placeholder:'Tell the agent what to study/change and what to ignore'})),
      D.button({class:'btn primary',gkey:'createTask',disabled:!selectedCount(db)},'Create task from selection')
    ]),
    D.section({class:'card'},[D.h2('Payload'),D.pre({class:'pre'},ctx?ctx.items.map(i=>`# ${i.label}\n${i.content}`).join('\n\n'):'')])
  ]);
}

function TasksPage(db){
  return D.section({class:'card'},[
    D.h2('Vibe Coding Tasks'),
    D.div((db.tasks||[]).map(t=>D.div({class:'project'},[
      D.span({class:'badge '+(t.status==='completed'?'ok':t.status==='failed'?'bad':'warn')},t.status),
      D.div([D.strong(t.title),D.div({class:'muted'},`${t.project_slug||''} | ${t.task_type} | ${t.classification}`),D.div({class:'muted'},t.user_prompt||'')]),
      D.a({class:'btn',href:`/api/platform/tasks/${t.id}/events`,target:'_blank'},'Events')
    ])))
  ]);
}

function SyntaxPage(db){
  const s=db.syntax;
  if(!s) return D.section({class:'card'},[D.h2('Syntax Checks'),D.p({class:'muted'},'Run from Tree for the selected project.')]);
  return D.section({class:'card'},[
    D.h2(`Syntax: ${s.project}`),D.p(`${s.checks.length} checks | ${s.duration_ms}ms | ${s.ok?'OK':'FAIL'}`),
    D.div(s.checks.map(c=>D.div({class:'project'},[D.span({class:'badge '+(c.ok?'ok':'bad')},c.ok?'ok':'fail'),D.div([D.strong(c.name),D.div({class:'muted'},c.lang)]),D.code({class:'muted'},(c.message||'').slice(0,160))])))
  ]);
}

function ServicesPage(db){
  return D.div({class:'grid cols2'},[
    D.section({class:'card'},[D.h2('Dependencies'),D.div((db.deps.checks||[]).map(c=>D.div({class:'project'},[D.span({class:'badge '+(c.ok?'ok':'bad')},c.status),D.strong(c.name),D.span({class:'muted'},c.output||'')])))]),
    D.section({class:'card'},[D.h2('Available Domains'),D.pre({class:'pre'},JSON.stringify(db.domains,null,2))])
  ]);
}

function body(db){
  const pages={overview:'Overview',vibe:'Vibe Coding',tree:'Project Tree',context:'AI Context',tasks:'Tasks',syntax:'Syntax',services:'Services'};
  return D.div({class:'shell'},[
    D.aside({class:'side'},[D.div({class:'brand'},'AI-First'),D.div({class:'sub'},'QDML protocol dashboard'),D.nav({class:'nav'},Object.keys(pages).map(k=>D.button({'data-page':k,gkey:'nav',class:db.page===k?'active':''},pages[k]))),D.button({class:'btn ghost',gkey:'refresh'},db.loading?'Loading...':'Refresh')]),
    D.main({class:'main'},[D.header({class:'top'},[D.h1(pages[db.page]||'AI-First'),D.div({class:'row'},[db.error?D.span({class:'badge bad'},db.error):null,D.a({class:'btn',href:'/',target:'_blank'},'Landing'),D.a({class:'btn',href:'/api/info',target:'_blank'},'API')])]),D.div({class:'content'},[
      db.page==='overview'?Overview(db):null,
      db.page==='vibe'?VibePage(db):null,
      db.page==='tree'?TreePage(db):null,
      db.page==='context'?ContextPage(db):null,
      db.page==='tasks'?TasksPage(db):null,
      db.page==='syntax'?SyntaxPage(db):null,
      db.page==='services'?ServicesPage(db):null
    ])])
  ]);
}

const ui = app(body, state, orders).mount('#app');
loadAll(ui);
"""
