"""RADAR editorial enrichment. Requires OPENAI_API_KEY GitHub Actions secret.
No API key: preserve existing analyses; do not publish invented editorial copy.
"""
import os,json,re,urllib.request,urllib.parse,html,datetime
from pathlib import Path
ROOT=Path(__file__).parent
feed_path=ROOT/'data/feed.json'
out_path=ROOT/'data/analyses.json'
feed=json.loads(feed_path.read_text(encoding='utf-8'))
saved=json.loads(out_path.read_text(encoding='utf-8')) if out_path.exists() else {}
key=os.environ.get('OPENAI_API_KEY','')
if not key:
 print('OPENAI_API_KEY absent: automatic editorial analysis skipped safely.')
 raise SystemExit(0)
def article_text(url):
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (RADAR editorial research)'})
  with urllib.request.urlopen(req,timeout=9) as r:
   raw=r.read(750000).decode('utf-8','ignore')
  raw=re.sub(r'<(script|style|nav|footer|header)[^>]*>[\s\S]*?</\1>',' ',raw,flags=re.I)
  raw=re.sub(r'<[^>]+>',' ',raw)
  return re.sub(r'\s+',' ',html.unescape(raw)).strip()[:16000]
 except Exception:return ''
def score(x):
 t=(x.get('title','')+' '+x.get('summary','')).lower()
 pos=r'scenograph|stage design|tour production|concert|live show|music video|set design|lighting design|performance|immersive|brand experience|art direction|visual identity|installation|film|clip|design'
 neg=r'awards|hiring|job opening|playlist|review|podcast|nominees|top 10|new album|stock|earnings'
 return 50*bool(re.search(pos,t))+30*bool(re.search(r'concert|stage|scenograph|tour production|music video|live show',t))-70*bool(re.search(neg,t))+min(len(x.get('summary',''))//90,15)
candidates=sorted([x for x in feed.get('items',[]) if x.get('url') not in saved and x.get('title') and x.get('url')],key=score,reverse=True)[:12]
for x in candidates:
 if score(x)<20:continue
 source=article_text(x['url'])
 if len(source)<850:
  print('Skip: insufficient full source',x['url']);continue
 prompt='''Tu es rédacteur et directeur artistique senior. Étudie exclusivement le texte fourni de l'article. Écris en français une analyse critique unique et vérifiable, non générique, en JSON strict.
Réponds avec {"publish":boolean,"intro":string,"points":[[titre,texte],...],"takeaway":string}.
Ne publie que si au moins trois décisions créatives précises sont documentées. Sinon publish=false.
L'analyse doit être dense mais concise, accessible, rythmée; entre 3 et 5 points variables selon le projet.
Traite ce qui est réellement pertinent: contexte, auteurs, intention déclarée, insight en tant qu'hypothèse, dispositif, lumière, matière, composition, narration, fabrication, contraintes, rapport au public, émotion probable, leçon transférable.
Ne prétends jamais connaître une intention ou un résultat non attesté. Distingue clairement les faits des hypothèses. Aucun détail inventé, aucun chiffre inventé, pas de répétition. Les titres ne sont pas figés. Mets **en gras** 1 à 2 expressions utiles par point, éventuellement ==un surlignage== exceptionnel.
Le takeaway est un principe DA précis, non un exercice générique.'''
 payload={'model':os.environ.get('RADAR_AI_MODEL','gpt-4.1-mini'),'temperature':0.2,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'title':x['title'],'url':x['url'],'source_text':source},ensure_ascii=False)}]}
 try:
  req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(req,timeout=50) as r:answer=json.load(r)
  a=json.loads(answer['choices'][0]['message']['content'])
  pts=a.get('points',[])
  if a.get('publish') and 3<=len(pts)<=5 and all(isinstance(p,list) and len(p)==2 and len(p[1])>=80 for p in pts) and len(a.get('intro',''))>=90 and len(a.get('takeaway',''))>=50:
   saved[x['url']]={'intro':a['intro'],'points':pts,'takeaway':a['takeaway'],'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_url':x['url']}
   print('Editorial accepted:',x['title'])
  else:print('Editorial rejected:',x['title'])
 except Exception as e:print('Analysis failed:',x['url'],str(e)[:180])
out_path.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Total AI editorials:',len(saved))
