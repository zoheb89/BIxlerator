(function(){
  function init(){
    var host=document.querySelector('.top-right');
    if(!host || host.dataset.controlsReady==='1') return !!host;
    var children=Array.prototype.slice.call(host.children);
    var pill=host.querySelector('.pill');
    var theme=children.find(function(x){return x.textContent.trim()==='◔'});
    var help=children.find(function(x){return x.textContent.trim()==='?'});
    var avatar=host.querySelector('.avatar');
    var user=children.find(function(x){return x.textContent.trim().indexOf('Zoheb')===0});
    if(!pill || !theme || !help || !avatar || !user) return false;

    host.dataset.controlsReady='1';
    host.classList.add('interactive-top-right');

    var style=document.createElement('style');
    style.textContent=''+
      '.interactive-top-right{gap:10px!important}'+
      '.header-control{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:34px;border:1px solid transparent;background:transparent;color:#63798d;border-radius:8px;padding:0 9px;font:500 12px "IBM Plex Sans",sans-serif;cursor:pointer;white-space:nowrap}'+
      '.header-control:hover{background:#eef7fb;border-color:#c8d9e5;color:#075b82}'+
      '.header-control.data{font-size:9.5px;letter-spacing:1px;border:1px solid #bfe1ed;color:#00749d;background:#eaf8fc;padding:0 11px}'+
      '.header-control.data:hover{background:#def3fa}'+
      '.header-control.icon{font-size:17px;width:34px;padding:0}'+
      '.header-control.user{padding:0 7px 0 4px;font-size:12px}'+
      '.header-control.user .avatar-small{display:inline-flex;align-items:center;justify-content:center;background:#0877b9;color:#fff;border-radius:50%;width:30px;height:30px;font-weight:600}'+
      '.header-menu{position:fixed;z-index:1000;min-width:260px;max-width:330px;background:#fff;border:1px solid #d5e1eb;border-radius:12px;box-shadow:0 18px 50px rgba(16,42,67,.16);padding:10px;color:#17314d;font-size:11px}'+
      '.header-menu h4{margin:3px 8px 9px;font-size:10px;letter-spacing:.8px;text-transform:uppercase;color:#668096}'+
      '.header-menu button,.header-menu a{display:block;width:100%;text-align:left;border:0;background:transparent;color:#17314d;text-decoration:none;padding:9px 8px;border-radius:7px;font:inherit;cursor:pointer}'+
      '.header-menu button:hover,.header-menu a:hover{background:#eef7fb;color:#00739e}'+
      '.header-menu .menu-row{padding:9px 8px;border-bottom:1px solid #edf1f5}'+
      '.header-menu .menu-row:last-child{border-bottom:0}'+
      '.header-menu strong{display:block;color:#17314d;font-weight:600}'+
      '.header-menu small{display:block;color:#73879a;margin-top:3px;line-height:1.35}'+
      ':root[data-theme="dark"] .header-control{color:#b4c3cf}'+
      ':root[data-theme="dark"] .header-control:hover{background:#203442;border-color:#405866;color:#fff}'+
      ':root[data-theme="dark"] .header-control.data{background:#173946;border-color:#315b6b;color:#72d4e8}'+
      ':root[data-theme="dark"] .header-menu{background:#17232f;border-color:#405463;color:#dce7ed;box-shadow:0 18px 50px rgba(0,0,0,.35)}'+
      ':root[data-theme="dark"] .header-menu h4{color:#91a5b5}'+
      ':root[data-theme="dark"] .header-menu .menu-row{border-color:#304352}'+
      ':root[data-theme="dark"] .header-menu strong,:root[data-theme="dark"] .header-menu button,:root[data-theme="dark"] .header-menu a{color:#e0e9ee}'+
      ':root[data-theme="dark"] .header-menu small{color:#a8bac8}'+
      ':root[data-theme="dark"] .header-menu button:hover,:root[data-theme="dark"] .header-menu a:hover{background:#203442;color:#72d4e8}';
    document.head.appendChild(style);

    function button(label,cls){var b=document.createElement('button');b.type='button';b.className='header-control '+(cls||'');b.textContent=label;return b}
    function closeMenus(){document.querySelectorAll('.header-menu').forEach(function(x){x.remove()})}
    function openMenu(anchor,title,html){
      closeMenus();
      var m=document.createElement('div');m.className='header-menu';
      m.innerHTML='<h4>'+title+'</h4>'+html;
      document.body.appendChild(m);
      var r=anchor.getBoundingClientRect();
      m.style.left=Math.min(Math.max(12,r.right-m.offsetWidth),window.innerWidth-m.offsetWidth-12)+'px';
      m.style.top=(r.bottom+7)+'px';
      return m;
    }

    var data=button('DATA & AI ▾','data');
    pill.replaceWith(data);
    data.onclick=function(e){e.stopPropagation();openMenu(data,'DATA & AI',''+
      '<div class="menu-row"><strong>Migration engines</strong><small>QVD → CSV · Qlik → DAX · Qlik Script → Python</small></div>'+
      '<div class="menu-row"><strong>AI capabilities</strong><small>PII classification · documentation · dashboard concepts</small></div>'+
      '<div class="menu-row"><strong>Runtime</strong><small>FastAPI services and the existing Python engines.</small></div>')};

    var themeBtn=button('◔','icon');
    theme.replaceWith(themeBtn);
    themeBtn.setAttribute('aria-label','Toggle Light and Dark mode');
    function applyTheme(){
      var mode=document.documentElement.dataset.theme==='dark'?'dark':'light';
      themeBtn.textContent=mode==='dark'?'☀':'◔';
      themeBtn.title=mode==='dark'?'Switch to Light mode':'Switch to Dark mode';
    }
    themeBtn.onclick=function(e){
      e.stopPropagation();
      var next=document.documentElement.dataset.theme==='dark'?'light':'dark';
      document.documentElement.dataset.theme=next;
      try{localStorage.setItem('bixlerator-theme',next)}catch(_e){}
      applyTheme();closeMenus();
    };
    applyTheme();

    var helpBtn=button('?','icon');
    help.replaceWith(helpBtn);
    helpBtn.setAttribute('aria-label','Help and resources');
    helpBtn.onclick=function(e){e.stopPropagation();openMenu(helpBtn,'HELP & RESOURCES',''+
      '<div class="menu-row"><strong>How BIxlerator works</strong><small>Use Modules to launch a migration capability and Recent Activity to track jobs.</small></div>'+
      '<a href="/api/docs" target="_blank" rel="noopener">Open API Docs →</a>')};

    var userBtn=button('','user');
    userBtn.innerHTML='<span class="avatar-small">Z</span><span>Zoheb</span><span>⌄</span>';
    avatar.replaceWith(userBtn); user.remove();
    userBtn.setAttribute('aria-label','Open Zoheb workspace menu');
    userBtn.onclick=function(e){e.stopPropagation();openMenu(userBtn,'WORKSPACE',''+
      '<div class="menu-row"><strong>Enterprise Migration Studio</strong><small>BIxlerator workspace · v1.0</small></div>'+
      '<div class="menu-row"><strong>Signed in as Zoheb</strong><small>Profile and authentication services are not enabled in this deployment.</small></div>')};

    document.addEventListener('click',closeMenus);
    window.addEventListener('resize',closeMenus);
    window.addEventListener('scroll',closeMenus,true);
    return true;
  }
  var tries=0, timer=setInterval(function(){if(init()||++tries>100)clearInterval(timer)},100);
})();

(function(){
  async function syncKpis(){
    try{
      var r=await fetch('/api/dashboard',{cache:'no-store'}); if(!r.ok)return;
      var d=await r.json(),k=d.kpis||{},cards=document.querySelectorAll('.kpi-card'); if(cards.length<4)return;
      var values=[k.qvd_assets_converted??0,k.pii_columns_secured??0,k.dax_expressions??0,(k.avg_conversion_seconds??0)+'s'];
      var notes=['+'+(k.qvd_this_week??0)+' this week','actual protected columns','+'+(k.dax_this_week??0)+' this week','completed assets'];
      cards.forEach(function(card,i){var v=card.querySelector('strong'),s=card.querySelector('small');if(v)v.textContent=values[i];if(s)s.textContent=notes[i]});
    }catch(e){}
  }
  syncKpis();setInterval(syncKpis,1000);
})();
