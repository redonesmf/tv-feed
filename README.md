# TV channel feed

Read-only playlist and programme-guide files for a TV on an isolated guest network.
No home computer needs to stay on, no inbound home-network ports are required,
and developer debugging can remain disabled.

- Playlist: https://redonesmf.github.io/tv-feed/p.m3u
- Programme guide: https://redonesmf.github.io/tv-feed/g.xml
- Status: https://redonesmf.github.io/tv-feed/status.json

The playlist advertises its guide URL for automatic discovery. These URLs and
the repository contents are publicly readable. No personal photos, account
logins, local device inventory, or private subscription credentials belong here.

## Sources and refresh

- Channels: iptv-org [Sports](https://iptv-org.github.io/iptv/categories/sports.m3u)
  and [UK](https://iptv-org.github.io/iptv/countries/uk.m3u).
- Additional links: `config/extra-channels.m3u`, originally checked from
  [chingithub1/iptv](https://github.com/chingithub1/iptv/blob/main/Original) and
  iptv-org News. These are fixed links, not a provider subscription.
- Guide: [IPTV-EPG.org](https://iptv-epg.org/guides), plus the
  [MJH XMLTV mirror](https://github.com/matthuisman/i.mjh.nz) for Pluto TV,
  Samsung TV Plus and Roku streams. Native stream IDs and reviewed aliases in
  `config/guide-mappings.json` map listings to the existing playlist IDs.
  Aliases have stream URL guards; similar names alone do not establish a match.
- Coverage report: https://redonesmf.github.io/tv-feed/coverage.json
- Optional guide-only playlist: https://redonesmf.github.io/tv-feed/guide.m3u
  This uses the same streams but includes only channels with real listings in
  the next 24 hours at build time. Listings can run out between refreshes.

The full playlist keeps every curated channel. Channels with fresh listings
appear first; unavailable schedules have separate, clearly labelled groups.
The guide-only version is an alternative to the full playlist, not an extra
playlist that must be added. Updating only `g.xml` does not update channel groups.

Pluto guide matches use the precise native feed ID, preserving regional
variants and upstream channel renames. Reviewed Samsung/Roku mappings use the
platform and country identified in the stream URL, even when the M3U channel ID
has a different country suffix. BBC News North America uses the corresponding
US guide, not the domestic BBC News schedule. No placeholder schedules are made
up. Duplicate and overlapping entries are removed. Publication validates all
retained and explicitly added IDs, the guide-only subset, timestamps, overlaps and coverage.
`status.json` distinguishes any listings, on-now listings and the next 24 hours.
Guide-only runs explicitly report that no media audit was performed and retain
the timestamp of the last channel-link check.
Some free channels publish no usable EPG; these remain playable without a guide.

GitHub Actions refreshes listings hourly at minute 23. At 05:23 and 17:23 UTC
it also rechecks channel links. Other runs keep the published stream URLs and
source groups without probing video streams. Full refreshes can be run manually
from Actions. Schedules can be delayed. The last validated deployment stays online if
a refresh fails. Check `status.json` and Actions when the guide appears stale.
GitHub can disable schedules after prolonged repository inactivity.

An HLS manifest and a small media sample are checked for source channels; this
does not guarantee continuous video playback or availability at another location.
The curated channel IDs in `config/retained-channels.m3u` are preserved. Working
replacement URLs for those IDs are preferred when available, while a failed
cloud probe retains the previously checked TV link. Cloud location/access results
can differ from the TV. Status separates playlist size from current cloud media
responses. New channels can be added to the extra-channel configuration. No guide
data is invented.
The guide uses source times; a programme listing does not establish that the
broadcast is live rather than a replay. The sources do not guarantee every
Premier League or Liverpool match.

## TV installation

In TiviMate, use the playlist and guide URLs above. In the installed free version,
playlist update controls are locked. Replacing the old PC URL requires deleting
the existing playlist and adding this combined M3U as a **TV playlist**. This
reimports the channel list; it does not uninstall the app. A Premium upgrade is
not required for this reimport. Keep the TV on guest Wi-Fi and ADB disabled.

After importing, open Sky Sports Premier League and check the preview and guide.
Also test Sky Sports Action and BBC News North America. The UK main-channel
additions are grouped separately from BBC News North America and sports.

## UK main-channel additions

Sixteen additional streams were decoded from a public HTTP MPEG-TS relay on
25 October 2026, after ordinary BBC/ITV/Channel 4/5 M3U candidates failed from
the US connection. Collection source:
[public playlist](https://github.com/badboys88888/IPTV/blob/94ce9db3dad99113d1e4954633f94941565ac8d5/iptv.m3u).
Decoded video, DVB service names and channel logos were inspected; original
384 channels are preserved. This is third-party relay availability evidence,
not a guarantee of continuous service or TV-device playback. No new TV app,
account login, private credentials or network-isolation changes are involved.

The group includes BBC One, BBC Two, ITV1-4, Channel 4, Channel 5, E4, Film4,
5STAR, 5USA, More4 +1, BBC News UK and two shared BBC Three/CBBC and BBC
Four/CBeebies feeds. The shared feeds showed BBC Three/Four at night despite
their legacy CBBC/CBeebies service names; their guide uses the corresponding
combined UK listings. More4 is explicitly the +1 feed. BBC One, E4, Film4,
5STAR, 5USA and More4 +1 are SD; the other ten additions are 1080-line HD.
The player must respect the MPEG-TS aspect ratio, especially for SD channels.

ITV1 uses a clearly recorded London/national guide reference because the relay
does not identify its regional edition. Regional-news listings may differ.
Explicit configured additions keep their verified URLs during future refreshes.

All sixteen appear in the full and guide-only playlists. An optional UK-only
playlist is available at https://redonesmf.github.io/tv-feed/uk.m3u and uses
the same g.xml EPG. It is an alternative import, not a required second playlist.
Channel additions and group changes require a playlist reimport in free TiviMate.

## Maintenance

Edit the extra-channel configuration only with public, verified source links.
Run the Actions workflow to rebuild and publish. Channel-list changes require
another reimport in the free TiviMate version; hosting does not unlock paid app
features. Guide refresh follows the player's existing behaviour.

For local checks, use Python 3.12: `python scripts/validate_feed.py`.
For a full refresh, use `python scripts/refresh.py`. Downloads and audit records
stay in ignored `.cache/`; only the `data/` directory is deployed.

Official GitHub Actions are pinned to specific commit IDs. Checkouts do not retain Git
credentials. The write token is supplied only to the commit step, after public
data fetching and validation complete. No arbitrary playlist content is executed.
