"""Collect RSS/Atom from editorial source domains. No fabricated DA analyses."""
import json,os,re,datetime,urllib.parse,urllib.request,xml.etree.ElementTree as ET,html,random,hashlib,time,time
from email.utils import parsedate_to_datetime
ROOT=os.path.dirname(__file__)
START=time.monotonic()
BUDGET_SECONDS=235
def budget_left():return BUDGET_SECONDS-(time.monotonic()-START)

sources=json.load(open(os.path.join(ROOT,'data/sources.json'),encoding='utf8'))
old=json.load(open(os.path.join(ROOT,'data/feed.json'),encoding='utf8'))
items={x['url']:x for x in old.get('items',[]) if x.get('url') and not re.match(r'^(03|11)\b',x.get('category','')) and not re.search(r'back[ -]?2[ -]?back|back[ -]?to[ -]?back',x.get('title',''),re.I)}
# Rejeter dès la collecte les actualités musicales sans création scénique analysable.
BLOCKED_EDITORIAL = re.compile(r"acetyl[eè]ne|prix.de.la.conception.lumi[eè]re|mylene.farmer.s.est.faite.remixee",re.I)
items={url:item for url,item in items.items() if not BLOCKED_EDITORIAL.search(url+" "+item.get("title",""))}
START=time.monotonic()
MAX_SECONDS=235
def budget():return time.monotonic()-START<MAX_SECONDS
HEAD={'User-Agent':'Mozilla/5.0 (compatible; RADARDA/1.0; editorial research)'}
def clean(s):return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',html.unescape(s or ''))).strip()[:900]
def get(url):
 if not budget():return None
 try:
  req=urllib.request.Request(url,headers=HEAD)
  with urllib.request.urlopen(req,timeout=2.5) as r:return r.read(800000)
 except Exception:return None
def date(v):
 try:return parsedate_to_datetime(v).astimezone(datetime.timezone.utc).isoformat()
 except Exception:
  try:return datetime.datetime.fromisoformat(v.replace('Z','+00:00')).isoformat()
  except Exception:return ''
KNOWN_FEEDS={
 'promonews.tv':['https://www.promonews.tv/rss.xml','https://www.promonews.tv/feed'],
 'stereogum.com':['https://www.stereogum.com/feed/'],
 'pitchfork.com':['https://pitchfork.com/rss/news/','https://pitchfork.com/rss/reviews/music/'],
 'directorsnotes.com':['https://directorsnotes.com/feed/'],
 'livedesignonline.com':['https://www.livedesignonline.com/rss.xml'],
 'tpimagazine.com':['https://www.tpimagazine.com/feed/'],
 'newscaststudio.com':['https://www.newscaststudio.com/feed/'],
 'plsn.com':['https://plsn.com/feed/'],
 'lsionline.com':['https://www.lsionline.com/feed/']
}
def candidates(url):
 p=urllib.parse.urlsplit(url);base=f'{p.scheme}://{p.netloc}';host=p.netloc.removeprefix('www.')
 direct=KNOWN_FEEDS.get(host,[])
 if any(p.path.lower().endswith(z) for z in ['/feed','/feed/','.xml','/rss']):direct=[url]+direct
 return list(dict.fromkeys(direct+[base+'/feed',base+'/feed/',base+'/rss',base+'/rss.xml',base+'/feed.xml',base+'/atom.xml']))
def image_from_markup(markup):
 if not markup:return ''
 m=re.search(r'<img[^>]+(?:src|data-src)\s*=\s*["\x27](https?[^"\x27]+)',markup,re.I)
 return html.unescape(m.group(1)) if m else ''
def valid_image(u):
 return u if u and u.startswith(('https://','http://')) and not any(z in u.lower() for z in ['pixel','tracking','gravatar','1x1']) else ''
