import collections, copy, datetime as dt, gzip, json, pathlib, re, urllib.request, os
import xml.etree.ElementTree as ET
from audit_sports import ROOT, CACHE, OUT, entries,load_sources

NOW=dt.datetime.now(dt.timezone.utc)
START=NOW-dt.timedelta(hours=12)
END=NOW+dt.timedelta(days=7)

def key(value):
    return value.split('@',1)[0].casefold()

def xmltime(value):
    try: return dt.datetime.strptime(value[:20],'%Y%m%d%H%M%S %z')
    except ValueError: return None

def cached_guide(country):
    local=CACHE/f'epg-{country}.xml'
    compressed=CACHE/f'epg-{country}.xml.gz'
    if local.exists() and NOW.timestamp()-local.stat().st_mtime>43200:
        local.unlink()
    if compressed.exists() and NOW.timestamp()-compressed.stat().st_mtime>43200:
        compressed.unlink()
    if local.exists(): return local
    if not compressed.exists():
        url=f'https://iptv-epg.org/files/epg-{country}.xml.gz'
        print(f'Downloading guide: {country}',flush=True)
        with urllib.request.urlopen(url,timeout=15) as response, compressed.open('wb') as dest:
            while chunk:=response.read(262144): dest.write(chunk)
    return compressed

