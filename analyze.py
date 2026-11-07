"""RADAR editorial enrichment. Requires GEMINI_API_KEY GitHub Actions secret.
No API key: preserve existing analyses; do not publish invented editorial copy.
"""
import os,json,re,urllib.request,urllib.parse,urllib.error,html,datetime,sys
from pathlib import Path
ROOT=Path(__file__).parent
feed_path=ROOT/'data/feed.json'
out_path=ROOT/'data/analyses.json'
feed=json.loads(feed_path.read_text(encoding='utf-8'))
saved=json.loads(out_path.read_text(encoding='utf-8')) if out_path.exists() else {}
key=os.environ.get('GEMINI_API_KEY','')
if not key:
 print('ERROR: GEMINI_API_KEY missing. Add GitHub Actions repository secret GEMINI_API_KEY.')
 raise SystemExit(2)
review_path=ROOT/'data/reviewed.json'
reviewed=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
def available_gemini_model():
 """Choose a generateContent model actually available to this API key."""
 req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',headers={'x-goog-api-key':key,'User-Agent':'RADAR-DA/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=18) as response:catalog=json.load(response)
 except urllib.error.HTTPError as exc:
  details=exc.read(1000).decode('utf-8','replace')
  raise RuntimeError('Gemini model discovery HTTP %s: %s'%(exc.code,details[:450])) from exc
 models=[m['name'].removeprefix('models/') for m in catalog.get('models',[]) if 'generateContent' in m.get('supportedGenerationMethods',[])]
 preferred=[os.environ.get('RADAR_AI_MODEL','gemini-3.5-flash-lite'),'gemini-3.5-flash-lite','gemini-3-flash','gemini-2.5-flash']
 chosen=next((m for m in preferred if m in models),None)
 if not chosen:
  print('Available generateContent models:',', '.join(models[:15]))
  raise RuntimeError('No compatible Gemini model found for this API key')
 print('Gemini model selected:',chosen)
 return chosen
def article_text(url):
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (RADAR editorial research)'})
  with urllib.request.urlopen(req,timeout=9) as r:
   raw=r.read(750000).decode('utf-8','ignore')
  raw=re.sub(r'<(script|style|nav|footer|header)[^>]*>[\s\S]*?</\1>',' ',raw,flags=re.I)
  raw=re.sub(r'<[^>]+>',' ',raw)
  return re.sub(r'\s+',' ',html.unescape(raw)).strip()[:16000]
 except Exception:return ''
def source_image(url):
 """Image issue de la page source uniquement, jamais une illustration inventée."""
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=8) as response:
   markup=response.read(400000).decode('utf-8','ignore')
  for tag in re.findall(r'<meta\\s+[^>]*>',markup,re.I):
   attrs={k.lower():html.unescape(v) for k,v in re.findall(r'([\\w:-]+)\\s*=\\s*["\\x27]([^"\\x27]+)',tag)}
   if (attrs.get('property','').lower() in ('og:image','og:image:secure_url') or attrs.get('name','').lower()=='twitter:image'):
    url_image=urllib.parse.urljoin(url,attrs.get('content',''))
    if url_image.startswith(('https://','http://')):return url_image
 except Exception as exc:print('Image unavailable:',str(exc)[:100])
 return ''
