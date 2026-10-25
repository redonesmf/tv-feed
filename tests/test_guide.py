import datetime as dt
import gzip
import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from supplement_guide import mapping_for, normalize, read_programmes, reviewed_mappings


class GuideMatchingTests(unittest.TestCase):
    def test_native_ids_keep_regional_sports_feeds_separate(self):
        ids = ['62cd74e38f6f0d000798cd93', '6357f3de3643ba0007bc0b50']
        matches = [mapping_for({'id': 'PlutoTVSport.se', 'url': f'https://jmp2.uk/plu-{ident}.m3u8'}, {}) for ident in ids]
        self.assertEqual([m['id'] for m in matches], ids)

    def test_alias_guard_rejects_changed_region_or_platform(self):
        mappings = reviewed_mappings()
        self.assertIsNone(mapping_for({'id': 'MostHaunted.uk@UK', 'url': 'https://example.org/amg00426c17-samsung-au/playlist.m3u8'}, mappings))
        self.assertIsNone(mapping_for({'id': 'FIFAPlus.uk@French', 'url': 'https://example.org/fifa.m3u8'}, mappings))
        self.assertIsNone(mapping_for({'id': 'GhostHunters.us@UK', 'url': 'https://example.org/samsung-au/playlist.m3u8'}, mappings))

    def test_only_correct_native_channel_gets_real_fresh_listings(self):
        xml = b'''<tv><channel id="correct"/><channel id="other"/>
        <programme channel="correct" start="20261025100000 +0000" stop="20261025110000 +0000"><title>Live football</title></programme>
        <programme channel="correct" start="20261025110000 +0000" stop="20261025120000 +0000"><title>No information</title></programme>
        <programme channel="correct" start="20251025100000 +0000" stop="20251025110000 +0000"><title>Old game</title></programme>
        <programme channel="other" start="20261025100000 +0000" stop="20261025110000 +0000"><title>Wrong region</title></programme></tv>'''
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / 'guide.xml.gz'
            path.write_bytes(gzip.compress(xml))
            start = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)
            result = read_programmes(path, {'correct': ['Stable.tv@UK']}, start, start + dt.timedelta(days=1))
        self.assertEqual(list(result), ['Stable.tv@UK'])
        self.assertEqual(len(result['Stable.tv@UK']), 1)
        self.assertEqual(result['Stable.tv@UK'][0].findtext('title'), 'Live football')
        self.assertEqual(result['Stable.tv@UK'][0].get('channel'), 'Stable.tv@UK')

    def test_duplicate_overlap_and_timezone_order(self):
        def node(start, stop):
            return ET.Element('programme', start=start, stop=stop)
        first = node('20261025100000 +0000', '20261025110000 +0000')
        overlap = node('20261025103000 +0000', '20261025120000 +0000')
        next_show = node('20261025070000 -0400', '20261025080000 -0400')
        self.assertEqual(normalize([next_show, first, first, overlap]), [first, next_show])


if __name__ == '__main__':
    unittest.main()