def og_image(url):
 """Extract an article's own hero image; never substitute unrelated imagery."""
 if not budget():return ''
 try:
  req=urllib.request.Request(url,headers=HEAD)
  with urllib.request.urlopen(req,timeout=min(5,max(.5,budget_left()))) as r:
   raw=r.read(450000).decode('utf-8','ignore')
  tags=re.findall(r'<meta\s+[^>]*>',raw,re.I)
  for key in ('og:image:secure_url','og:image','twitter:image'):
   for tag in tags:
    attrs={k.lower():html.unescape(v) for k,v in re.findall(r'([\w:-]+)\s*=\s*["\x27]([^"\x27]+)["\x27]',tag)}
    if attrs.get('property','').lower()==key or attrs.get('name','').lower()==key:
     found=valid_image(urllib.parse.urljoin(url,attrs.get('content','')))
     if found:return found
  for pattern in (r'<link[^>]+rel=["\x27]image_src["\x27][^>]+href=["\x27]([^"\x27]+)',r'<img[^>]+(?:class|id)=["\x27][^"\x27]*(?:featured|hero|post-image)[^"\x27]*["\x27][^>]+(?:src|data-src)=["\x27]([^"\x27]+)'):
   m=re.search(pattern,raw,re.I)
   if m:
    found=valid_image(urllib.parse.urljoin(url,html.unescape(m.group(1))))
    if found:return found
  return ''
 except Exception:return ''
def translate_fr(value):
 """Traduction best-effort ; l'original reste disponible en cas d'échec."""
 if not value or len(value)<3 or not budget():return value
 try:
  query=urllib.parse.urlencode({'client':'gtx','sl':'auto','tl':'fr','dt':'t','q':value[:650]})
  req=urllib.request.Request('https://translate.googleapis.com/translate_a/single?'+query,headers=HEAD)
  with urllib.request.urlopen(req,timeout=3) as r:data=json.load(r)
  return ''.join(part[0] or '' for part in data[0]).strip()
 except Exception:return ''
def music_links(markup):
 links={}
 for u in re.findall(r'https?[^\\s\\"\\x27<>]+',html.unescape(markup or '')):
  u=u.rstrip('.,);')
  host=urllib.parse.urlsplit(u).netloc.lower().removeprefix('www.')
  if host in ('youtube.com','m.youtube.com','youtu.be','vimeo.com','dailymotion.com') and ('clip_url' not in links):links['clip_url']=u
  if host in ('open.spotify.com','music.apple.com','soundcloud.com','deezer.com','tidal.com','bandcamp.com') and ('audio_url' not in links):links['audio_url']=u
 return links
def parse(blob):
 try:root=ET.fromstring(blob)
 except Exception:return []
 entries=[]
 for node in root.findall('.//item')+root.findall('{http://www.w3.org/2005/Atom}entry'):
  def val(*tags):
   for tag in tags:
    n=node.find(tag)
    if n is not None and n.text:return n.text.strip()
   return ''
  link=val('link');a=node.find('{http://www.w3.org/2005/Atom}link')
  if not link and a is not None:link=a.attrib.get('href','')
  title=clean(val('title','{http://www.w3.org/2005/Atom}title'))
  if link.startswith('http') and title:
   desc=val('description','{http://www.w3.org/2005/Atom}summary','{http://purl.org/rss/1.0/modules/content/}encoded')
   pic=''
   for tag in ['{http://search.yahoo.com/mrss/}content','{http://search.yahoo.com/mrss/}thumbnail','enclosure']:
    media=node.find(tag)
    if media is not None and (tag!='enclosure' or media.attrib.get('type','').startswith('image/')):
     pic=media.attrib.get('url','')
     if pic:break
   pic=valid_image(pic) or valid_image(image_from_markup(desc))
   entries.append(dict(title=title,url=link,published=date(val('pubDate','{http://www.w3.org/2005/Atom}published','{http://www.w3.org/2005/Atom}updated')),summary=clean(desc),image=pic,**music_links(desc)))
 return entries
# Rattrapage exceptionnel du 1 au 7 novembre : toutes les sources sur un seul passage.\n# Rotation stable par jour : toutes les sources passent sur six créneaux,
# avec un quota renforcé pour les arts de la scène, la TV, les clips et la danse.
from zoneinfo import ZoneInfo
now=datetime.datetime.now(datetime.timezone.utc)
paris=now.astimezone(ZoneInfo('Europe/Paris'))
wave_hours=(6,9,12,15,18,21)
slot=int(os.environ.get('RADAR_SLOT_INDEX',str(wave_hours.index(paris.hour) if paris.hour in wave_hours else 0)))%6
seed=int(hashlib.sha256(paris.date().isoformat().encode()).hexdigest()[:12],16)
by_category={}
for s in sources:by_category.setdefault(s['category'],[]).append(s)
# Chaque vague inclut toutes les catégories. Les sources sont réparties
# entre les huit vagues, avec au moins une source par catégorie et par vague.
rotations=[[] for _ in range(6)]
for category,group in sorted(by_category.items()):
 group=group[:]
 random.Random(seed+int(hashlib.md5(category.encode()).hexdigest()[:8],16)).shuffle(group)
 for wave in range(6):
  selection=[s for i,s in enumerate(group) if i%6==wave]
  if not selection and group:selection=[group[wave%len(group)]]
  rotations[wave].extend(selection)