# Priorites editoriales : spectacle, clips, danse, TV et immersion d'abord.
# La qualite du projet prime sur les mots-cles : un article secondaire peut etre retenu.
CATEGORY_PRIORITY={
 '01':100,'14':100,'15':100,'02':95,'08':90,
 '04':78,'07':78,'06':74,'10':72,
 '03':55,'05':52,'11':52,'09':50,'13':50,'12':35
}
PROJECT_SIGNALS=r'scenograph|scenograph|stage design|tour production|concert production|live show|set design|lighting design|broadcast set|tv studio|music video|directed by|performance|stage production|production design|show design|immersive experience|projection mapping|interactive installation|spatial design|event scenography|brand activation|advertising campaign|creative campaign|art direction|dance film|choreograph|fooh|dooh|out.of.home'
CREATIVE_SIGNALS=r'concept|intention|storytell|narrativ|dramaturg|emotion|visual|material|texture|lighting|light|color|colour|space|set|direction|film|design|experience|creative|campaign|installation|identity|cinematograph'
NON_PROJECT=r'sag.aftra|unioniz|union recognition|collective bargain|labor agreement|labour agreement|trade union|workers.rights|union contract|union membership|syndicat|syndical|reconnaissance syndicale|convention collective|appointment|appointed|acquires|acquisition|product launch|introduces|new microphone|distribution partner|conference|trade show|expo|award|playlist|review|podcast|nominees|new album|earnings|hiring|job opening|ranking|chart'
def score(x):
 t=(x.get('title','')+' '+x.get('summary','')).lower()
 cat=(x.get('category') or '')[:2]
 project=bool(re.search(PROJECT_SIGNALS,t))
 creative=bool(re.search(CREATIVE_SIGNALS,t))
 nonproject=bool(re.search(NON_PROJECT,t))
 # Une categorie prioritaire ne suffit pas : il faut des indices d'un projet concret.
 if nonproject:return -100
 return CATEGORY_PRIORITY.get(cat,35)+(65 if project else 0)+(20 if creative else 0)+(10 if x.get('image') else 0)+min(len(x.get('summary',''))//90,12)
# Jusqu'a trois projets par categorie et par veille, avec priorite aux shows, concerts et TV.
# Garde-fou du quota gratuit : 15 appels Gemini maximum par execution.
CATEGORY_ORDER=['01','02','09','14','15','08','06','04','07','10','13','03','05','11','12']
MAX_PER_CATEGORY=3
MAX_API_CALLS=int(os.environ.get('RADAR_MAX_AI_CALLS','15'))
eligible=[x for x in feed.get('items',[]) if x.get('url') not in saved and x.get('url') not in reviewed and x.get('title') and x.get('url') and score(x)>=125 and x.get('published') and x.get('published')[:10]>=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=14)).date().isoformat()]
eligible.sort(key=lambda x:(score(x),x.get('published','')),reverse=True)
by_category={}
for item in eligible:
 code=(item.get('category') or '')[:2]
 by_category.setdefault(code,[]).append(item)
candidates=[]
for code in CATEGORY_ORDER:
 candidates.extend(by_category.get(code,[])[:MAX_PER_CATEGORY])
for code in sorted(set(by_category)-set(CATEGORY_ORDER)):
 candidates.extend(by_category[code][:MAX_PER_CATEGORY])
candidates=candidates[:MAX_API_CALLS]
print('Editorial priority:',', '.join(CATEGORY_ORDER[:5]))
print('Editorial shortlist by category:',{code:sum(x.get('category','')[:2]==code for x in candidates) for code in CATEGORY_ORDER if any(x.get('category','')[:2]==code for x in candidates)})

print('RADAR candidates:',len(candidates),'existing analyses:',len(saved))
attempted=0;accepted=0;source_fail=0;api_fail=0
model=None
if candidates:
 try:model=available_gemini_model()
 except Exception as exc:
  print('Gemini configuration error:',str(exc)[:650])
  raise SystemExit(3)
