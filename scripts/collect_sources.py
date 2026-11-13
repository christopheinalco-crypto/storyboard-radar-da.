#!/usr/bin/env python3
"""RADAR DA: independent source coverage audit and discovery. No unreviewed publishing."""
import concurrent.futures
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; RADARDAResearch/1.0; editorial discovery)"}
PRIORITY_CATEGORIES={"01 Spectacle Concert","02 TV Broadcast","09 France Pro","14 Musique Clips","15 Danse Performance"}
LIMIT=100

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.in_title=False;self.title=""
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="a":
            href=attrs.get("href","")
            if href.startswith("http") and href not in self.links:self.links.append(href)
        if tag=="title":self.in_title=True
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title+=data

def inspect(entry):
    url=entry.get("url","")
    result={"name":entry.get("name"),"url":url,"category":entry.get("category"),"priority":entry.get("priority"),"checked_at":NOW}
    try:
        req=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=9) as response:
            raw=response.read(180000)
            result["http_status"]=response.status
            result["final_url"]=response.url
            result["content_type"]=response.headers.get("Content-Type","")
        parser=Links()
        if b"<html" in raw[:10000].lower() or "html" in result["content_type"]:
            parser.feed(raw.decode("utf-8","replace"))
        else:
            # XML feeds: collect linked articles, excluding the source homepage.
            parser.links=re.findall(r"<link[^>]*>(https?[^<]+)</link>",raw.decode("utf-8","replace"),re.I)[:30]
        result["page_title"]=html.unescape(parser.title.strip())[:180]
        result["links_found"]=len(parser.links)
        result["sample_links"]=parser.links[:8]
        result["status"]="opened" if 200<=response.status<400 else "http_error"
    except Exception as e:
        result["status"]="error";result["error"]=str(e)[:240]
    return result

def main():
    sources=json.loads((DATA/"sources.json").read_text(encoding="utf-8"))
    previous_path=DATA/"source-coverage.json"
    try:previous=json.loads(previous_path.read_text(encoding="utf-8"))
    except (FileNotFoundError,ValueError):previous={}
    # Prioritize unseen sources over repeatedly checking the same few.
    history=previous.get("last_checked_by_url",{})
    ordered=sorted(sources,key=lambda x:(0 if x.get("category") in PRIORITY_CATEGORIES else 1,
        0 if x.get("priority")=="P1" else 1 if x.get("priority")=="P2" else 2,
        history.get(x.get("url"),"")))
    # Rotate start between executions by day/hour, preserving coverage of priority sectors.
    hour=dt.datetime.now(dt.timezone.utc).hour
    offset=(dt.datetime.now(dt.timezone.utc).toordinal()*4+hour//6)%len(ordered)
    selected=(ordered[offset:]+ordered[:offset])[:LIMIT]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results=list(pool.map(inspect,selected))
    for item in results:history[item["url"]]=NOW
    opened=sum(r["status"]=="opened" for r in results)
    audit={"checked_at":NOW,"catalogue_total":len(sources),"target":LIMIT,
        "attempted":len(results),"opened_successfully":opened,
        "failed":len(results)-opened,"target_met":opened>=LIMIT,
        "last_checked_by_url":history,"results":results}
    previous_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Discovery only; no rights-uncleared photos or unreviewed articles get published.
    existing=set()
    for file in ("feed.json","published-projects.json"):
        try:
            data=json.loads((DATA/file).read_text(encoding="utf-8"))
            for item in data.get("items",data.get("projects",[])):
                if isinstance(item,dict):existing.add(item.get("url"))
        except (FileNotFoundError,ValueError):pass
    candidates=[]
    for result in results:
        if result["status"]!="opened":continue
        for url in result.get("sample_links",[]):
            if url not in existing and url not in [x["url"] for x in candidates]:
                candidates.append({"url":url,"source":result["name"],"source_category":result["category"],
                    "status":"unverified_discovery","found_at":NOW})
    (DATA/"source-discoveries.json").write_text(json.dumps({"updated_at":NOW,
        "warning":"Links are unverified; not articles ready for publication.",
        "items":candidates[:400]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"RADAR DA: {opened}/{len(results)} opened; {len(results)-opened} errors; {len(candidates)} discovered links")
    if opened<LIMIT:print("COVERAGE FAILURE: fewer than 100 sources successfully opened")

if __name__=="__main__":main()
