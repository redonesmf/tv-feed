"""Match streaming guides by native stream ID or a reviewed, URL-guarded alias.

Never infer a schedule from a similar channel name or a channel's country suffix:
several UK playlist entries actually carry Australian or New Zealand streams.
"""
import collections
import copy
import datetime as dt
import gzip
import json
import re
import urllib.request
import xml.etree.ElementTree as ET

from audit_sports import CACHE, ROOT

SOURCES = {'pluto': 'PlutoTV', 'samsung': 'SamsungTVPlus', 'roku': 'Roku'}
PLACEHOLDERS = {'', 'no data', 'no information', 'tba', 'to be announced'}


def xmltime(value):
    try:
        return dt.datetime.strptime(value, '%Y%m%d%H%M%S %z')
    except (ValueError, TypeError):
        return None


def reviewed_mappings():
    return json.loads((ROOT.parent / 'config/guide-mappings.json').read_text(encoding='utf-8'))


def mapping_for(entry, mappings):
    # The native ID identifies the precise Pluto region/feed, even after a rename.
    native = re.search(r'^https://jmp2\.uk/plu-([a-f0-9]{24})\.m3u8(?:\?|$)', entry['url'])
    if native:
        return {'source': 'pluto', 'id': native[1], 'reason': 'Native Pluto stream ID'}
    mapping = mappings.get(entry['id'])
    if mapping and mapping['stream_contains'] in entry['url']:
        return mapping
    return None


def cached_supplement(source, now):
    path = CACHE / f'supplement-{source}.xml.gz'
    if path.exists() and now.timestamp() - path.stat().st_mtime < 1800:
        return path
    url = f'https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/{SOURCES[source]}/all.xml.gz'
    temporary = path.with_suffix('.gz.tmp')
    try:
        with urllib.request.urlopen(url, timeout=30) as response, temporary.open('wb') as dest:
            size = 0
            while chunk := response.read(262144):
                size += len(chunk)
                if size > 35_000_000:
                    raise ValueError('Supplement exceeds download limit')
                dest.write(chunk)
        # A partial/non-gzip download must not become the cached copy.
        with gzip.open(temporary, 'rb') as stream:
            for _, node in ET.iterparse(stream, events=('end',)):
                node.clear()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def read_programmes(path, targets, start, end):
    result = collections.defaultdict(list)
    with gzip.open(path, 'rb') as stream:
        context = ET.iterparse(stream, events=('start', 'end'))
        _, root = next(context)
        for event, node in context:
            if event != 'end' or node.tag not in ('channel', 'programme'):
                continue
            if node.tag == 'programme' and node.get('channel') in targets:
                title = ' '.join(node.findtext('title', '').split())
                begin, stop = xmltime(node.get('start')), xmltime(node.get('stop'))
                if title.casefold() not in PLACEHOLDERS and begin and stop and begin < stop and stop > start and begin < end:
                    for target in targets[node.get('channel')]:
                        clone = copy.deepcopy(node)
                        clone.set('channel', target)
                        result[target].append(clone)
            root.remove(node)
    return result


def normalize(nodes):
    """Discard duplicates/overlaps, keeping one real programme per time slot."""
    result = []
    last_stop = None
    for node in sorted(nodes, key=lambda n: (xmltime(n.get('start')) or dt.datetime.min.replace(tzinfo=dt.timezone.utc), xmltime(n.get('stop')) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))):
        begin, stop = xmltime(node.get('start')), xmltime(node.get('stop'))
        if not begin or not stop or begin >= stop or (last_stop and begin < last_stop):
            continue
        result.append(node)
        last_stop = stop
    return result


def add_supplements(tree, checked, mappings, now, start, end, errors):
    targets = collections.defaultdict(lambda: collections.defaultdict(list))
    provenance = {}
    for entry in checked:
        match = mapping_for(entry, mappings)
        if match and match['source'] in SOURCES:
            targets[match['source']][match['id']].append(entry['id'])
            provenance[entry['id']] = dict(source=match['source'], guide_id=match['id'], reason=match['reason'])
    replacements = {}
    for source, ids in targets.items():
        try:
            parsed = read_programmes(cached_supplement(source, now), ids, start, end)
            # A stale guide cannot replace a still-usable existing schedule.
            fresh = {target: normalize(nodes) for target, nodes in parsed.items()
                     if any(xmltime(n.get('stop')) > now and xmltime(n.get('start')) < now + dt.timedelta(hours=24) for n in nodes)}
            replacements.update(fresh)
            print(f'{source}: {len(fresh)} feeds matched by stream identity', flush=True)
        except Exception as exc:
            errors.append({'source': source, 'error': str(exc)[:200]})
    for node in list(tree):
        if node.tag == 'programme' and node.get('channel') in replacements:
            tree.remove(node)
    for nodes in replacements.values():
        tree.extend(nodes)
    return {target: provenance[target] for target in replacements}
