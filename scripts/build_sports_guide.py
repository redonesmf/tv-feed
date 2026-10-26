import argparse, collections, copy, datetime as dt, gzip, json, pathlib, re, urllib.request, os
import xml.etree.ElementTree as ET
from audit_sports import ROOT, CACHE, OUT, entries,load_sources
from supplement_guide import reviewed_mappings, mapping_for, add_supplements, normalize
from daily_view import render_daily

NOW=dt.datetime.now(dt.timezone.utc)
START=NOW-dt.timedelta(hours=12)
END=NOW+dt.timedelta(days=7)

def key(value):
    return value.split('@',1)[0].casefold()

def xmltime(value):
    try: return dt.datetime.strptime(value[:20],'%Y%m%d%H%M%S %z')
    except ValueError: return None

def is_football(entry):
    terms=('setanta','beinsports','premiersports','sporttv','football','futbol','futebol','fifa','golazo','mutv','lfctv','skysportspremierleague')
    return any(term in entry['id'].casefold() for term in terms)

def nfl_group_for(spec, has_guide):
    group='NFL game broadcasters' if spec['role']=='game broadcaster' else 'NFL news and replays'
    return group if has_guide else group+' - guide unavailable'

def group_for(entry, matched, uk_main, nfl_view=None):
    if entry['id'] in uk_main:
        return 'UK main channels' if entry['id'] in matched else 'UK main - guide unavailable'
    if nfl_view and entry['id'] in nfl_view:
        return nfl_group_for(nfl_view[entry['id']],entry['id'] in matched)
    if entry['id'] in matched:
        if is_football(entry): return 'Football with guide'
        if 'Extra' in entry['sources']: return 'BBC and Sky'
        return 'UK with guide' if 'UK' in entry['sources'] else 'Sports with guide'
    if is_football(entry): return 'Football - guide unavailable'
    return 'UK - guide unavailable' if 'UK' in entry['sources'] else 'More channels - guide unavailable'

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

def snapshot_entries():
    data=ROOT.parent/'data'
    rows=entries((data/'p.m3u').read_text(encoding='utf-8'))
    report={c['id']:c for c in json.loads((data/'coverage.json').read_text(encoding='utf-8'))['channels']}
    originals={e['id']:e for name in ['retained-channels.m3u','extra-channels.m3u'] for e in entries((ROOT.parent/'config'/name).read_text(encoding='utf-8'))}
    extra_ids={e['id'] for e in entries((ROOT.parent/'config/extra-channels.m3u').read_text(encoding='utf-8'))}
    for e in rows:
        group=originals.get(e['id'],e)['attrs'].get('group-title','')
        e['sources']=['Retained','Extra'] if e['id'] in extra_ids else (report.get(e['id'],{}).get('source_labels') or ['Retained','UK' if group=='UK channels' else ('Extra' if group.startswith('BBC and Sky') else 'Sports')])
    return rows