def build():
    all_entries=load_sources()
    health=json.loads((OUT/'channel-health.json').read_text(encoding='utf-8'))
    status={(c['id'],c['url']):c for c in health['channels']}
    candidates=[e for e in all_entries if (status.get((e['id'],e['url']),{}).get('status')=='media_responded' or 'Extra' in e['sources'] or 'Retained' in e['sources'])]
    def rank(entry):
        result=status.get((entry['id'],entry['url']),{})
        quality=re.search(r'\((\d+)p\)',entry['name'])
        return (result.get('status')=='media_responded','video_probe' in result,int(quality.group(1)) if quality else 0)
    unique={}
    for entry in sorted(candidates,key=rank,reverse=True):
        identity=entry['id'] or entry['url']
        if identity not in unique: unique[identity]=entry
        else:
            unique[identity]['sources']=list(dict.fromkeys(unique[identity]['sources']+entry['sources']))
    seen_urls=set(); checked=[]
    for entry in unique.values():
        if entry['url'] not in seen_urls:
            seen_urls.add(entry['url']); checked.append(entry)
    targets=collections.defaultdict(list)
    for e in checked: targets[key(e['id'])].append(e['id'])
    country_counts=collections.Counter(key(e['id']).rsplit('.',1)[-1] for e in checked)
    available={'al','ar','am','au','at','bs','by','be','bo','ba','br','bg','ca','cl','co','cr','hr','cw','cz','dk','do','ec','sv','fi','fr','ge','de','gh','gr','gt','hn','hk','hu','is','in','id','il','it','jm','jp','lv','lt','lu','my','mt','mx','nl','nz','ng','no','pk','pa','py','pe','ph','pl','pt','ro','ru','rs','sg','za','kr','es','se','ch','tw','th','tt','tr','ug','ua','gb','us','uy','ve','zw'}
    aliases={'uk':'gb'}
    countries=[aliases.get(c,c) for c,n in country_counts.most_common() if aliases.get(c,c) in available]
    # Only fetch countries represented by checked channels; omit unrelated guide data.
    countries=list(dict.fromkeys(countries))
    tree=ET.Element('tv',{'generator-info-name':'Sports TV matched guide','source-info-name':'IPTV-EPG.org'})
    programmes=collections.Counter(); channel_nodes={}; errors=[]
    for country in countries:
        try:
            path=cached_guide(country)
            stream=gzip.open(path,'rb') if path.suffix=='.gz' else path.open('rb')
            local_count=0
            with stream:
                context=ET.iterparse(stream,events=('start','end'))
                _,root=next(context)
                for event,node in context:
                    if event!='end': continue
                    if node.tag=='channel':
                        for target in targets.get(key(node.get('id','')),[]):
                            clone=copy.deepcopy(node); clone.set('id',target)
                            channel_nodes[target]=clone
                        root.remove(node)
                    elif node.tag=='programme':
                        matched=targets.get(key(node.get('channel','')),[])
                        title=' '.join(node.findtext('title','').split())
                        begin=xmltime(node.get('start','')); end=xmltime(node.get('stop',''))
                        if matched and title.casefold() not in {'','no data','no information','tba','to be announced'} and begin and end and end>START and begin<END:
                            for target in matched:
                                clone=copy.deepcopy(node); clone.set('channel',target)
                                tree.append(clone); programmes[target]+=1; local_count+=1
                        root.remove(node)
            print(f'{country}: {local_count} matching programmes',flush=True)
        except Exception as exc:
            errors.append({'country':country,'error':str(exc)[:200]})
            print(f'{country}: guide unavailable: {exc}',flush=True)
    # Add every checked channel before programme elements, so unmatched channels stay usable.
    for index,e in enumerate(checked):
        node=channel_nodes.get(e['id'])
        if node is None:
            node=ET.Element('channel',{'id':e['id']})
            ET.SubElement(node,'display-name').text=e['name']
            if e['logo']: ET.SubElement(node,'icon',{'src':e['logo']})
        tree.insert(index,node)
    xml=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    (OUT/'guide.xml.tmp').write_bytes(xml)
    (OUT/'guide.xml.tmp').replace(OUT/'guide.xml')
    with gzip.open(OUT/'guide.xml.gz.tmp','wb') as dest: dest.write(xml)
    (OUT/'guide.xml.gz.tmp').replace(OUT/'guide.xml.gz')
    matched=set(programmes)
    football_terms=('setanta','beinsports','premiersports','sporttv','football','futbol','futebol','fifa','golazo','mutv','lfctv','skysportspremierleague')
    def is_football(e): return any(term in e['id'].casefold() for term in football_terms)
    ordered=sorted(checked,key=lambda e:(0 if is_football(e) else (1 if 'Extra' in e['sources'] else (2 if 'UK' in e['sources'] else 3)),e['id'] not in matched,e['name'].casefold()))
    def playlist(items):
        lines=['#EXTM3U x-tvg-url="'+os.environ.get('PUBLIC_FEED_BASE_URL','https://redonesmf.github.io/tv-feed').rstrip('/')+'/g.xml"']
        for e in items:
            group='Football channels' if is_football(e) else ('BBC and Sky' if 'Extra' in e['sources'] else ('UK channels' if 'UK' in e['sources'] else ('Sports with guide' if e['id'] in matched else 'More sports - guide unavailable')))
            lines.append(f'#EXTINF:-1 tvg-id="{e["id"]}" tvg-logo="{e["logo"]}" group-title="{group}",{e["name"]}')
            for opt,value in e['opts'].items(): lines.append(f'#EXTVLCOPT:{opt}={value}')
            lines.append(e['url'])
        return '\n'.join(lines)+'\n'
    (OUT/'Sports-Checked.m3u.tmp').write_text(playlist(ordered),encoding='utf-8')
    (OUT/'Sports-Checked.m3u.tmp').replace(OUT/'Sports-Checked.m3u')
    cloud_verified=sum(status.get((e['id'],e['url']),{}).get('status')=='media_responded' for e in checked)
    summary={'built_at':NOW.isoformat(),'source_candidates':len(all_entries),'playlist_channels':len(checked),'media_responding_from_updater':cloud_verified,'retained_without_current_cloud_verification':len(checked)-cloud_verified,'uk_channels':sum('UK' in e['sources'] for e in checked),'duplicates_removed':len(candidates)-len(checked),'channels_with_programmes':len(matched),'programme_count':sum(programmes.values()),'guide_countries':countries,'guide_errors':errors,'guide_coverage':[{'id':e['id'],'name':e['name'],'sources':e['sources'],'programmes':programmes[e['id']]} for e in ordered]}
    (OUT/'guide-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='guide_coverage'},ensure_ascii=False),flush=True)

if __name__=='__main__': build()
