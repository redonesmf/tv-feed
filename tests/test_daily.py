import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from audit_sports import entries
from daily_view import render_daily


class DailyViewTests(unittest.TestCase):
    def setUp(self):
        self.header = '#EXTM3U x-tvg-url="https://example.org/g.xml"'
        self.rows = entries(self.header + '\n'
            '#EXTINF:-1 tvg-id="News.uk" tvg-logo="https://example.org/logo.png" group-title="Original",News (SD)\n'
            '#EXTVLCOPT:http-referrer=https://example.org/\nhttps://example.org/news.m3u8\n'
            '#EXTINF:-1 tvg-id="NFLChannel.us" group-title="Old",NFL Channel - shows, scores and replays\nhttps://example.org/nfl.m3u8\n')
        self.specs = [{'id':'News.uk','group':'UK TV'}, {'id':'NFLChannel.us','group':'NFL'}]

    def test_order_exact_stream_metadata_and_full_backup_preserved(self):
        original = copy.deepcopy(self.rows)
        text, selected, omitted = render_daily(list(reversed(self.rows)), {'News.uk','NFLChannel.us'}, self.header, self.specs)
        result = entries(text)
        self.assertEqual(selected, ['News.uk','NFLChannel.us'])
        self.assertEqual(omitted, [])
        for before, after in zip(original, result):
            self.assertEqual((before['id'],before['name'],before['url'],before['opts']),
                             (after['id'],after['name'],after['url'],after['opts']))
        self.assertEqual(result[0]['attrs']['tvg-logo'], 'https://example.org/logo.png')
        self.assertEqual([r['attrs']['group-title'] for r in result], ['UK TV','NFL'])
        self.assertEqual(self.rows, original)
        self.assertTrue(text.startswith(self.header + '\n'))

    def test_missing_upcoming_schedule_omitted_without_removing_backup(self):
        text, selected, omitted = render_daily(self.rows, {'News.uk'}, self.header, self.specs)
        self.assertEqual(selected, ['News.uk'])
        self.assertEqual(omitted, ['NFLChannel.us'])
        self.assertEqual(len(entries(text)), 1)
        self.assertEqual(len(self.rows), 2)

    def test_duplicate_ids_and_streams_rejected(self):
        with self.assertRaisesRegex(ValueError, 'repeats a channel ID'):
            render_daily(self.rows, {'News.uk'}, self.header, [self.specs[0],self.specs[0]])
        self.rows[1]['url'] = self.rows[0]['url']
        with self.assertRaisesRegex(ValueError, 'repeats a stream URL'):
            render_daily(self.rows, {'News.uk','NFLChannel.us'}, self.header, self.specs)

    def test_unknown_channel_or_group_and_wrong_group_order_rejected(self):
        with self.assertRaisesRegex(ValueError, 'absent from full backup'):
            render_daily(self.rows, set(), self.header, [{'id':'Missing','group':'UK TV'}])
        with self.assertRaisesRegex(ValueError, 'unknown group'):
            render_daily(self.rows, set(), self.header, [{'id':'News.uk','group':'All games live'}])
        with self.assertRaisesRegex(ValueError, 'display order'):
            render_daily(self.rows, set(), self.header, list(reversed(self.specs)))


if __name__ == '__main__':
    unittest.main()
