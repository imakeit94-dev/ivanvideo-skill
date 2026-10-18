'use strict';
(async () => {
  const $=id=>document.getElementById(id), data=await (await fetch('data.json')).json();
  const audio=$('clock'), video=$('visual'), still=$('still'), fps=data.fps, last=(data.frames-1)/fps;
  let iframe=$('engine');const engines=new Map();
  let current=null, currentTime=0, generation=0, pending=Promise.resolve(), notes=[], errors=[], raf=0, boxes=[], warningList=[];
  const native=$('native-stage');native.style.width=data.width+'px';native.style.height=data.height+'px';
  $('title').textContent=data.title;
  function resize(){const w=$('stage-box').clientWidth;native.style.transform=`scale(${w/data.width})`;$('stage-box').style.height=w*data.height/data.width+'px';}
  new ResizeObserver(resize).observe($('stage-box'));resize();
  $('scrub').max=last;$('scrub').step=1/fps;audio.src=data.audio;
  const regions=data.overlays.map(r=>{const el=document.createElement('div');el.className='region '+r.kind;
    Object.assign(el.style,{left:r.x*data.width+'px',top:r.y*data.height+'px',width:r.width*data.width+'px',height:r.height*data.height+'px',
      borderRadius:r.shape==='circle'?'50%':'0',fontSize:(r.font_size||Math.max(16,data.height*.04))+'px'});
    el.textContent=r.label||(r.kind==='avatar'?'头像占位':r.kind==='subtitle'?'字幕区域':'重要区域');$('regions').append(el);return {...r,el};});
  function caption(t){return data.captions.filter(c=>c.start_seconds<=t&&t<c.end_seconds).map(c=>c.text).join('\n');}
  function waitEvent(el,event){return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{done();reject(new Error(event+' timeout'));},20000);
    const ok=()=>{done();resolve();},bad=()=>{done();reject(new Error('Media failed to load'));};
    function done(){clearTimeout(timer);el.removeEventListener(event,ok);el.removeEventListener('error',bad);}
    el.addEventListener(event,ok,{once:true});el.addEventListener('error',bad,{once:true});});}
  function instrument(w){if(w.__ivanHook)return;w.__ivanHook=true;const p=w.CanvasRenderingContext2D.prototype;
    for(const name of ['fillText','strokeText']){const old=p[name];p[name]=function(text,x,y,maxWidth){
      if(this.canvas===w.__canvas&&this.globalAlpha>.08&&String(text).trim()){
        const m=this.measureText(text), scale=maxWidth&&m.width>maxWidth?maxWidth/m.width:1,T=this.getTransform();
        const left=x-m.actualBoundingBoxLeft*scale,right=x+m.actualBoundingBoxRight*scale,top=y-m.actualBoundingBoxAscent,bottom=y+m.actualBoundingBoxDescent;
        const points=[[left,top],[right,top],[left,bottom],[right,bottom]].map(([x,y])=>({x:T.a*x+T.c*y+T.e,y:T.b*x+T.d*y+T.f}));
        (w.__ivanText||(w.__ivanText=[])).push({text:String(text),x:Math.min(...points.map(p=>p.x)),y:Math.min(...points.map(p=>p.y)),
          right:Math.max(...points.map(p=>p.x)),bottom:Math.max(...points.map(p=>p.y))});
      }return old.apply(this,arguments);};}
  }
  async function loadShot(shot){
    if(current&&current.id===shot.id)return;
    iframe.style.display=video.style.display=still.style.display='none';current=shot;boxes=[];
    if(shot.type==='animation'){
      if(engines.has(shot.id)){iframe=engines.get(shot.id);iframe.style.display='block';return;}
      if(engines.size){iframe=document.createElement('iframe');iframe.title='内置动画 '+shot.id;native.insertBefore(iframe,$('regions'));}
      engines.set(shot.id,iframe);iframe.style.display='block';const loaded=waitEvent(iframe,'load');iframe.src='engine/clip.html?render=1&spec=../'+encodeURI(shot.spec);await loaded;
      const w=iframe.contentWindow;await new Promise((resolve,reject)=>{const start=performance.now();function poll(){
        if(w.__bootFailed)return reject(new Error(w.__bootFailed));if(w.__ready)return resolve();
        if(performance.now()-start>30000)return reject(new Error('Engine timeout'));setTimeout(poll,20);}poll();});instrument(w);
    }else if(shot.type==='video'){
      video.style.display='block';video.style.objectFit=shot.fit;
      if(video.getAttribute('src')!==shot.path){const loaded=waitEvent(video,'loadedmetadata');video.src=shot.path;await loaded;}
    }else{still.style.display='block';still.style.objectFit=shot.fit;
      if(still.getAttribute('src')!==shot.path){const loaded=waitEvent(still,'load');still.src=shot.path;await loaded;}}
  }
  function intersects(b,r){const x=r.x*data.width,y=r.y*data.height,w=r.width*data.width,h=r.height*data.height;
    if(b.right<=x||b.x>=x+w||b.bottom<=y||b.y>=y+h)return false;
    if(r.shape!=='circle')return true;
    const cx=x+w/2,cy=y+h/2,px=Math.max(b.x,Math.min(cx,b.right)),py=Math.max(b.y,Math.min(cy,b.bottom));
    return ((px-cx)/(w/2))**2+((py-cy)/(h/2))**2<=1;
  }
  function inspect(){warningList=[];$('bounds').replaceChildren();const unique=new Set();
    for(const b of boxes){const hits=regions.filter(r=>intersects(b,r)).map(r=>r.id);
      if(b.x<0||b.y<0||b.right>data.width||b.bottom>data.height)hits.push('canvas-edge');
      if(!hits.length)continue;const key=JSON.stringify([b.text,...hits]);if(unique.has(key))continue;unique.add(key);
      warningList.push({text:b.text,regions:hits,bounds:{x:b.x,y:b.y,right:b.right,bottom:b.bottom}});
      const el=document.createElement('div');el.className='text-bound';Object.assign(el.style,{left:b.x+'px',top:b.y+'px',width:(b.right-b.x)+'px',height:(b.bottom-b.y)+'px'});$('bounds').append(el);
    }
    for(const r of regions){if(r.kind==='subtitle'&&caption(currentTime)&&(r.el.scrollHeight>r.el.clientHeight+1||r.el.scrollWidth>r.el.clientWidth+1)){
      warningList.push({text:caption(currentTime),regions:[r.id,'subtitle-overflow'],bounds:{x:r.x*data.width,y:r.y*data.height,right:(r.x+r.width)*data.width,bottom:(r.y+r.height)*data.height}});}}
    $('warnings').replaceChildren();for(const q of warningList){const p=document.createElement('p');p.textContent=`检查线索：${q.text} → ${q.regions.join(', ')}`;$('warnings').append(p);}
    return {time:currentTime,shot:current&&current.id,local_time:current?currentTime-current.start_frame/fps:null,warnings:warningList,caption:caption(currentTime),text_boxes:boxes.length};
  }
  async function render(t){
    const frame=Math.min(data.frames-1,Math.max(0,Math.floor((t+1e-8)*fps))),time=frame/fps;
    const shot=data.shots.find(s=>s.start_frame<=frame&&frame<s.end_frame);if(!shot)throw new Error('Timeline gap');
    await loadShot(shot);const local=time-shot.start_frame/fps;
    if(shot.type==='animation'){const w=iframe.contentWindow;w.__ivanText=[];await w.prepare(local);w.renderFrame(local);boxes=w.__ivanText;}
    else{boxes=[];if(shot.type==='video'){const target=Math.min(video.duration-.001,shot.trim_in_seconds+local);
      if(Math.abs(video.currentTime-target)>.001){const event=waitEvent(video,'seeked');video.currentTime=target;await event;}}}
    currentTime=time;$('scrub').value=time;$('time').textContent=`${time.toFixed(3)} / ${(data.frames/fps).toFixed(3)}s`;
    const cap=caption(time);$('caption').textContent=cap;
    regions.forEach(r=>{if(r.kind==='subtitle')r.el.textContent=cap||r.label||'字幕区域';});
    [...$('shots').children].forEach(b=>b.classList.toggle('current',b.dataset.id===shot.id));
    inspect();$('status').textContent=`${shot.id} · 第 ${frame} 帧 · 声音时钟 ${audio.currentTime.toFixed(3)}s`;
  }
  function pause(){audio.pause();cancelAnimationFrame(raf);}
  async function seek(t){pause();const target=Math.max(0,Math.min(last,Number(t)));if(!Number.isFinite(target))throw new Error('Invalid seek');
    const mine=++generation;pending=pending.catch(()=>{}).then(async()=>{if(mine!==generation)return;
      if(Math.abs(audio.currentTime-target)>.00001||audio.seeking){const done=waitEvent(audio,'seeked');audio.currentTime=target;await done;}
      if(Math.abs(audio.currentTime-target)>1/fps)throw new Error('Audio seek did not reach requested position; use the bundled range-capable preview server');
      await render(target);});await pending;}
  async function tick(){if(audio.paused)return;try{pending=pending.then(()=>audio.paused?undefined:render(Math.min(last,audio.currentTime)));await pending;
    if(audio.currentTime>=last){pause();return;}if(!audio.paused)raf=requestAnimationFrame(tick);}catch(e){fail(e);}}
  async function play(){await pending;if(audio.currentTime>=last)await seek(0);await audio.play();raf=requestAnimationFrame(tick);}
  function fail(error){pause();errors.push(String(error));$('status').textContent='预览失败：'+error;$('play').disabled=true;}
  function state(){return {time:currentTime,audio_time:audio.currentTime,paused:audio.paused,shot:current&&current.id,errors:[...errors]};}
  $('play').onclick=()=>audio.paused?play().catch(fail):pause();$('scrub').oninput=e=>seek(e.target.value).catch(fail);
  $('overlays').onchange=()=>{$('regions').classList.toggle('hidden',!$('overlays').checked);};
  $('boxes').onchange=()=>{$('bounds').classList.toggle('hidden',!$('boxes').checked);};
  for(const shot of data.shots){const b=document.createElement('button');b.dataset.id=shot.id;b.textContent=`${data.selected_ids.includes(shot.id)?'包装':'母版'} · ${shot.id} · ${(shot.start_frame/fps).toFixed(3)}s`;
    b.onclick=()=>seek(shot.start_frame/fps).catch(fail);$('shots').append(b);}
  $('mark').onclick=()=>{const text=$('note').value.trim();if(!text)return;notes.push({time_seconds:currentTime,frame:Math.round(currentTime*fps),shot:current.id,text});
    const li=document.createElement('li');li.textContent=`${currentTime.toFixed(3)}s / ${current.id}：${text}`;$('notes').append(li);$('note').value='';};
  $('save').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,notes},null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='review-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  audio.addEventListener('ended',pause);audio.addEventListener('error',()=>fail(new Error('Audio load failed')));
  window.ivanPreview={ready:false,seek,play,pause,state,inspect};
  if(audio.readyState<1)await waitEvent(audio,'loadedmetadata');
  // Boot animation pages before playback so fonts and images do not interrupt the audio clock at a cut.
  for(const shot of data.shots.filter(s=>s.type==='animation'))await loadShot(shot);
  await seek(Number(new URLSearchParams(location.search).get('t')||0));$('play').disabled=false;window.ivanPreview.ready=true;
})().catch(error=>{document.getElementById('status').textContent='预览失败：'+error;window.ivanPreviewError=String(error);});