special=os.environ.get('RADAR_SPECIAL','')=='1'
selected=sources[:] if os.environ.get('RADAR_SLOT','')=='manual' else rotations[slot][:]
if special:
 # Tour 1 : toutes les catégories ; tours supplémentaires : spectacle, concert,
 # clips et danse. Le budget temps reste prioritaire sur le nombre de sources.
 groups={k:v[:] for k,v in by_category.items()}
 for k,v in groups.items():random.Random(seed+int(hashlib.md5(k.encode()).hexdigest()[:8],16)).shuffle(v)
 priority=[k for k in sorted(groups) if any(t in k.lower() for t in ('spectacle','concert','clips','danse'))]
 order=priority+[k for k in sorted(groups) if k not in priority]
 selected=[]
 for round_index in range(max(len(v) for v in groups.values())):
  for cat in order:
   if round_index<len(groups[cat]):selected.append(groups[cat][round_index])
else:
 random.Random(seed+slot).shuffle(selected)
# Priorité de passage : sources montrant la fabrication des projets, puis médias
# créatifs spécialisés. Les sources secondaires restent en rotation, sans
# être supprimées du catalogue.
PRIMARY_DOMAINS={
 'tpimagazine.com':100,'livedesignonline.com':100,'plsn.com':96,
 'lsionline.com':95,'revue-as.fr':94,'promonews.tv':98,
 'directorsnotes.com':90,'newscaststudio.com':90,
 'mindsparklemag.com':76,'designboom.com':74,'dezeen.com':74
}
SECONDARY_DOMAINS={'stereogum.com','pitchfork.com'}
def source_weight(src):
 host=urllib.parse.urlsplit(src.get('url','')).netloc.lower().removeprefix('www.')
 cat=src.get('category','').lower()
 tier=src.get('priority','')
 score=PRIMARY_DOMAINS.get(host,0)
 if any(t in cat for t in ('spectacle','concert','musique clips','tv broadcast')):score+=34
 if any(t in cat for t in ('graphisme','retail','architecture','publicité','marketing','design')):score+=16
 if tier=='P1':score+=15
 if host in SECONDARY_DOMAINS:score-=60
 return score
selected.sort(key=source_weight,reverse=True)
checked=0;working=[]
for s in selected:
 if budget_left()<18:break
 for u in candidates(s['url'])[:2]:
  if budget_left()<18:break
  blob=get(u);feed=parse(blob) if blob else []
  if feed:
   working.append({'name':s['name'],'feed':u,'category':s['category']})
   for x in feed[:35]:
    x.update(source=s['name'],category=s['category'],angle=s['interest'],status='source_detected_not_editorially_analyzed')
    previous=items.get(x['url'],{})
    if not x.get('image'):x['image']=previous.get('image','')
    items[x['url']]={**previous,**x}
   break
 checked+=1
# Enrichir un nombre limité d'articles récents sans ralentir excessivement le workflow.
# Recover missing images first for curated projects and stage productions.
# Retry missing images on subsequent runs; prioritize without relying on recency alone.
def image_priority(x):
 t=(x.get('title','')+' '+x.get('summary','')).lower()
 return (100 if x.get('status')=='editorial_reviewed' else 0)+(45 if re.search(r'concert|tour|scenograph|stage|spectacle|performance|music video|clip',t) else 0)
missing=[x for x in items.values() if not x.get('image') and x.get('url')]
missing.sort(key=lambda x:(image_priority(x),x.get('published','')),reverse=True)
for x in missing[:24]:
 if budget_left()<15:break
 found=og_image(x['url'])
 if found:x['image']=found
