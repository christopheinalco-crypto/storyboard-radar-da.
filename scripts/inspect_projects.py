#!/usr/bin/env python3
"""Enrich RADAR DA discoveries by opening actual project pages. Never auto-publish."""
import concurrent.futures
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DATA=Path(__file__).resolve().parents[1]/"data"
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; RADARDAResearch/2.0)"}
LIMIT=160

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta={}
        self.title=""
        self.in_title=False
        self.text=[]
        self.in_body=False
        self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="meta":
            key=a.get("property") or a.get("name")
            if key and a.get("content"):self.meta[key.lower()]=a["content"].strip()
        if tag=="title":self.in_title=True
        if tag=="body":self.in_body=True
        if tag in ("script","style","nav","footer"):self.skip+=1
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
        if tag in ("script","style","nav","footer"):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if self.in_title:self.title+=data
        if self.in_body and not self.skip:
            t=" ".join(data.split())
            if len(t)>25:self.text.append(t)

def inspect(item):
    url=item["url"]
    out={**item,"inspected_at":NOW}
    try:
        req=Request(url,headers=HEADERS)
        with urlopen(req,timeout=10) as response:
            final=response.url
            typ=response.headers.get("Content-Type","")
            raw=response.read(350000)
        if "html" not in typ.lower():
            raise ValueError("non-HTML response")
        parser=Metadata()
        parser.feed(raw.decode("utf-8","replace"))
        m=parser.meta
        title=html.unescape(m.get("og:title") or m.get("twitter:title") or parser.title).strip()
        image=m.get("og:image") or m.get("twitter:image") or ""
        date=next((m[k] for k in ("article:published_time","datepublished","date","article:modified_time") if m.get(k)),"")
        description=html.unescape(m.get("og:description") or m.get("description") or "").strip()
        out.update({"status":"page_inspected","final_url":final,"page_title":title[:220],
            "description":description[:900],"published_date_claim":date[:40],
            "image_candidate":urljoin(final,image) if image else "",
            "image_verified":False,"page_excerpt":" ".join(parser.text)[:2200],
            "needs_editorial_review":True})
    except Exception as e:
        out.update({"status":"inspection_failed","error":str(e)[:180]})
    return out

def main():
    shortlist=json.loads((DATA/"editorial-shortlist.json").read_text(encoding="utf-8"))
    candidates=shortlist.get("items",[])[:LIMIT]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results=list(pool.map(inspect,candidates))
    ok=sum(x["status"]=="page_inspected" for x in results)
    with_image=sum(bool(x.get("image_candidate")) for x in results)
    report={"updated_at":NOW,"attempted":len(results),"opened":ok,
        "failed":len(results)-ok,"image_candidates":with_image,
        "warning":"Images are candidates only, not tested for rendering or reuse. Editorial scores /20 and publication require review.",
        "items":results}
    (DATA/"project-inspections.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"RADAR DA project inspections: {ok}/{len(results)} pages opened; {with_image} image candidates")

if __name__=="__main__":main()