def build(snapshot=False,reuse_audit=False):
    all_entries=snapshot_entries() if snapshot else load_sources()
    health={'channels':[]} if snapshot else json.loads((OUT/'channel-health.json').read_text(encoding='utf-8'))
    status={(c['id'],c['url']):c for c in health['channels']}
    candidates=[e for e in all_entries if (status.get((e['id'],e['url']),{}).get('status')=='media_responded' or 'Extra' in e['sources'] or 'Retained' in e['sources'])]
    configured=entries((ROOT.parent/'config/extra-channels.m3u').read_text(encoding='utf-8'))
    curated={(e['id'],e['url']) for e in configured}
    uk_main={e['id'] for e in configured if e['attrs'].get('group-title')=='UK main channels'}
    uk_order={e['id']:i for i,e in enumerate(configured) if e['id'] in uk_main}
    nfl_rows=json.loads((ROOT.parent/'config/nfl-view.json').read_text(encoding='utf-8'))
    nfl_view={e['id']:e for e in nfl_rows}
    nfl_order={e['id']:i for i,e in enumerate(nfl_rows)}
    def rank(entry):
        result=status.get((entry['id'],entry['url']),{})
        quality=re.search(r'\((\d+)p\)',entry['name'])
        # Explicit additions keep their decoded/identity-checked URL, rather than
        # switching to another regional stream that happens to pass a cloud probe.
        return ((entry['id'],entry['url']) in curated,result.get('status')=='media_responded','video_probe' in result,int(quality.group(1)) if quality else 0)
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
    mappings=reviewed_mappings()
    targets=collections.defaultdict(list)
    extra_countries=[]; provenance={}
    for e in checked:
        match=mapping_for(e,mappings)
        source_id=match['id'] if match and match['source']=='primary' else e['id']
        targets[key(source_id)].append(e['id'])
        if match and match['source']=='primary':
            extra_countries.append(match['country'])
            provenance[e['id']]={'source':'IPTV-EPG.org','guide_id':source_id,'reason':match['reason']}

    country_counts=collections.Counter(key(e['id']).rsplit('.',1)[-1] for e in checked)
    available={'al','ar','am','au','at','bs','by','be','bo','ba','br','bg','ca','cl','co','cr','hr','cw','cz','dk','do','ec','sv','fi','fr','ge','de','gh','gr','gt','hn','hk','hu','is','in','id','il','it','jm','jp','lv','lt','lu','my','mt','mx','nl','nz','ng','no','pa','py','pe','ph','pl','pt','ro','ru','rs','sg','za','kr','es','se','ch','tw','th','tt','tr','ug','ua','gb','us','uy','ve','zw'}
    aliases={'uk':'gb'}
    countries=[aliases.get(c,c) for c,n in country_counts.most_common() if aliases.get(c,c) in available]
    # Only fetch countries represented by checked channels; omit unrelated guide data.
    countries=list(dict.fromkeys(countries+extra_countries))
    tree=ET.Element('tv',{'generator-info-name':'Sports TV matched guide','source-info-name':'IPTV-EPG.org; matthuisman/i.mjh.nz'})
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
                        if not matched:
                            root.remove(node)
                            continue
                        title=' '.join(node.findtext('title','').split())
                        begin=xmltime(node.get('start','')); end=xmltime(node.get('stop',''))
                        if matched and title.casefold() not in {'','no data','no information','tba','to be announced'} and begin and end and begin<end and end>START and begin<END:
                            for target in matched:
                                clone=copy.deepcopy(node); clone.set('channel',target)
                                tree.append(clone); programmes[target]+=1; local_count+=1
                        root.remove(node)
            print(f'{country}: {local_count} matching programmes',flush=True)
        except Exception as exc:
            errors.append({'country':country,'error':str(exc)[:200]})
            print(f'{country}: guide unavailable: {exc}',flush=True)
    provenance.update(add_supplements(tree,checked,mappings,NOW,START,END,errors))
    # One non-overlapping schedule per stable playlist ID. Track fresh coverage,
    # rather than calling a channel covered because it has only yesterday's data.
    by_channel=collections.defaultdict(list)
    for node in list(tree):
        by_channel[node.get('channel')].append(node)
        tree.remove(node)
    programmes=collections.Counter(); current=set(); upcoming=set()
    coverage=[]
    for e in checked:
        nodes=normalize(by_channel[e['id']])
        tree.extend(nodes); programmes[e['id']]=len(nodes)
        if any(xmltime(n.get('start'))<=NOW<xmltime(n.get('stop')) for n in nodes): current.add(e['id'])
        if any(xmltime(n.get('stop'))>NOW and xmltime(n.get('start'))<NOW+dt.timedelta(hours=24) for n in nodes): upcoming.add(e['id'])
        coverage.append({'id':e['id'],'name':e['name'],'source_labels':e['sources'],'programmes':len(nodes),'on_now':e['id'] in current,'next_24h':e['id'] in upcoming,**provenance.get(e['id'],{'source':'IPTV-EPG.org' if nodes else None})})
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
    matched=upcoming
    def topic_rank(entry):
        if entry['id'] in uk_main: return 0
        if entry['id'] in nfl_view: return 1 if nfl_view[entry['id']]['role']=='game broadcaster' else 2
        return 3 if is_football(entry) else (4 if 'Extra' in entry['sources'] else (5 if 'UK' in entry['sources'] else 6))
    ordered=sorted(checked,key=lambda e:(e['id'] not in matched,topic_rank(e),uk_order.get(e['id'],999),nfl_order.get(e['id'],999),e['name'].casefold()))
    def playlist(items,nfl_only=False):
        lines=['#EXTM3U x-tvg-url="'+os.environ.get('PUBLIC_FEED_BASE_URL','https://redonesmf.github.io/tv-feed').rstrip('/')+'/g.xml"']
        for e in items:
            spec=nfl_view.get(e['id'])
            group=nfl_group_for(spec,e['id'] in matched) if nfl_only else group_for(e,matched,uk_main,nfl_view)
            label=spec.get('label',e['name']) if spec else e['name']
            lines.append(f'#EXTINF:-1 tvg-id="{e["id"]}" tvg-logo="{e["logo"]}" group-title="{group}",{label}')
            for opt,value in e['opts'].items(): lines.append(f'#EXTVLCOPT:{opt}={value}')
            lines.append(e['url'])
        return '\n'.join(lines)+'\n'
    (OUT/'Sports-Checked.m3u.tmp').write_text(playlist(ordered),encoding='utf-8')
    (OUT/'Sports-Checked.m3u.tmp').replace(OUT/'Sports-Checked.m3u')
    (OUT/'Guide-Only.m3u').write_text(playlist([e for e in ordered if e['id'] in matched]),encoding='utf-8')
    (OUT/'UK-Main.m3u').write_text(playlist([e for e in ordered if e['id'] in uk_main]),encoding='utf-8')
    by_id={e['id']:e for e in checked}
    (OUT/'NFL-Watch.m3u').write_text(playlist([by_id[e['id']] for e in nfl_rows if e['id'] in by_id],nfl_only=True),encoding='utf-8')
    full_text=(OUT/'Sports-Checked.m3u').read_text(encoding='utf-8')
    daily_text,daily_ids,daily_omitted=render_daily(entries(full_text),upcoming,full_text.splitlines()[0])
    (OUT/'Daily-TV.m3u').write_text(daily_text,encoding='utf-8')
    (OUT/'coverage.json').write_text(json.dumps({'built_at':NOW.isoformat(),'channels':coverage},ensure_ascii=False,indent=2),encoding='utf-8')
    cloud_verified=None if snapshot or reuse_audit else sum(status.get((e['id'],e['url']),{}).get('status')=='media_responded' for e in checked)
    previous=json.loads((ROOT.parent/'data/status.json').read_text(encoding='utf-8'))
    last_check=previous.get('last_media_check_at',previous['built_at']) if snapshot or reuse_audit else NOW.isoformat()
    summary={'built_at':NOW.isoformat(),'source_candidates':len(all_entries),'playlist_channels':len(checked),'media_audit_performed':not (snapshot or reuse_audit),'last_media_check_at':last_check,'media_responding_from_updater':cloud_verified,'retained_without_current_cloud_verification':None if snapshot or reuse_audit else len(checked)-cloud_verified,'uk_channels':sum('UK' in e['sources'] or e['id'] in uk_main for e in checked),'nfl_watchlist_channels':len(nfl_view),'nfl_watchlist_with_upcoming_listings':len(set(nfl_view)&upcoming),'uk_main_channels':len(uk_main),'uk_main_with_upcoming_listings':len(uk_main & upcoming),'duplicates_removed':len(candidates)-len(checked),'channels_with_programmes':sum(n>0 for n in programmes.values()),'channels_with_current_programme':len(current),'channels_with_listings_next_24h':len(upcoming),'supplemented_channels':sum(v.get('source') in {'pluto','samsung','roku'} for v in provenance.values()),'programme_count':sum(programmes.values()),'guide_countries':countries,'guide_errors':errors,'guide_coverage':[{'id':e['id'],'name':e['name'],'sources':e['sources'],'programmes':programmes[e['id']]} for e in ordered]}
    summary.update(daily_channels=len(daily_ids),daily_omitted_without_upcoming_guide=daily_omitted)
    (OUT/'guide-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='guide_coverage'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',action='store_true',help='Update guide only; preserve published stream URLs and source labels')
    parser.add_argument('--reuse-audit',action='store_true',help='Do not mark a cached media audit as newly performed')
    args=parser.parse_args()
    build(args.snapshot,args.reuse_audit)
