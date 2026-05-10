// m-bulk:umd_open
;(function(g,f){
  if(typeof module==='object'&&module.exports)module.exports=f();
  else if(typeof define==='function'&&define.amd)define(f);
  else g.MAS=f();
}(typeof globalThis!=='undefined'?globalThis:typeof window!=='undefined'?window:this,function(){'use strict';

// m-end:umd_open
// m-bulk:constants
var _uid=0;
var VOID={area:1,base:1,br:1,col:1,embed:1,hr:1,img:1,input:1,link:1,meta:1,param:1,source:1,track:1,wbr:1};
var SVG_NS='http://www.w3.org/2000/svg';
var SVG_TAGS={svg:1,g:1,path:1,circle:1,ellipse:1,rect:1,line:1,polyline:1,polygon:1,text:1,tspan:1,defs:1,use:1,clipPath:1,mask:1,linearGradient:1,radialGradient:1,stop:1,pattern:1,symbol:1,marker:1,filter:1};
var HEAD_ONLY={title:1,meta:1,link:1,base:1};
var HEAD_CAPABLE={title:1,meta:1,link:1,base:1,style:1,script:1};
var RTL_LANGS={ar:1,fa:1,he:1,ur:1};

// m-end:constants
// m-bulk:hooks
// ── Hooks (Observer pattern — zero core pollution) ──────
var _hooks={onError:[],onRender:[],onState:[]};
function hook(name,fn){if(_hooks[name])_hooks[name].push(fn);return function(){_hooks[name]=_hooks[name].filter(function(f){return f!==fn;});};}
function emit(name,data){var hs=_hooks[name];if(hs)for(var i=0;i<hs.length;i++)try{hs[i](data);}catch(e){console.error('[MAS:hook]',e);}}

// m-end:hooks
// m-bulk:i18n
// ── i18n — optional utility (NOT required by core) ──────
// With database-level flatting, data arrives pre-translated.
// t() is only needed if UI labels are kept client-side.
function t(db,key){
  var i18n=db&&db.i18n;if(!i18n)return key;
  var lang=(db.env&&db.env.lang)||i18n.lang||'en';
  var dict=i18n.dict||i18n;
  var row=dict[key];
  if(!row||typeof row!=='object')return key;
  return row[lang]||row[i18n.fallback||'en']||row[Object.keys(row)[0]]||key;
}

// m-end:i18n
// m-bulk:component_registry
// ── Component Registry ──────────────────────────────────
var _components={};
function component(name,fn,memo){
  // Normalize: 'user-card' and 'userCard' both register as 'user-card'
  var normalized=name.replace(/[A-Z]/g,function(m){return '-'+m.toLowerCase();}).replace(/^-/,'').toLowerCase();
  _components[normalized]={fn:fn,memo:memo||false};
}

function resolveComponent(tag){
  if(_components[tag])return _components[tag];
  var kebab=tag.replace(/[A-Z]/g,function(m){return '-'+m.toLowerCase();}).replace(/^-/,'').toLowerCase();
  return _components[kebab]||null;
}

// ── Module Registry (self-contained capsules) ──────────
var _modules={},_currentDb=null,_currentCtx=null;

function prefixGkey(ns,a){
  if(a&&typeof a==='object'&&!a._t&&a.gkey&&String(a.gkey).indexOf('.')===-1){
    var copy={};for(var k in a)copy[k]=a[k];
    copy.gkey=ns+'.'+a.gkey;
    return copy;
  }
  return a;
}

// m-end:component_registry
// m-bulk:module_system
function createModuleD(ns){
  if(typeof Proxy==='undefined')return D; // fallback
  return new Proxy({},{
    get:function(_,tag){
      if(tag==='h')return function(t,a,b){return h(t,prefixGkey(ns,a),b);};
      // Pass through helper functions (show, unless, etc.)
      if(_dHelpers[tag])return _dHelpers[tag];
      if(typeof tag!=='string')return undefined;
      return function(a,b){return h(tag,prefixGkey(ns,a),b);};
    }
  });
}


function createModuleCtx(ns){
  var $={
    get db(){return(_currentDb||{})[ns]||{};},
    set:function(partial){
      if(!_currentCtx)return;
      var cur=(_currentCtx.db[ns])||{};
      var upd={};for(var k in cur)upd[k]=cur[k];
      if(partial&&typeof partial==='object')for(var k2 in partial)upd[k2]=partial[k2];
      var change={};change[ns]=upd;
      _currentCtx.set(change);
    },
    get root(){return _currentDb||{};},
    get env(){return(_currentDb||{}).env||{};},
    get route(){return(_currentDb||{})._route||{};},
    setRoot:function(p){if(_currentCtx)_currentCtx.set(p);},
    setEnv:function(key,val){
      if(!_currentCtx)return;
      var env=(_currentCtx.db.env)||{};var upd={};for(var ek in env)upd[ek]=env[ek];upd[key]=val;
      if(_currentCtx.db.persistEnv&&_currentCtx.db.persistEnv.indexOf(key)>-1&&typeof localStorage!=='undefined'){try{localStorage.setItem('mas_env_'+key,JSON.stringify(val));}catch(e){}}
      _currentCtx.set({env:upd});
    },
    // ── Smart Helpers ──
    id:function(e){var el=e&&(e.target||e);if(typeof el==='object'&&el.closest)el=el.closest('[data-id]');return el&&el.dataset?isNaN(+el.dataset.id)?el.dataset.id:+el.dataset.id:null;},
    push:function(key,item){var arr=($.db[key]||[]).slice();arr.push(item);var u={};u[key]=arr;$.set(u);},
    drop:function(key,idOrFn){var fn=typeof idOrFn==='function'?function(i){return!idOrFn(i);}:function(i){return(i.id!==undefined?i.id:i)!==idOrFn;};var u={};u[key]=($.db[key]||[]).filter(fn);$.set(u);},
    patch:function(key,id,changes){var u={};u[key]=($.db[key]||[]).map(function(i){return(i.id!==undefined?i.id:i)===id?Object.assign({},i,changes):i;});$.set(u);},
    toggle:function(key){var u={};u[key]=!$.db[key];$.set(u);},
    item:function(key,e){var id=$.id(e);return($.db[key]||[]).find(function(i){return(i.id!==undefined?i.id:i)===id;})||null;},
    bind:function(ev){var t=ev&&(ev.target||ev);if(t&&t.name){var u={};u[t.name]=t.type==='checkbox'?t.checked:t.value;$.set(u);}}
  };
  return $;
}

function registerModule(name,config){
  if(_modules[name]){console.warn('[MAS] Module "'+name+'" already registered! Overwriting.');}
  _modules[name]=config;
  // Register module's UI as a component → D.moduleName() works
  if(config.ui){
    var kebab=name.replace(/[A-Z]/g,function(m){return '-'+m.toLowerCase();}).replace(/^-/,'').replace(/\./g,'-').toLowerCase();
    var modD=createModuleD(name);
    component(kebab,function(props){
      var $=createModuleCtx(name);
      return config.ui($,modD,props);
    },config.memo||false);
  }
  // Inject CSS
  if(config.css&&typeof document!=='undefined'){
    var s=document.createElement('style');
    s.setAttribute('data-mas-mod',name);
    s.textContent=config.css;
    document.head.appendChild(s);
  }
}

// m-end:module_system
// m-bulk:vdom_core

// ── h: create vnode ─────────────────────────────────────
function h(tag,a,b){
  var props={},children=[],key,gkey;
  if(a==null);
  else if(typeof a==='string'||typeof a==='number')children=[a];
  else if(Array.isArray(a))children=a;
  else if(typeof a==='object'&&!a._t){
    for(var k in a){
      if(k==='key'){key=a[k];continue;}
      if(k==='gkey'){gkey=a[k];continue;}
      props[k]=a[k];
    }
    if(b!=null)children=typeof b==='string'||typeof b==='number'?[b]:Array.isArray(b)?b:[b];
  }else children=[a];

  // Check if tag is a registered component
  var comp=resolveComponent(tag);
  if(comp){
    var allProps={};for(var pk in props)allProps[pk]=props[pk];
    allProps.children=normKids(children);
    allProps.key=key;
    // Memo: skip re-render if props unchanged
    var memoFn=comp.memo;
    var cacheKey='_c_'+(comp.fn.name||tag)+'_'+(key!=null?key:'');
    if(memoFn&&comp._prevProps){
      var skip=typeof memoFn==='function'?memoFn(comp._prevProps,allProps):(shallowEqual(comp._prevProps,allProps));
      if(skip&&comp._prevResult){comp._prevProps=allProps;return comp._prevResult;}
    }
    var result=comp.fn(allProps,D);
    if(memoFn){comp._prevProps=allProps;comp._prevResult=result;}
    if(result&&key!=null&&result.key==null)result.key=key;
    if(result&&gkey!=null&&result.gkey==null)result.gkey=gkey;
    return result;
  }

  var kids=normKids(children);
  var tg=String(tag).toLowerCase();
  return{_t:'e',tag:tg,props:props,key:key,gkey:gkey,children:VOID[tg]?[]:kids,_id:++_uid,_el:null,_head:!!HEAD_ONLY[tg]};
}

function normKids(arr){
  var out=[],i,c;
  for(i=0;i<arr.length;i++){
    c=arr[i];
    if(c==null||c===false||c===true){out.push({_t:'x',_el:null});continue;}
    if(typeof c==='string'||typeof c==='number')out.push({_t:'t',v:String(c),_el:null});
    else if(Array.isArray(c)){var inner=normKids(c);for(var j=0;j<inner.length;j++)out.push(inner[j]);}
    else out.push(c);
  }
  return out;
}

function shallowEqual(a,b){
  if(a===b)return true;
  if(!a||!b)return false;
  var ka=Object.keys(a),kb=Object.keys(b);
  if(ka.length!==kb.length)return false;
  for(var i=0;i<ka.length;i++){var k=ka[i];if(k==='children')continue;if(a[k]!==b[k])return false;}
  return true;
}

// ── DSL Proxy ───────────────────────────────────────────
var _dHelpers={};
var D=typeof Proxy!=='undefined'?new Proxy({},{
  get:function(_,tag){
    if(tag==='h')return h;
    if(_dHelpers[tag])return _dHelpers[tag];
    if(typeof tag!=='string')return undefined;
    return function(a,b){return h(tag,a,b);};
  }
}):buildFallbackDSL();

function buildFallbackDSL(){
  var tags='div,span,p,h1,h2,h3,h4,h5,h6,a,button,input,textarea,select,option,optgroup,form,label,fieldset,legend,img,video,audio,canvas,iframe,table,thead,tbody,tfoot,tr,th,td,caption,ul,ol,li,dl,dt,dd,nav,header,footer,main,aside,section,article,details,summary,figure,figcaption,pre,code,blockquote,strong,em,b,i,small,mark,time,hr,br,datalist,output,progress,meter,svg,path,circle,rect,line,g,defs,use,template,picture,source,track,title,meta,link,base,style,script'.split(',');
  var o={h:h};
  tags.forEach(function(t){o[t]=function(a,b){return h(t,a,b);};o[t.charAt(0).toUpperCase()+t.slice(1)]=o[t];});
  for(var hk in _dHelpers)o[hk]=_dHelpers[hk];
  return o;
}
// Conditional helpers
_dHelpers.show=function(cond,vnode){return cond?vnode:null;};
_dHelpers.unless=function(cond,vnode){return cond?null:vnode;};


// m-end:vdom_core
// m-bulk:head_manager
// ── Head Manager ────────────────────────────────────────
var Head={
  _set:function(tag,id,attrs){
    var head=document.head;if(!head)return;
    var sel=tag+'[data-mas="'+id+'"]';
    var el=head.querySelector(sel);
    if(!el){el=document.createElement(tag);el.setAttribute('data-mas',id);head.appendChild(el);}
    for(var k in attrs){
      if(k==='textContent'||k==='text')el.textContent=attrs[k];
      else if(k==='_html'||k==='innerHTML')el.innerHTML=attrs[k];
      else if(attrs[k]==null)el.removeAttribute(k);
      else el.setAttribute(k,String(attrs[k]));
    }
    return el;
  },
  applyVNode:function(v){
    if(!v||v._t!=='e')return;
    var tag=v.tag;
    if(tag==='title'){
      var txt=v.children&&v.children[0]&&v.children[0].v||'';
      if(document)document.title=txt;
      return;
    }
    var id=v.props.id||v.props.name||v.props.property||v.props.rel&&(v.props.rel+':'+(v.props.href||''))||('auto-'+v._id);
    var attrs={};
    for(var k in v.props)attrs[k]=v.props[k];
    if(tag==='style'||tag==='script'){
      var content=v.children&&v.children[0]&&v.children[0].v||'';
      if(content)attrs.textContent=content;
    }
    this._set(tag,id,attrs);
  },
  apply:function(spec){
    if(!spec)return;
    if(spec.title!=null&&document)document.title=String(spec.title);
    var i,arr;
    arr=spec.metas||[];for(i=0;i<arr.length;i++){var m=arr[i];this._set('meta',m.id||m.name||m.property||('m'+i),m);}
    arr=spec.links||[];for(i=0;i<arr.length;i++){var l=arr[i];this._set('link',l.id||(l.rel+':'+(l.href||''))||('l'+i),l);}
    arr=spec.styles||[];for(i=0;i<arr.length;i++){var s=arr[i];this._set('style',s.id||('s'+i),{textContent:s.content||s.text||''});}
    arr=spec.scripts||[];for(i=0;i<arr.length;i++){var sc=arr[i];
      if(sc.src){this._set('script',sc.id||sc.src,sc);}
      else{this._set('script',sc.id||('sc'+i),{textContent:sc.content||sc.text||''});}
    }
  }
};

// m-end:head_manager
// m-bulk:render_engine
// ── Render ──────────────────────────────────────────────
function render(v){
  if(!v)return document.createComment('');
  if(v._t==='x'){var cn=document.createComment('');v._el=cn;return cn;}
  if(v._t==='t'){var tn=document.createTextNode(v.v);v._el=tn;return tn;}
  if(v._head){Head.applyVNode(v);return document.createComment('head:'+v.tag);}
  if(v.props&&v.props._toHead&&HEAD_CAPABLE[v.tag]){Head.applyVNode(v);return document.createComment('head:'+v.tag);}
  var isSvg=SVG_TAGS[v.tag];
  var el=isSvg?document.createElementNS(SVG_NS,v.tag):document.createElement(v.tag);
  if(v.key!=null)el.setAttribute('data-key',String(v.key));
  if(v.gkey!=null)el.setAttribute('gkey',String(v.gkey));
  setProps(el,v.props,{});
  // Bridge: external library manages this element's content
  if(v.props&&typeof v.props._bridge==='function'){
    var cleanup=v.props._bridge(el);
    if(typeof cleanup==='function')el._masCleanup=cleanup;
    el._masBridged=true;
  }else if(v.children){
    for(var i=0;i<v.children.length;i++)el.appendChild(render(v.children[i]));
  }
  v._el=el;
  return el;
}

function setProps(el,next,prev){
  var all={},k;
  for(k in prev)all[k]=1;for(k in next)all[k]=1;
  for(k in all){
    if(k==='_toHead'||k==='_bridge')continue;
    var n=next[k],p=prev[k];
    if(n===p)continue;
    if(k==='class'||k==='className'){el.className=n||'';continue;}
    if(k==='style'){
      if(typeof n==='object'){if(typeof p==='object')for(var s in p)if(!(s in(n||{})))el.style[s]='';for(var s2 in n)el.style[s2]=n[s2];}
      else if(typeof n==='string')el.setAttribute('style',n);
      else el.removeAttribute('style');continue;
    }
    if(k==='value'){
      if(el.tagName==='INPUT'||el.tagName==='TEXTAREA'){
        var active=document.activeElement===el;
        if(active&&typeof el.selectionStart==='number'){
          var ss=el.selectionStart,se=el.selectionEnd;
          if(el.value!==n)el.value=n==null?'':n;
          try{el.setSelectionRange(ss,se);}catch(_){}
        }else if(el.value!==n)el.value=n==null?'':n;
      }else if(el.value!==n)el.value=n;continue;
    }
    if(k==='checked'){el.checked=!!n;continue;}
    if(k==='_html'){if(typeof n==='string')el.innerHTML=n;continue;}
    if(k.slice(0,2)==='on'){
      var ev=k.slice(2).toLowerCase();
      if(typeof p==='function')el.removeEventListener(ev,p);
      if(typeof n==='function')el.addEventListener(ev,n);continue;
    }
    if(n==null||n===false)el.removeAttribute(k);
    else el.setAttribute(k,n===true?'':String(n));
  }
}

// m-end:render_engine
// m-bulk:patch_engine
// ── Patch ───────────────────────────────────────────────
function same(a,b){return a&&b&&a._t===b._t&&a.tag===b.tag&&a.key===b.key;}

function patch(parent,next,prev){
  var el=prev&&prev._el;
  if(next&&(next._head||(next.props&&next.props._toHead&&HEAD_CAPABLE[next.tag]))){
    Head.applyVNode(next);
    if(!prev||!prev._head){}
    return;
  }
  if(!prev){parent.appendChild(render(next));return;}
  if(!next){
    // Cleanup bridged elements before removal
    if(el){
      if(el._masBridged&&typeof el._masCleanup==='function')try{el._masCleanup();}catch(_){}
      if(el.parentNode)el.parentNode.removeChild(el);
    }
    return;
  }
  if(!same(next,prev)){
    var ne=render(next);
    if(el){
      if(el._masBridged&&typeof el._masCleanup==='function')try{el._masCleanup();}catch(_){}
      if(el.parentNode)el.parentNode.replaceChild(ne,el);else parent.appendChild(ne);
    }else parent.appendChild(ne);
    return;
  }
  if(next._t==='x'){next._el=el;return;}
  if(next._t==='t'){if(next.v!==prev.v&&el)el.nodeValue=next.v;next._el=el;return;}
  next._el=el;
  if(next.gkey!==prev.gkey){if(next.gkey!=null)el.setAttribute('gkey',String(next.gkey));else el.removeAttribute('gkey');}
  if(next.key!==prev.key){if(next.key!=null)el.setAttribute('data-key',String(next.key));else el.removeAttribute('data-key');}
  setProps(el,next.props||{},prev.props||{});
  // Bridge: re-call bridge function, skip children patching
  if(next.props&&typeof next.props._bridge==='function'){
    next.props._bridge(el);
    return;
  }
  patchKids(el,next.children||[],prev.children||[]);
}

function patchKids(el,nc,pc){
  var i,hasKeys=false;
  for(i=0;i<nc.length&&!hasKeys;i++)if(nc[i]&&nc[i].key!=null)hasKeys=true;
  for(i=0;i<pc.length&&!hasKeys;i++)if(pc[i]&&pc[i].key!=null)hasKeys=true;
  if(!hasKeys){for(i=0;i<Math.max(nc.length,pc.length);i++)patch(el,nc[i]||null,pc[i]||null);return;}
  // ── Optimized keyed reconciliation ──
  // Phase 1: head/tail matching (covers append, prepend, simple edits)
  var ns=0,ne=nc.length-1,os=0,oe=pc.length-1;
  while(ns<=ne&&os<=oe&&same(nc[ns],pc[os])){patch(el,nc[ns],pc[os]);ns++;os++;}
  while(ns<=ne&&os<=oe&&same(nc[ne],pc[oe])){patch(el,nc[ne],pc[oe]);ne--;oe--;}
  // Phase 2: simple insert (old exhausted, new remains)
  if(os>oe){
    var before=ne+1<nc.length&&nc[ne+1]&&nc[ne+1]._el?nc[ne+1]._el:null;
    for(i=ns;i<=ne;i++){var nel=render(nc[i]);el.insertBefore(nel,before);}
    return;
  }
  // Phase 3: simple remove (new exhausted, old remains)
  if(ns>ne){
    for(i=os;i<=oe;i++)if(pc[i]&&pc[i]._el&&pc[i]._el.parentNode){
      if(pc[i]._el._masBridged&&typeof pc[i]._el._masCleanup==='function')try{pc[i]._el._masCleanup();}catch(_){}
      el.removeChild(pc[i]._el);
    }
    return;
  }
  // Phase 4: general case — map remaining old keys
  var oldMap=new Map(),used=new Set();
  for(i=os;i<=oe;i++){var p=pc[i];if(p&&p.key!=null)oldMap.set(p.key,i);}
  for(i=ns;i<=ne;i++){
    var n=nc[i];
    if(n&&n.key!=null&&oldMap.has(n.key)){var oi=oldMap.get(n.key);used.add(oi);patch(el,n,pc[oi]);}
    else patch(el,n,null);
  }
  for(i=oe;i>=os;i--)
    if(!used.has(i)&&pc[i]&&pc[i]._el&&pc[i]._el.parentNode){
      if(pc[i]._el._masBridged&&typeof pc[i]._el._masCleanup==='function')try{pc[i]._el._masCleanup();}catch(_){}
      el.removeChild(pc[i]._el);
    }
  for(i=ne;i>=ns;i--){
    var ref=i+1<=ne&&nc[i+1]&&nc[i+1]._el?nc[i+1]._el:(ne+1<nc.length&&nc[ne+1]&&nc[ne+1]._el?nc[ne+1]._el:null);
    if(nc[i]&&nc[i]._el&&nc[i]._el.nextSibling!==ref)el.insertBefore(nc[i]._el,ref);
  }
}

// m-end:patch_engine
// m-bulk:scroll_env
// ── Scroll Capture/Restore ──────────────────────────────
function captureScroll(targets){
  if(!targets||!targets.length)return[];
  var entries=[];
  for(var i=0;i<targets.length;i++){
    var t=targets[i];
    if(t==='window'||t===window){
      entries.push({top:window.scrollY||0,left:window.scrollX||0,win:true});continue;
    }
    var node=typeof t==='string'?document.querySelector(t):t;
    if(node)entries.push({sel:t,top:node.scrollTop,left:node.scrollLeft,node:node});
  }
  return entries;
}
function restoreScroll(entries){
  if(!entries||!entries.length)return;
  var apply=function(){for(var i=0;i<entries.length;i++){
    var e=entries[i];
    if(e.win){try{window.scrollTo(e.left,e.top);}catch(_){}continue;}
    var n=e.node||(typeof e.sel==='string'?document.querySelector(e.sel):null);
    if(n){n.scrollTop=e.top;n.scrollLeft=e.left;}
  }};
  apply();requestAnimationFrame(function(){apply();requestAnimationFrame(apply);});
}

// ── Env ─────────────────────────────────────────────────
function applyEnv(db){
  var root=document&&document.documentElement;if(!root)return;
  var env=db&&db.env||{};
  var lang=env.lang||'en';
  root.setAttribute('lang',lang);
  root.setAttribute('dir',RTL_LANGS[lang]?'rtl':'ltr');
  var theme=env.theme||'light';
  root.setAttribute('data-theme',theme);
  if(theme==='dark')root.classList.add('dark');else root.classList.remove('dark');
}

// m-end:scroll_env
// m-bulk:delegation
// ── Event Delegation (New Format) ───────────────────────
// Orders format:
//   { gkey: { on: 'click',             do: fn } }   — single event
//   { gkey: { on: ['click','touchend'], do: fn } }   — multiple events
//   { gkey: fn }                                      — shorthand (click)
//
// The `do` function receives (event, ctx)
// The `gkey` matches the element attribute gkey="..."
var KNOWN_EVENTS={click:1,dblclick:1,contextmenu:1,input:1,change:1,submit:1,reset:1,keydown:1,keypress:1,keyup:1,pointerdown:1,pointerup:1,pointermove:1,mousedown:1,mouseup:1,mousemove:1,mouseenter:1,mouseleave:1,touchstart:1,touchend:1,touchmove:1,focus:1,blur:1,wheel:1,scroll:1,drag:1,dragstart:1,dragend:1,dragover:1,drop:1};

function parseOrders(obj){
  var map={};
  function add(ev,gk,fn){
    if(!map[ev])map[ev]=[];
    map[ev].push({gkey:gk,fn:fn});
  }
  for(var gk in obj){
    var val=obj[gk];
    // Shorthand: { save: fn }  →  click on gkey="save"
    if(typeof val==='function'){
      add('click',gk,val);
      continue;
    }
    // Full format: { save: { on: 'click', do: fn } }
    if(val&&typeof val==='object'&&typeof val.do==='function'){
      var events=val.on||'click';
      if(typeof events==='string')events=[events];
      for(var i=0;i<events.length;i++){
        var ev=events[i].replace(/^on/i,'').toLowerCase();
        add(ev,gk,val.do);
      }
    }
  }
  return map;
}

function delegate(root,ordersMap,ctx){
  var teardowns=[];
  for(var evName in ordersMap){
    (function(type,handlers){
      var capture=type==='focus'||type==='blur'||type==='scroll';
      var listener=function(e){
        var node=e.target;
        while(node&&node!==root){
          var href=node.getAttribute&&node.getAttribute('data-href');
          if(type==='click'&&href){e.preventDefault();if(typeof go==='function')go(href);return;}
          var gk=node.getAttribute&&node.getAttribute('gkey');
          if(gk){for(var i=0;i<handlers.length;i++){
            if(handlers[i].gkey===gk||handlers[i].gkey==='*'){
              try{handlers[i].fn(e,ctx);}catch(err){emit('onError',{type:'order',error:err,gkey:gk});console.error('[MAS]',err);}
              return;
            }
          }}
          node=node.parentElement;
        }
      };
      root.addEventListener(type,listener,capture);
      teardowns.push(function(){root.removeEventListener(type,listener,capture);});
    })(evName,ordersMap[evName]);
  }
  return{teardown:function(){teardowns.forEach(function(f){f();});}};
}

// m-end:delegation
// m-bulk:app_factory
// ── App Factory ─────────────────────────────────────────
function createApp(bodyFn,database,orders){
  var db=database||{};
  // Load persisted env variables if defined in db.persistEnv
  if(db.persistEnv&&db.env&&typeof localStorage!=='undefined'){
    for(var ei=0;ei<db.persistEnv.length;ei++){
      var epk=db.persistEnv[ei];
      try{var esaved=localStorage.getItem('mas_env_'+epk);if(esaved!==null)db.env[epk]=JSON.parse(esaved);}catch(_){}
    }
  }
  // Auto-merge module state under namespace with persistence
  for(var ns in _modules){
    var m=_modules[ns];
    if(m.db&&!db[ns]){
      var initDb=JSON.parse(JSON.stringify(m.db));
      if(m.persist&&typeof localStorage!=='undefined'){
        for(var i=0;i<m.persist.length;i++){
          var pkey=m.persist[i];
          var saved=localStorage.getItem('mas_'+ns+'_'+pkey);
          if(saved!==null){try{initDb[pkey]=JSON.parse(saved);}catch(_){}}
        }
      }
      db[ns]=initDb;
    }
  }
  // Auto-merge module orders — wrap handlers with $ (module context)
  var mergedOrders={};
  if(orders)for(var ok in orders)mergedOrders[ok]=orders[ok];
  for(var ns2 in _modules){
    var mo=_modules[ns2].orders;
    if(mo)for(var gk in mo){
      var entry=mo[gk];
      // Wrap handler: convert ctx → $ (module-scoped context)
      (function(modNs,origEntry){
        var origFn=typeof origEntry==='function'?origEntry:(origEntry&&origEntry.do);
        var events=typeof origEntry==='object'&&origEntry.on?origEntry.on:'click';
        var wrappedFn=function(e,ctx){
          var $={get db(){return ctx.db[modNs]||{};},
            set:function(p){var cur=ctx.db[modNs]||{};var u={};for(var k in cur)u[k]=cur[k];if(p&&typeof p==='object')for(var k2 in p)u[k2]=p[k2];var ch={};ch[modNs]=u;ctx.set(ch);},
            get root(){return ctx.db;},get env(){return ctx.db.env||{};},get route(){return ctx.db._route||{};},
            setRoot:function(p){ctx.set(p);},
            setEnv:function(key,val){
              var env=ctx.db.env||{};var upd={};for(var ek in env)upd[ek]=env[ek];upd[key]=val;
              if(ctx.db.persistEnv&&ctx.db.persistEnv.indexOf(key)>-1&&typeof localStorage!=='undefined'){try{localStorage.setItem('mas_env_'+key,JSON.stringify(val));}catch(e){}}
              ctx.set({env:upd});
            },
            id:function(ev){var el=ev&&(ev.target||ev);if(typeof el==='object'&&el.closest)el=el.closest('[data-id]');return el&&el.dataset?isNaN(+el.dataset.id)?el.dataset.id:+el.dataset.id:null;},
            push:function(key,item){var arr=($.db[key]||[]).slice();arr.push(item);var pu={};pu[key]=arr;$.set(pu);},
            drop:function(key,idOrFn){var fn=typeof idOrFn==='function'?function(i){return!idOrFn(i);}:function(i){return(i.id!==undefined?i.id:i)!==idOrFn;};var dr={};dr[key]=($.db[key]||[]).filter(fn);$.set(dr);},
            patch:function(key,id,changes){var pa={};pa[key]=($.db[key]||[]).map(function(i){return(i.id!==undefined?i.id:i)===id?Object.assign({},i,changes):i;});$.set(pa);},
            toggle:function(key){var tg={};tg[key]=!$.db[key];$.set(tg);},
            item:function(key,ev){var id=$.id(ev);return($.db[key]||[]).find(function(i){return(i.id!==undefined?i.id:i)===id;})||null;},
            bind:function(ev){var t=ev&&(ev.target||ev);if(t&&t.name){var u={};u[t.name]=t.type==='checkbox'?t.checked:t.value;$.set(u);}}
          };
          origFn(e,$);
        };
        mergedOrders[modNs+'.'+gk]={on:events,do:wrappedFn};
      })(ns2,entry);
    }
  }
  var vdom=null,rootEl=null,ctx=null;
  var dirty=false,scheduled=false;
  var freezeDepth=0,pendingScroll=null;
  var delegation=null,ordersMap=parseOrders(mergedOrders);

  function schedule(){
    if(scheduled||freezeDepth>0)return;
    scheduled=true;
    requestAnimationFrame(function(){scheduled=false;if(dirty&&freezeDepth===0)flush();});
  }

  function flush(opts){
    dirty=false;scheduled=false;
    try{
      applyEnv(db);
      if(db.head)Head.apply(db.head);
      var scrollEntries=captureScroll(pendingScroll||(opts&&opts.keepScroll));
      _currentDb=db;_currentCtx=ctx;
      var next=bodyFn(db,D);
      patch(rootEl,next,vdom);
      vdom=next;
      if(scrollEntries.length)restoreScroll(scrollEntries);
      pendingScroll=null;
      emit('onRender',{db:db,root:rootEl});
    }catch(err){
      emit('onError',{type:'render',error:err});
      console.error('[MAS:render]',err);
    }
  }

  ctx={
    get db(){return db;},
    set:function(partial,opts){
      var prev=db;
      if(typeof partial==='function')db=partial(db);
      else if(partial&&typeof partial==='object'){
        var n={};for(var k in db)n[k]=db[k];
        for(var k2 in partial){
          n[k2]=partial[k2];
          var m=_modules[k2];
          if(m&&m.persist&&typeof localStorage!=='undefined'){
            for(var pi=0;pi<m.persist.length;pi++){
              var pk=m.persist[pi];
              if(partial[k2][pk]!==undefined){try{localStorage.setItem('mas_'+k2+'_'+pk,JSON.stringify(partial[k2][pk]));}catch(e){}}
            }
          }
        }
        db=n;
      }
      else db=partial;
      emit('onState',{prev:prev,next:db});
      dirty=true;
      // Priority scheduling: 'idle' uses requestIdleCallback
      var pri=opts&&opts.priority;
      if(pri==='idle'&&typeof requestIdleCallback!=='undefined'){
        if(!scheduled){scheduled=true;requestIdleCallback(function(){scheduled=false;if(dirty&&freezeDepth===0)flush();});}
      }else{schedule();}
    },
    getState:function(){return db;},
    setState:function(u,o){ctx.set(u,o);},
    flush:function(opts){flush(opts);},
    rebuild:function(opts){flush(opts);},
    freeze:function(scrollTargets){
      freezeDepth++;
      if(scrollTargets)pendingScroll=(pendingScroll||[]).concat(Array.isArray(scrollTargets)?scrollTargets:[scrollTargets]);
      return freezeDepth;
    },
    unfreeze:function(){
      if(freezeDepth>0)freezeDepth--;
      if(freezeDepth===0&&dirty)flush();
      return freezeDepth;
    },
    batch:function(fn){
      ctx.freeze();
      try{if(typeof fn==='function')fn(ctx);}
      finally{ctx.unfreeze();}
    },
    t:function(key){return t(db,key);}
  };

  var instance={
    mount:function(sel){
      rootEl=typeof sel==='string'?document.querySelector(sel):sel;
      if(!rootEl){console.error('[MAS] mount target not found:',sel);return instance;}
      applyEnv(db);
      if(db.head)Head.apply(db.head);
      _currentDb=db;_currentCtx=ctx;
      vdom=bodyFn(db,D);
      rootEl.innerHTML='';
      rootEl.appendChild(render(vdom));
      if(delegation)delegation.teardown();
      delegation=delegate(rootEl,ordersMap,ctx);
      // Auto-fetch modules that have a fetch function
      for(var ns in _modules){if(typeof _modules[ns].fetch==='function'){
        (function(modNs,fetchFn){
          var $={get db(){return db[modNs]||{};},
            set:function(p){var cur=db[modNs]||{};var u={};for(var k in cur)u[k]=cur[k];for(var k2 in p)u[k2]=p[k2];var ch={};ch[modNs]=u;ctx.set(ch);},
            get root(){return db;},get env(){return db.env||{};}
          };
          Promise.resolve().then(function(){return fetchFn($);}).catch(function(err){$.set({error:err.message,loading:false});});
        })(ns,_modules[ns].fetch);
      }}
      emit('onRender',{db:db,root:rootEl});
      return instance;
    },
    // ── Hydration: attach events to server-rendered HTML ──
    hydrate:function(sel){
      rootEl=typeof sel==='string'?document.querySelector(sel):sel;
      if(!rootEl){console.error('[MAS] hydrate target not found:',sel);return instance;}
      applyEnv(db);
      _currentDb=db;_currentCtx=ctx;
      // Build VDOM from body function (same as mount)
      vdom=bodyFn(db,D);
      // Walk existing DOM and link _el references (no DOM creation)
      hydrateNode(rootEl.firstChild,vdom);
      if(delegation)delegation.teardown();
      delegation=delegate(rootEl,ordersMap,ctx);
      emit('onRender',{db:db,root:rootEl});
      return instance;
    },
    get state(){return db;},
    set:ctx.set,
    setState:ctx.set,
    getState:function(){return db;},
    flush:ctx.flush,
    rebuild:ctx.flush,
    freeze:ctx.freeze,
    unfreeze:ctx.unfreeze,
    batch:ctx.batch,
    setOrders:function(newOrders){
      ordersMap=parseOrders(newOrders||{});
      if(delegation)delegation.teardown();
      if(rootEl)delegation=delegate(rootEl,ordersMap,ctx);
    }
  };
  return instance;
}

// m-end:app_factory
// m-bulk:hydration
// ── Hydration helper: link existing DOM to VDOM ─────────
function hydrateNode(domNode,vnode){
  if(!vnode||!domNode)return;
  if(vnode._head)return;
  if(vnode._t==='t'){vnode._el=domNode;return;}
  vnode._el=domNode;
  // Set props that need JS (value, checked, bridge)
  if(vnode.props){
    if(vnode.props.value!=null&&domNode.value!==undefined)domNode.value=vnode.props.value;
    if(vnode.props.checked!=null)domNode.checked=!!vnode.props.checked;
    if(typeof vnode.props._bridge==='function'){
      var cleanup=vnode.props._bridge(domNode);
      if(typeof cleanup==='function')domNode._masCleanup=cleanup;
      domNode._masBridged=true;
    }
  }
  // Recurse children
  if(vnode.children&&!domNode._masBridged){
    var domKids=domNode.childNodes;
    var vi=0;
    for(var di=0;di<domKids.length&&vi<vnode.children.length;di++){
      var dk=domKids[di],vc=vnode.children[vi];
      if(!vc)continue;
      if(vc._t==='t'&&dk.nodeType===3){vc._el=dk;vi++;continue;}
      if(vc._t==='e'&&dk.nodeType===1){hydrateNode(dk,vc);vi++;continue;}
      if(dk.nodeType===8)continue; // skip comments
      vi++;
    }
  }
}

// m-end:hydration
// m-bulk:lazy_loader
// ── Script Loader (lazy loading) ────────────────────────
var _loaded={};
function load(url,cb){
  if(_loaded[url]){if(cb)cb(null);return Promise.resolve();}
  return new Promise(function(resolve,reject){
    var s=document.createElement('script');
    s.src=url;s.async=true;
    s.onload=function(){_loaded[url]=true;if(cb)cb(null);resolve();};
    s.onerror=function(e){var err=new Error('Failed to load: '+url);if(cb)cb(err);reject(err);};
    document.head.appendChild(s);
  });
}
function loaded(url){return!!_loaded[url];}

// ── Lazy Modules ────────────────────────────────────────
var _lazyModules={};
function lazyModule(name,url){
  _lazyModules[name]={url:url,loading:false,loaded:false};
  // Register a placeholder component that triggers loading on first use
  var kebab=name.replace(/[A-Z]/g,function(m){return '-'+m.toLowerCase();}).replace(/^-/,'').replace(/\./g,'-').toLowerCase();
  component(kebab,function(props,D){
    var lm=_lazyModules[name];
    if(lm.loaded&&_modules[name]){
      // Module is loaded — render it
      var $=createModuleCtx(name);
      var modD=createModuleD(name);
      return _modules[name].ui($,modD,props);
    }
    if(!lm.loading){
      lm.loading=true;
      load(lm.url).then(function(){
        lm.loaded=true;lm.loading=false;
        // Module should have registered itself via MAS.module() in the loaded script
        // Trigger re-render
        if(_currentCtx)_currentCtx.set({});
      }).catch(function(err){
        lm.loading=false;
        console.error('[MAS:lazy]',err);
      });
    }
    // Show loading placeholder
    return D.div({class:'mas-lazy-loading'},'⏳');
  });
}

// m-end:lazy_loader
// m-bulk:ssr
// ── SSR: Server-Side Rendering ──────────────────────────
var ESC={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return ESC[c];});}

function renderToString(v){
  if(!v)return'';
  if(v._t==='t')return esc(v.v);
  if(v._head)return''; // head elements handled separately
  var tag=v.tag,html='<'+tag;
  for(var k in v.props){
    if(k==='_html'||k==='_bridge'||k==='_toHead')continue;
    if(k.slice(0,2)==='on')continue;
    var val=v.props[k];
    if(val===true)html+=' '+k;
    else if(val!=null&&val!==false)html+=' '+k+'="'+esc(String(val))+'"';
  }
  if(v.gkey)html+=' gkey="'+esc(v.gkey)+'"';
  if(v.key!=null)html+=' data-key="'+esc(String(v.key))+'"';
  if(VOID[tag])return html+'/>';
  html+='>';
  if(v.props&&typeof v.props._html==='string'){html+=v.props._html;}
  else{for(var i=0;i<v.children.length;i++)html+=renderToString(v.children[i]);}
  return html+'</'+tag+'>';
}

function renderHeadToString(db){
  var html='';
  if(!db||!db.head)return html;
  var h=db.head;
  if(h.title)html+='<title>'+esc(h.title)+'</title>';
  var i,arr;
  arr=h.metas||[];for(i=0;i<arr.length;i++){html+='<meta';for(var k in arr[i])html+=' '+k+'="'+esc(arr[i][k])+'"';html+='/>';}
  arr=h.links||[];for(i=0;i<arr.length;i++){html+='<link';for(var k2 in arr[i])html+=' '+k2+'="'+esc(arr[i][k2])+'"';html+='/>';}
  arr=h.styles||[];for(i=0;i<arr.length;i++)html+='<style>'+(arr[i].content||'')+'</style>';
  arr=h.scripts||[];for(i=0;i<arr.length;i++){
    if(arr[i].src)html+='<script src="'+esc(arr[i].src)+'"><\/script>';
    else html+='<script>'+(arr[i].content||'')+'<\/script>';
  }
  return html;
}

// m-end:ssr
// m-bulk:router_exports
// ── Router ──────────────────────────────────────────────
var _router=null;
function createRouter(appInstance,routeMap,opts){
  opts=opts||{};
  var mode=opts.mode||'hash';
  var routes=[],guardFn=opts.guard||null;
  var beforeEachFn=opts.beforeEach||null,afterEachFn=opts.afterEach||null;
  var _prevRoute=null;

  for(var pattern in routeMap){
    var name=routeMap[pattern];
    var keys=[];
    var regStr='^'+pattern.replace(/:([^/]+)/g,function(_,k){keys.push(k);return'([^/]+)';}).replace(/\*/g,'.*')+'$';
    routes.push({pattern:pattern,name:name,keys:keys,regex:new RegExp(regStr)});
  }

  function getPath(){
    if(mode==='hash'){var h=(typeof location!=='undefined'&&location.hash||'#/');return h.slice(1)||'/';}
    return typeof location!=='undefined'?location.pathname:'/';
  }

  function resolve(path){
    path=path||getPath();
    var query={};
    var qi=path.indexOf('?');
    if(qi>-1){var qs=path.slice(qi+1);path=path.slice(0,qi);qs.split('&').forEach(function(p){var kv=p.split('=');if(kv[0])query[decodeURIComponent(kv[0])]=decodeURIComponent(kv[1]||'');});}
    for(var i=0;i<routes.length;i++){
      var r=routes[i],m=path.match(r.regex);
      if(m){
        var params={};
        for(var j=0;j<r.keys.length;j++)params[r.keys[j]]=decodeURIComponent(m[j+1]);
        return{name:r.name,path:path,params:params,query:query,pattern:r.pattern};
      }
    }
    for(var k=0;k<routes.length;k++){if(routes[k].pattern==='*')return{name:routes[k].name,path:path,params:{},query:query,pattern:'*'};}
    return{name:'__404',path:path,params:{},query:query,pattern:null};
  }

  function apply(routeInfo){
    if(beforeEachFn){var ok=beforeEachFn(_prevRoute,routeInfo,appInstance.state);if(ok===false)return false;}
    if(guardFn){var allowed=guardFn(routeInfo,appInstance.state);if(allowed===false)return false;}
    appInstance.set({_route:routeInfo});
    if(afterEachFn)afterEachFn(_prevRoute,routeInfo);
    _prevRoute=routeInfo;
    return true;
  }

  function go(path,goOpts){
    goOpts=goOpts||{};
    var info=resolve(path);
    if(beforeEachFn){var ok=beforeEachFn(_prevRoute,info,appInstance.state);if(ok===false)return false;}
    if(guardFn){var allowed=guardFn(info,appInstance.state);if(allowed===false)return false;}
    try{
      if(mode==='hash'){
        if(goOpts.replace)location.replace('#'+path);
        else location.hash='#'+path;
      }else{
        if(goOpts.replace)history.replaceState(null,'',path);
        else history.pushState(null,'',path);
      }
    }catch(err){console.warn('[MAS:router] URL update blocked (often happens in local file:// iframes):',err.message);}
    if(mode!=='hash')apply(info); // apply directly if not relying on hashchange
    return true;
  }

  function start(){
    var initial=resolve();
    apply(initial);
    if(mode==='hash'){
      window.addEventListener('hashchange',function(){apply(resolve());});
    }else{
      window.addEventListener('popstate',function(){apply(resolve());});
    }
  }

  _router={go:go,resolve:resolve,start:start,routes:routes,mode:mode};
  return _router;
}

function go(path,opts){if(_router)return _router.go(path,opts);console.warn('[MAS] No router initialized');}

return{
  D:D,h:h,app:createApp,t:t,
  Head:Head,applyEnv:applyEnv,
  hook:hook,component:component,module:registerModule,lazy:lazyModule,
  load:load,loaded:loaded,
  renderToString:renderToString,renderHeadToString:renderHeadToString,
  router:createRouter,go:go
};
}));


// m-end:router_exports