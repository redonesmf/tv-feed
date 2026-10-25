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
- Guide: [IPTV-EPG.org](https://iptv-epg.org/guides), using matching channel IDs.

GitHub Actions refreshes at 05:23 and 17:23 UTC and can also be run manually from
Actions. Schedules can be delayed. The last validated deployment stays online if
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
Also test Sky Sports Action and BBC News North America. BBC One and BBC Two have
not been added because their candidate links could not be verified.

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