for x in candidates:
 if score(x)<125:continue
 source=article_text(x['url'])
 if len(source)<850:
  source_fail+=1
  reviewed[x['url']]={'status':'source_unavailable','at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
  print('Skip: insufficient full source',x['url']);continue
 attempted+=1
 prompt='''Tu es directeur artistique senior, critique visuel et pédagogue. Étudie exclusivement l'article source fourni. Rédige en français une analyse éditoriale approfondie, concrète et précise, jamais un simple résumé. Réponds uniquement en JSON valide:
{"publish":boolean,"intro":string,"points":[[titre,texte],...],"takeaway":string,"title_fr":string}.

PUBLICATION : le sujet doit être UNE REALISATION CREATIVE CONCRETE (scénographie, concert, clip, spectacle, danse, plateau TV, installation, publicité, expérience de marque, création graphique ou spatiale). Refuse les annonces de tournée sans dispositif décrit, sorties d'albums/singles, panoramas, classements, actualités syndicales, nominations et communiqués sans création analysable. Publie seulement si la source documente au moins TROIS décisions artistiques observables ou explicitement décrites. Sinon publish=false.

INTRO (130 à 230 mots environ) : situe le projet, ses auteurs et son contexte vérifiables, puis explique l'enjeu artistique spécifique et ce qui mérite d'être observé. Ne répète pas le titre.

POINTS (4 à 6, environ 100 à 160 mots chacun, à adapter à la richesse des faits disponibles) : choisis des angles réellement propres au projet. Pour chaque point, développe (1) un fait ou choix créatif précis attesté par la source, (2) sa logique de conception, (3) l'effet perceptif, narratif ou émotionnel plausible et pourquoi, (4) si pertinent une tension, contrainte ou alternative créative. Approfondis les liens intention → choix de forme → effet produit. Selon le projet : espace, dramaturgie, lumière, couleur, matière, typographie, cadrage, mouvement, montage, rythme, son, chorégraphie, interaction, fabrication, contraintes et réception. N'impose jamais toutes ces rubriques. Titres courts, différents, non répétitifs.

TAKEAWAY (80 à 130 mots environ) : une leçon de direction artistique précise, transférable et applicable, avec condition ou limite; pas une maxime vague.

RIGUEUR : ne fabrique ni intentions d'auteurs, ni descriptions de plans, ni chiffres, ni réactions du public. Distingue explicitement les faits rapportés et les interprétations. Si la source ne permet pas la profondeur demandée, refuse plutôt que d'inventer ou de diluer. Ne cite pas d'experts externes non présents dans la source. Evite les répétitions entre introduction, points et takeaway. Langage vivant, lisible, sans jargon gratuit; mets **en gras** au plus deux expressions importantes par point. Le titre français doit rester fidèle au projet.'''
 payload={'system_instruction':{'parts':[{'text':prompt}]},'contents':[{'role':'user','parts':[{'text':json.dumps({'title':x['title'],'url':x['url'],'source_text':source},ensure_ascii=False)}]}],'generationConfig':{'temperature':0.2,'responseMimeType':'application/json'}}
 try:
  endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(model,safe='')+':generateContent'
  req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(req,timeout=65) as r:answer=json.load(r)
  raw=''.join(p.get('text','') for p in answer['candidates'][0]['content']['parts'])
  a=json.loads(raw)
  pts=a.get('points',[])
  if a.get('publish') and 4<=len(pts)<=6 and all(isinstance(p,list) and len(p)==2 and len(p[1])>=300 for p in pts) and len(a.get('intro',''))>=400 and len(a.get('takeaway',''))>=250:
   if not x.get('image'):x['image']=source_image(x['url'])
   if not x.get('image'):
    reviewed[x['url']]={'status':'no_image','at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    print('Editorial withheld: missing image',x['title']);continue
   saved[x['url']]={'intro':a['intro'],'points':pts,'takeaway':a['takeaway'],'title_fr':a.get('title_fr',''),'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_url':x['url']}
   if a.get('title_fr') and len(a['title_fr'])>=12:x['title_fr']=a['title_fr']
   accepted+=1
   print('Editorial accepted:',x['title'])
  else:
   reviewed[x['url']]={'status':'editorial_rejected','at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   print('Editorial rejected:',x['title'])
 except urllib.error.HTTPError as e:
  api_fail+=1
  details=e.read(1500).decode('utf-8','replace')
  print('Analysis failed:',x['url'],'HTTP',e.code,details[:650])
  if e.code in (400,401,403,404,429):
   print('Gemini API configuration/quota failure: stopping requests for this run.')
   break
 except Exception as e:
  api_fail+=1
  print('Analysis failed:',x['url'],str(e)[:250])
review_path.write_text(json.dumps(reviewed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out_path.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
feed_path.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Total AI editorials:',len(saved))

print('RADAR summary: attempted=%d accepted=%d source_unavailable=%d api_errors=%d'%(attempted,accepted,source_fail,api_fail))
if api_fail:sys.exit(3)
