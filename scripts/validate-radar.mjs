import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync('index.html','utf8');
let errors=[];
const scripts=[...html.matchAll(/<script(?:\\s[^>]*)?>([\\s\\S]*?)<\\/script>/gi)].map(x=>x[1]);
if(!scripts.length)errors.push('No inline JavaScript');
scripts.forEach((code,i)=>{try{new vm.Script(code,{filename:'index.html:inline-'+(i+1)})}catch(e){errors.push('JavaScript syntax '+(i+1)+': '+e.message)}});
for(const path of ['data/feed.json','data/analyses.json','data/sources.json']){
 try{JSON.parse(fs.readFileSync(path,'utf8'))}catch(e){errors.push(path+': '+e.message)}
}
for(const marker of ['function toggleInlineStudy','seen-action','source-action','da-study-action','function refreshRadar','function drawFeed']){
 if(!html.includes(marker))errors.push('Missing UI element: '+marker);
}
if(errors.length){console.error('RADAR validation FAILED:\\n'+errors.join('\\n'));process.exit(1)}
console.log('RADAR validation OK: '+scripts.length+' JS scripts, JSON data, navigation markers.');