# Traduire les TITRES en priorité, avant les résumés : le titre français est essentiel à l'interface.
# Plafond par exécution pour ne pas saturer le service externe.
recent=sorted(items.values(),key=lambda y:y.get('published',''),reverse=True)
translated_titles=0
for x in recent[:100]:
 if translated_titles>=8 or budget_left()<12:break
 if not x.get('title_fr') and x.get('title'):
  tr=translate_fr(x['title'])
  if tr:
   x['title_fr']=tr
   translated_titles+=1
translated_summaries=0
for x in recent[:35]:
 if translated_summaries>=2 or budget_left()<8:break
 if x.get('summary') and not x.get('summary_fr'):
  tr=translate_fr(x['summary'])
  if tr:
   x['summary_fr']=tr
   translated_summaries+=1
translated=translated_titles+translated_summaries
# Précaution éditoriale : ne pas exposer de visuels associés à des contenus explicitement nus.
# Filtrage textuel prudent, qui ne remplace pas une modération visuelle.
unsafe_image_terms=re.compile(r'\\b(?:nudity|nude|naked|topless|full frontal|explicit nudity|pornograph|nsfw|nudit[ée]|dénud[ée]|nu intégral|nue intégrale|sans vêtements)\\b',re.I)
for x in items.values():
 if unsafe_image_terms.search(' '.join([x.get('title',''),x.get('title_fr',''),x.get('summary',''),x.get('summary_fr','')])):
  x['image']=''
week_start=datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc)
week_end=datetime.datetime(2026,11,8,tzinfo=datetime.timezone.utc)
def in_test_week(x):
 try:return week_start<=datetime.datetime.fromisoformat(x.get('published','').replace('Z','+00:00')).astimezone(datetime.timezone.utc)<week_end
 except Exception:return False
week_items=[x for x in items.values() if in_test_week(x)]
print('TEST RATTRAPAGE 1-7 NOVEMBRE:',len(week_items),'articles,',sum(bool(x.get('image')) for x in week_items),'avec image')
# Sélection test : au maximum trois références par étiquette, jamais de remplissage.
# Ce score est une présélection automatique : il ne remplace pas une analyse humaine.
def article_score(x):
 text=(x.get('title','')+' '+x.get('summary','')).lower()
 banned=r'best songs|songs of the week|tracks of the week|playlist|weekly roundup|chart|ranking|\btop [0-9]+\b|album review|newsletter|podcast'
 if re.search(banned,text):return -100
 positive=r'campaign|design|stage|scenograph|concert|show|performance|music video|visual|film|installation|brand|art direction|directed|creative|architecture|typograph|identity|exhibition|clip|lumière|spectacle'
 score=sum(3 for t in re.findall(positive,text))
 score+=2 if x.get('image') else 0
 score+=3 if x.get('summary') and len(x['summary'])>90 else 0
 return score
selected_by_category={}
if special:
 for cat in sorted(by_category):
  candidates_cat=[x for x in items.values() if x.get('category')==cat and x.get('url')]
  candidates_cat.sort(key=lambda x:(article_score(x),x.get('published','')),reverse=True)
  selected_by_category[cat]=[{'title':x.get('title_fr') or x.get('title'),'url':x['url'],'score':article_score(x)} for x in candidates_cat if article_score(x)>=5][:3]
 print('SPECIAL EDITORIAL SHORTLIST:',json.dumps({k:len(v) for k,v in selected_by_category.items()},ensure_ascii=False))
print('Checked',checked,'feeds found',len(working),'items',len(items),'images',sum(bool(x.get('image')) for x in items.values()),'translated fields',translated)
result={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'collected_unreviewed','working_feeds':working,'collection_slot':slot,'collection_hour_paris':paris.hour,'sources_selected':len(selected),'sources_checked':checked,'special_test':special,'special_selection':selected_by_category,'backfill_test':{'period':'2026-11-01/2026-11-07','articles':len(week_items),'with_images':sum(bool(x.get('image')) for x in week_items)},'items':[x for x in sorted(items.values(),key=lambda x:x.get('published',''),reverse=True) if not re.match(r'^(03|11)\b',x.get('category','')) and not re.search(r'back[ -]?2[ -]?back|back[ -]?to[ -]?back',x.get('title',''),re.I)][:550]}
with open(os.path.join(ROOT,'data/feed.json'),'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
