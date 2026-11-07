"""Collect RSS/Atom from editorial source domains. No fabricated DA analyses."""
import json,os,re,datetime,urllib.parse,urllib.request,xml.etree.ElementTree as ET,html
from email.utils import parsedate_to_datetime
ROOT=os.path.dirname(__file__)
sources=json.load(open(os.path.join(ROOT,'data/sources.json'),encoding='utf8'))
old=json.load(open(os.path.join(ROOT,'data/feed.json'),encoding='utf8'))
items={x['url']:x for x in old.get('items',[]) if x.get('url')}
HEAD={'User-Agent':'Mozilla/5.0 (compatible; RADARDA/1.0; editorial research)'}
def clean(s):return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',html.unescape(s or ''))).strip()[:450]
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
  if link.startswith('http') and title:entries.append(dict(title=title,url=link,published=date(val('pubDate','{http://www.w3.org/2005/Atom}published','{http://www.w3.org/2005/Atom}updated')),summary=clean(val('description','{http://www.w3.org/2005/Atom}summary'))))
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
    items[x['url']]=x
   break
 checked+=1
print('Checked',checked,'feeds found',len(working),'items',len(items))
result={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'collected_unreviewed','working_feeds':working,'items':sorted(items.values(),key=lambda x:x.get('published',''),reverse=True)[:400]}
with open(os.path.join(ROOT,'data/feed.json'),'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
