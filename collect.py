"""Collect RSS/Atom from editorial source domains. No fabricated DA analyses."""
import json,os,re,datetime,urllib.parse,urllib.request,xml.etree.ElementTree as ET,html,random,hashlib
from email.utils import parsedate_to_datetime
ROOT=os.path.dirname(__file__)
sources=json.load(open(os.path.join(ROOT,'data/sources.json'),encoding='utf8'))
old=json.load(open(os.path.join(ROOT,'data/feed.json'),encoding='utf8'))
items={x['url']:x for x in old.get('items',[]) if x.get('url')}
HEAD={'User-Agent':'Mozilla/5.0 (compatible; RADARDA/1.0; editorial research)'}
def clean(s):return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',html.unescape(s or ''))).strip()[:900]
def get(url):
 try:
  req=urllib.request.Request(url,headers=HEAD)
  with urllib.request.urlopen(req,timeout=3) as r:return r.read(800000)
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
 m=re.search(r'<img[^>]+(?:src|data-src)\\s*=\\s*["\\x27](https?[^"\\x27]+)',markup,re.I)
 return html.unescape(m.group(1)) if m else ''
def valid_image(u):
 return u if u and u.startswith(('https://','http://')) and not any(z in u.lower() for z in ['pixel','tracking','gravatar','1x1']) else ''
def og_image(url):
 try:
  req=urllib.request.Request(url,headers=HEAD)
  with urllib.request.urlopen(req,timeout=3) as r:
   raw=r.read(220000).decode('utf-8','ignore')
  for tag in re.findall(r'<meta\\s+[^>]*>',raw,re.I):
   if re.search(r'(?:og:image|twitter:image)',tag,re.I):
    m=re.search(r'content\\s*=\\s*["\\x27]([^"\\x27]+)',tag,re.I)
    if m:return valid_image(urllib.parse.urljoin(url,html.unescape(m.group(1))))
  return ''
 except Exception:return ''
def translate_fr(value):
 """Traduction best-effort ; l'original reste disponible en cas d'échec."""
 if not value or len(value)<3:return value
 try:
  query=urllib.parse.urlencode({'client':'gtx','sl':'auto','tl':'fr','dt':'t','q':value[:650]})
  req=urllib.request.Request('https://translate.googleapis.com/translate_a/single?'+query,headers=HEAD)
  with urllib.request.urlopen(req,timeout=6) as r:data=json.load(r)
  return ''.join(part[0] or '' for part in data[0]).strip()
 except Exception:return ''
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
   entries.append(dict(title=title,url=link,published=date(val('pubDate','{http://www.w3.org/2005/Atom}published','{http://www.w3.org/2005/Atom}updated')),summary=clean(desc),image=pic))
 return entries
# Rotation stable par jour : toutes les sources passent sur six créneaux,
# avec un quota renforcé pour les arts de la scène, la TV, les clips et la danse.
now=datetime.datetime.now(datetime.timezone.utc)
slot=int(os.environ.get('RADAR_SLOT_INDEX',str({6:0,9:1,12:2,15:3,18:4,21:5}.get(now.hour,(now.hour//3)%6))))%4
seed=int(hashlib.sha256(now.date().isoformat().encode()).hexdigest()[:12],16)
by_category={}
for s in sources:by_category.setdefault(s['category'],[]).append(s)
rotations=[[] for _ in range(6)]
for category,group in sorted(by_category.items()):
 group=group[:]
 random.Random(seed+int(hashlib.md5(category.encode()).hexdigest()[:8],16)).shuffle(group)
 for i,s in enumerate(group):rotations[i%6].append(s)
# Lors d'un déclenchement manuel, inspecter toutes les sources ; en automatique,
# répartir la charge sur la journée et conserver un renouvellement transversal.
selected=sources if os.environ.get('RADAR_SLOT','')=='manual' else rotations[slot]
random.Random(seed+slot).shuffle(selected)
checked=0;working=[]
for s in selected:
 for u in candidates(s['url'])[:3]:
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
missing=[x for x in sorted(items.values(),key=lambda y:y.get('published',''),reverse=True)[:80] if not x.get('image')]
for x in missing[:18]:
 x['image']=og_image(x['url'])
# Traduction incrémentale, plafonnée pour respecter les limites du service externe.
recent=sorted(items.values(),key=lambda y:y.get('published',''),reverse=True)
translated=0
for x in recent[:100]:
 if translated>=12:break
 if not x.get('title_fr'):
  tr=translate_fr(x.get('title',''))
  if tr:x['title_fr']=tr;translated+=1
 if translated>=12:break
 if x.get('summary') and not x.get('summary_fr'):
  tr=translate_fr(x['summary'])
  if tr:x['summary_fr']=tr;translated+=1
week_start=datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc)
week_end=datetime.datetime(2026,11,8,tzinfo=datetime.timezone.utc)
def in_test_week(x):
 try:return week_start<=datetime.datetime.fromisoformat(x.get('published','').replace('Z','+00:00')).astimezone(datetime.timezone.utc)<week_end
 except Exception:return False
week_items=[x for x in items.values() if in_test_week(x)]
print('TEST RATTRAPAGE 1-7 NOVEMBRE:',len(week_items),'articles,',sum(bool(x.get('image')) for x in week_items),'avec image')
print('Checked',checked,'feeds found',len(working),'items',len(items),'images',sum(bool(x.get('image')) for x in items.values()),'translated fields',translated)
result={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'collected_unreviewed','working_feeds':working,'collection_slot':slot,'sources_checked':checked,'backfill_test':{'period':'2026-11-01/2026-11-07','articles':len(week_items),'with_images':sum(bool(x.get('image')) for x in week_items)},'items':sorted(items.values(),key=lambda x:x.get('published',''),reverse=True)[:550]}
with open(os.path.join(ROOT,'data/feed.json'),'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
