import collections,datetime as dt,json,pathlib,sys,xml.etree.ElementTree as ET
from audit_sports import entries,public_url
from supplement_guide import xmltime

DATA=pathlib.Path(__file__).resolve().parents[1]/'data'

def validate(folder=DATA,playlist_name='p.m3u',guide_name='g.xml'):
 text=(folder/playlist_name).read_text(encoding='utf-8')
 channels=entries(text)
 assert text.startswith('#EXTM3U'), 'Playlist header missing'
 assert 'https://redonesmf.github.io/tv-feed/g.xml' in text.splitlines()[0], 'Guide URL is incorrect'
 assert len(channels)>=100, 'Unexpectedly small channel list; preserving published feed'
 ids=[e['id'] for e in channels]
 assert len(set(ids))==len(ids), 'Duplicate channel IDs'
 assert len({e['url'] for e in channels})==len(channels), 'Duplicate channel URLs'
 assert all(public_url(e['url']) for e in channels), 'Non-public or credential-bearing channel URL'
 assert '192.168.4.' not in text, 'Local network address must not be published'
 required={'SkySportsPremierLeague.uk@SD','SkySportsAction.uk@SD','BBCNews.uk@NorthAmerica'}
 retained=pathlib.Path(__file__).resolve().parents[1]/'config/retained-channels.m3u'
 if retained.exists(): required.update(e['id'] for e in entries(retained.read_text(encoding='utf-8')))
 assert required.issubset(ids), 'An existing curated or requested channel is missing'
 root=ET.parse(folder/guide_name).getroot()
 guide_ids={n.get('id') for n in root.findall('channel')}
 assert set(ids)==guide_ids, 'Guide and playlist channel IDs differ'
 programmes=root.findall('programme')
 assert len(programmes)>=500, 'Guide download is incomplete; preserving published feed'
 assert all(p.get('channel') in guide_ids for p in programmes), 'Guide has unknown channel references'
 assert all(p.findtext('title','').casefold() not in {'','no data','no information','tba'} for p in programmes), 'Guide contains placeholder programmes'
 covered={p.get('channel') for p in programmes}
 assert {'SkySportsPremierLeague.uk@SD','SkySportsAction.uk@SD'}.issubset(covered), 'Sky programme data is missing; preserving published feed'
 assert len(covered)>=130, 'Guide coverage has regressed; preserving published feed'
 by_channel=collections.defaultdict(list)
 for p in programmes:
  start,stop=xmltime(p.get('start')),xmltime(p.get('stop'))
  assert start and stop and start<stop, 'Invalid programme time'
  by_channel[p.get('channel')].append((start,stop))
 for slots in by_channel.values():
  slots.sort()
  assert all(a[1]<=b[0] for a,b in zip(slots,slots[1:])), 'Duplicate or overlapping programme listings'
 coverage=json.loads((folder/'coverage.json').read_text(encoding='utf-8'))
 assert {c['id'] for c in coverage['channels']}==set(ids), 'Coverage report has different channels'
 built=dt.datetime.fromisoformat(coverage['built_at'])
 upcoming={ident for ident,slots in by_channel.items() if any(stop>built and start<built+dt.timedelta(hours=24) for start,stop in slots)}
 assert upcoming=={c['id'] for c in coverage['channels'] if c['next_24h']}, 'Coverage report is incorrect'
 guide_only='Guide-Only.m3u' if playlist_name=='Sports-Checked.m3u' else 'guide.m3u'
 focused=entries((folder/guide_only).read_text(encoding='utf-8'))
 assert {c['id'] for c in focused}==upcoming, 'Guide-only playlist includes missing listings'
 original={c['id']:c['url'] for c in channels}
 assert all(original[c['id']]==c['url'] for c in focused), 'Guide-only playlist changed a stream'
 result={'channels':len(channels),'channels_with_guide':len(covered),'programmes':len(programmes),'groups':sorted({e['attrs']['group-title'] for e in channels}),'validation':'passed'}
 return result

if __name__=='__main__':
 print(json.dumps(validate(),indent=2))
