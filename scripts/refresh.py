"""Refresh only public source data; publish after validation preserves a last-good feed."""
import argparse,json,pathlib,shutil,subprocess,sys,urllib.request
from audit_sports import ROOT,CACHE,OUT
from validate_feed import DATA,validate

def refresh(reuse_audit=False,guide_only=False):
 if not guide_only:
  shutil.copyfile(ROOT.parent/'config/extra-channels.m3u',CACHE/'extra-latest.m3u')
  shutil.copyfile(ROOT.parent/'config/retained-channels.m3u',CACHE/'retained-latest.m3u')
 if not reuse_audit and not guide_only:
  for url,name in [('https://iptv-org.github.io/iptv/categories/sports.m3u','sports-latest.m3u'),('https://iptv-org.github.io/iptv/countries/uk.m3u','uk-latest.m3u')]:
   with urllib.request.urlopen(url,timeout=25) as response: body=response.read(2_000_000)
   if not body.lstrip().startswith(b'#EXTM3U'): raise RuntimeError('Upstream did not return an M3U playlist')
   (CACHE/name).write_bytes(body)
  subprocess.run([sys.executable,str(ROOT/'audit_sports.py')],check=True)
 subprocess.run([sys.executable,str(ROOT/'build_sports_guide.py')]+(['--snapshot'] if guide_only else (['--reuse-audit'] if reuse_audit else [])),check=True)
 result=validate(OUT,'Sports-Checked.m3u','guide.xml')
 summary=json.loads((OUT/'guide-summary.json').read_text(encoding='utf-8'))
 status={k:v for k,v in summary.items() if k!='guide_coverage'}
 status.update(playlist_url='https://redonesmf.github.io/tv-feed/p.m3u',guide_url='https://redonesmf.github.io/tv-feed/g.xml',guide_only_playlist_url='https://redonesmf.github.io/tv-feed/guide.m3u',coverage_url='https://redonesmf.github.io/tv-feed/coverage.json',uk_playlist_url='https://redonesmf.github.io/tv-feed/uk.m3u',nfl_playlist_url='https://redonesmf.github.io/tv-feed/nfl.m3u',validation=result['validation'],source='iptv-org Sports and UK; manually decoded BBC/Sky and UK main-channel additions')
 status['daily_playlist_url']='https://redonesmf.github.io/tv-feed/daily.m3u'
 for old,new in [('Sports-Checked.m3u','p.m3u'),('guide.xml','g.xml'),('Guide-Only.m3u','guide.m3u'),('coverage.json','coverage.json'),('UK-Main.m3u','uk.m3u'),('NFL-Watch.m3u','nfl.m3u'),('Daily-TV.m3u','daily.m3u')]:
  shutil.copyfile(OUT/old,DATA/(new+'.tmp'))
  (DATA/(new+'.tmp')).replace(DATA/new)
 (DATA/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 modes=parser.add_mutually_exclusive_group()
 modes.add_argument('--reuse-audit',action='store_true',help='For local verification with an already checked source snapshot')
 modes.add_argument('--guide-only',action='store_true',help='Refresh listings, preserving published channels without probing streams')
 args=parser.parse_args()
 refresh(args.reuse_audit,args.guide_only)
