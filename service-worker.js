// RADAR DA — shell cache versioned; HTML and editorial JSON always network-first.
const CACHE='radar-da-shell-v3';
const ROOT='/storyboard-radar-da./';
const ASSETS=[ROOT+'manifest.webmanifest',ROOT+'icons/radar-da.svg'];
self.addEventListener('install',event=>{
 event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
 event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('radar-da-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
 const request=event.request;
 if(request.method!=='GET')return;
 const url=new URL(request.url);
 if(url.origin!==self.location.origin)return;
 // Never serve an outdated page shell or editorial data from a service-worker cache.
 if(request.mode==='navigate'||url.pathname.includes('/data/')||url.pathname.endsWith('/index.html')||url.pathname===ROOT){
  event.respondWith(fetch(new Request(request,{cache:'no-store'})));
  return;
 }
 event.respondWith(fetch(request).catch(()=>caches.match(request)));
});
