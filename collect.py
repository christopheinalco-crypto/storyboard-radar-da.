"""Collect RSS/Atom from editorial source domains. No fabricated DA analyses."""
import json,os,re,datetime,urllib.parse,urllib.request,xml.etree.ElementTree as ET,html
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
  with urllib.request.urlopen(req,timeout=7) as r:return r.read(800000)
 except Exception:return None
def date(v):
 try:return parsedate_to_datetime(v).astimezone(datetime.timezone.utc).isoformat()
 except Exception:
  try:return datetime.datetime.fromisoformat(v.replace('Z','+00:00')).isoformat()
  except Exception:return ''
def candidates(url):
 p=urllib.parse.urlsplit(url);base=f'{p.scheme}://{p.netloc}'
 return [base+'/feed',base+'/feed/',base+'/rss',base+'/rss.xml',base+'/feed.xml',base+'/atom.xml']
def image_from_markup(markup):
 if not markup:return ''
 m=re.search(r'<img[^>]+(?:src|data-src)=[\\\"\\\'](https?[^\\\"\\\']+)',markup,re.I)
 return html.unescape(m.group(1)) if m else ''
def valid_image(u):
 return u if u and u.startswith('https://') and not any(z in u.lower() for z in ['pixel','tracking','gravatar','1x1']) else ''
def og_image(url):
 try:
  req=urllib.request.Request(url,headers=HEAD)
  with urllib.request.urlopen(req,timeout=5) as r:
   raw=r.read(180000).decode('utf-8','ignore')
  m=re.search(r'<meta[^>]+(?:property|name)=[\\\"\\\'](?:og:image|twitter:image)[\\\"\\\'][^>]+content=[\\\"\\\']([^\\\"\\\']+)',raw,re.I)
  if not m:m=re.search(r'<meta[^>]+content=[\\\"\\\']([^\\\"\\\']+)[\\\"\\\'][^>]+(?:property|name)=[\\\"\\\'](?:og:image|twitter:image)[\\\"\\\']',raw,re.I)
  return valid_image(urllib.parse.urljoin(url,html.unescape(m.group(1)))) if m else ''
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
# Focus on high-priority sources; broaden as feeds are validated.
checked=0;working=[]
for s in sources:
 if s['priority']!='P1':continue
 for u in candidates(s['url']):
  blob=get(u);feed=parse(blob) if blob else []
  if feed:
   working.append({'name':s['name'],'feed':u})
   for x in feed[:12]:
    x.update(source=s['name'],category=s['category'],angle=s['interest'],status='source_detected_not_editorially_analyzed')
    previous=items.get(x['url'],{})
    if not x.get('image'):x['image']=previous.get('image','')
    items[x['url']]={**previous,**x}
   break
 checked+=1
# Enrichir un nombre limité d'articles récents sans ralentir excessivement le workflow.
missing=[x for x in sorted(items.values(),key=lambda y:y.get('published',''),reverse=True)[:80] if not x.get('image')]
for x in missing[:35]:
 x['image']=og_image(x['url'])
print('Checked',checked,'feeds found',len(working),'items',len(items),'images',sum(bool(x.get('image')) for x in items.values()))
result={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'collected_unreviewed','working_feeds':working,'items':sorted(items.values(),key=lambda x:x.get('published',''),reverse=True)[:400]}
with open(os.path.join(ROOT,'data/feed.json'),'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
