import concurrent.futures, datetime as dt, json, pathlib, re, socket, time, zlib
import urllib.request, urllib.error, urllib.parse, ipaddress, hashlib

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT.parent / '.cache'
CACHE.mkdir(parents=True, exist_ok=True)
OUT = CACHE / 'build'
OUT.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'

def entries(text):
    result = []
    for block in re.split(r'(?=^#EXTINF:)', text, flags=re.M)[1:]:
        lines = block.strip().splitlines()
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', lines[0]))
        urls = [x.strip() for x in lines[1:] if x.strip() and not x.startswith('#')]
        if not urls:
            continue
        opts = dict(re.findall(r'^#EXTVLCOPT:([^=]+)=(.*)$', block, re.M))
        name = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', lines[0], maxsplit=1)[1]
        result.append(dict(id=attrs.get('tvg-id',''), name=name,
            logo=attrs.get('tvg-logo',''), url=urls[0], attrs=attrs, opts=opts))
    return result

def public_url(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: return False
        if p.hostname.lower() in {'localhost','localhost.localdomain'}: return False
        if re.search(r'/live/[^/]+/[^/]+/\d+',p.path): return False
        if any(k.lower() in {'username','password','passwd','api_key','apikey','authorization'} for k,v in urllib.parse.parse_qsl(p.query)): return False
        try:
            if not ipaddress.ip_address(p.hostname).is_global: return False
        except ValueError: pass
        return True
    except ValueError: return False

def load_sources():
    merged={}
    for filename,label in [('sports-latest.m3u','Sports'),('uk-latest.m3u','UK'),('extra-latest.m3u','Extra')]:
        path=CACHE/filename
        if not path.exists(): continue
        for entry in entries(path.read_text(encoding='utf-8-sig')):
            if not public_url(entry['url']): continue
            if not entry['id']: entry['id']='Unmapped'+hashlib.sha256(entry['url'].encode()).hexdigest()[:16]+'.invalid'
            ident=(entry['id'],entry['url'])
            if ident in merged:
                merged[ident]['sources'].append(label)
            else:
                entry['sources']=[label]
                merged[ident]=entry
    return list(merged.values())

def fetch(url, headers, limit=262144):
    if not public_url(url): raise ValueError('Only public HTTP(S) media URLs are allowed')
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        body=response.read(limit)
        encoding=response.headers.get('Content-Encoding','').lower()
        if encoding=='gzip' or body.startswith(b'\x1f\x8b'):
            body=zlib.decompressobj(16+zlib.MAX_WBITS).decompress(body,limit)
        elif encoding=='deflate':
            body=zlib.decompressobj().decompress(body,limit)
        return body, response.geturl(), response.headers.get('Content-Type','')

def audit(entry):
    start = time.monotonic()
    result = {k:entry[k] for k in ('id','name','url')}
    headers = {'User-Agent':entry['opts'].get('http-user-agent',entry['attrs'].get('http-user-agent',UA))}
    referer = entry['opts'].get('http-referrer',entry['attrs'].get('http-referrer'))
    if referer:
        headers['Referer'] = referer
    try:
        url = entry['url']
        for depth in range(4):
            body, final_url, content_type = fetch(url, headers)
            text = body.decode('utf-8-sig', errors='replace')
            if not text.lstrip().startswith('#EXTM3U'):
                if body and (body[0] == 0x47 or body.startswith(b'FLV') or b'ftyp' in body[:32]):
                    result.update(status='media_responded', media_url=final_url)
                    break
                result.update(status='unexpected_content', detail=content_type)
                break
            lines = text.splitlines()
            variants=[]
            for i,line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF:') and i+1<len(lines):
                    band = re.search(r'(?<!-)BANDWIDTH=(\d+)',line)
                    variants.append((int(band.group(1)) if band else 0, lines[i+1]))
            if variants:
                url = urllib.parse.urljoin(final_url, sorted(variants)[0][1])
                continue
            segments=[x for x in lines if x and not x.startswith('#')]
            if not segments:
                result.update(status='empty_playlist')
                break
            segment = urllib.parse.urljoin(final_url, segments[-1])
            chunk, segment_final, segment_type = fetch(segment,headers,8192)
            if not chunk or b'<html' in chunk[:100].lower():
                result.update(status='invalid_media',detail=segment_type)
            elif chunk[0] == 0x47 or any(atom in chunk[:512] for atom in (b'styp',b'moof',b'ftyp',b'mdat')) or '#EXT-X-MAP:' in text:
                result.update(status='media_responded', media_url=final_url)
            else:
                result.update(status='unverified_media',detail=segment_type)
            break
        else:
            result.update(status='playlist_nesting_limit')
    except urllib.error.HTTPError as exc:
        result.update(status=f'http_{exc.code}')
    except Exception as exc:
        result.update(status='unreachable',detail=str(exc)[:160])
    result['seconds'] = round(time.monotonic()-start,2)
    return result

def main():
    items=load_sources()
    results=[]
    print(f'Auditing {len(items)} channels with four workers; media reads capped at 8 KiB.',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(audit,e):e for e in items}
        for future in concurrent.futures.as_completed(futures):
            result=future.result(); results.append(result)
            if len(results)%20==0 or len(results)==len(items):
                print(f'{len(results)}/{len(items)} checked; {sum(x["status"]=="media_responded" for x in results)} returned media.',flush=True)
                (CACHE/'audit-progress.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'HLS manifest plus up to 8 KiB from one current media segment; no location or authentication bypass; no retries on rejected requests','channels':results}
    (OUT/'channel-health.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Audit complete.',flush=True)

if __name__=='__main__': main()
