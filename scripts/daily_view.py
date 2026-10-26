"""A guide-backed, ordered view of existing streams, leaving the full feed intact."""
import json
import pathlib

GROUPS = ('UK TV', 'Football', 'NFL', 'Other Sports')
CONFIG = pathlib.Path(__file__).resolve().parents[1] / 'config/daily-view.json'


def render_daily(rows, upcoming, header, configuration=None):
    specs = configuration if configuration is not None else json.loads(CONFIG.read_text(encoding='utf-8'))
    ids = [spec['id'] for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError('Daily TV configuration repeats a channel ID')
    if any(spec['group'] not in GROUPS for spec in specs):
        raise ValueError('Daily TV configuration contains an unknown group')
    group_order = [GROUPS.index(spec['group']) for spec in specs]
    if group_order != sorted(group_order):
        raise ValueError('Daily TV groups must follow the configured display order')
    by_id = {row['id']: row for row in rows}
    missing = set(ids) - set(by_id)
    if missing:
        raise ValueError('Daily TV channels absent from full backup: ' + ', '.join(sorted(missing)))
    selected, omitted, lines = [], [], [header]
    seen_urls = set()
    for spec in specs:
        row = by_id[spec['id']]
        if row['id'] not in upcoming:
            omitted.append(row['id'])
            continue
        if row['url'] in seen_urls:
            raise ValueError('Daily TV repeats a stream URL')
        seen_urls.add(row['url'])
        attrs = dict(row['attrs'])
        attrs['group-title'] = spec['group']
        metadata = ' '.join(f'{key}="{value}"' for key, value in attrs.items())
        lines.append(f'#EXTINF:-1 {metadata},{row["name"]}')
        lines.extend(f'#EXTVLCOPT:{key}={value}' for key, value in row['opts'].items())
        lines.append(row['url'])
        selected.append(row['id'])
    return '\n'.join(lines) + '\n', selected, omitted
