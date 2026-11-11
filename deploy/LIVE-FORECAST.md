# Daily forecast deployment

Current UI release: `20261111-184034-daily-forecast`, SHA-256 `c903d4884f43e93ebcf8580792ed7698334f14eb22a542eba666b87c004c27ca`. Only navigation order and chapter-number mapping changed: overview, demand forecast, fleet plan, scenario costs, model evaluation, 7-day forecast, history, settings. Original heading style is retained. The first six tabs remain in the main navigation; history/settings are under More. DOM navigation/number checks and public asset hashes passed; dispatch forecasts are retained.

The user requested undoing the latest chapter-header/navigation change. Active release and current-code link have been restored to `20261111-182537-daily-forecast`. The three changed local UI files were restored from that release, and the associated DOM assertions were reverted. Public HTML/CSS/JS match the restored files. Live dispatch forecasts and the daily timer are retained. Release `20261111-183511-daily-forecast` remains archived but is no longer active.

## Target correction, 2026-11-12

Current release: `20261111-182537-daily-forecast`, archive SHA-256 `89ff5fdc7a960ae4a96a2f3af36895c798e694e02f666b3753619596372de7fb`.

The initial call-count target below was incorrect for the requested dispatch forecast and is superseded. The current live pipeline filters MEDIC, counts distinct `rowid` response records, and groups by `dispatch_dttm`, rather than collapsing records by `call_number` and received time. One call involving two MEDIC units contributes two dispatches. Source probe for received dates 2026-11-08 to 2026-11-10 found 608 response rows/distinct RowIDs versus 559 distinct calls.

The regenerated API reports `target=medic-dispatches`, `unit=dispatches`, `timeField=dispatch_dttm`, `identityField=rowid`. All 168 future hours were regenerated; the new historical holdout MAE is 3.162 dispatches/hour. This metric is not comparable as the same target to the former calls/hour result. Client validation rejects legacy call-count snapshots, and the API rejects the wrong target.

New aggregate history archives use `history-medic-dispatches-YYYYMMDD.json`; forecast archive filenames end in `-medic-dispatches.json`. Original call-count archives remain identifiable by their own target metadata and are not used as dispatch training data. Historical experimental CSVs/checkpoints remain unchanged and still need a separate target audit before comparing them to this dispatch forecast.

The daily timer remains enabled. Real retraining, public API metadata, public JS/HTML hashes, and client unit guards were verified after deployment.

## Initial deployment (superseded target)

Enabled on 2026-11-12 (Asia/Saigon) at https://emsforecast.live/daily-forecast.

- Release: `20261111-181742-daily-forecast`.
- Archive SHA-256: `4a08c7baa352bebee3123098dc6009726f5a4103654cca2bd31a130eaffb2da6`.
- Current code link: `/home/charlotte/apps/emsforecast-current`.
- Data: `/home/charlotte/apps/emsforecast-live`, separate from immutable web releases.
- Worker venv: `/home/charlotte/apps/emsforecast-live-venv`.
- Timer: `emsforecast-update.timer`, enabled; 07:00 America/Los_Angeles with up to five minutes randomized delay; catches missed runs after reboot.
- Worker: `emsforecast-update.service`; retries failures after 30 minutes, up to two starts per two hours.
- Web service reads `EMS_LIVE_DIR=/home/charlotte/apps/emsforecast-live`.
- Forecast API: `/api/live-forecast`; API preserves the latest successful forecast while separately reporting refresh failures.

First real run succeeded: 168 hourly estimates for 2026-11-11 through 2026-11-17, with observations through 2026-11-10 23:00 in San Francisco. Fourteen-day holdout MAE was 2.870 calls/hour. This is historical validation, not an accuracy guarantee for the future week.

The target is distinct calls with a MEDIC response, grouped by received time; it is not the number of dispatched vehicles. DataSF queries return only aggregated day/hour counts. No addresses, patient data, or call identifiers are downloaded or served. The source's latest day is excluded because it may be incomplete. Source more than three days behind prevents publication; previous forecasts remain available and the UI flags age after 36 hours.

Each run trains a fixed seasonal Prophet model on the most recent 180 complete days. A separate 14-day holdout fit reports recent error; final fitting includes those historical days. There are no future observed lag inputs. Seven calendar days use 24 wall-clock model slots each; DST days are explicitly noted in the UI. Existing experimental datasets and checkpoints are unchanged.

`hourly-history.json` retains the latest downloaded aggregate history. `archive/history-YYYYMMDD.json` retains each day's input history and timestamped forecast JSON files retain issued forecasts. JSON publication uses atomic file replacement.

Operations:

```bash
systemctl list-timers emsforecast-update.timer
sudo systemctl start emsforecast-update.service
sudo journalctl -u emsforecast-update.service -n 50 --no-pager
curl -fsS https://emsforecast.live/api/live-forecast
```

Future releases must include `ems/live`, `web/live.mjs`, and the live worker units. `activate_release.py` preserves shared data configuration and updates the current code link. Stop the update service before switching worker code if a run is in progress. The dependency list is `deploy/requirements-live.txt`; Windows development also needs tzdata, included there.

Verified: real ingestion and Prophet fit on VPS, successful systemd service exit, enabled timer and next run, public API with 168 hours/seven days, public HTML/JS/CSS hashes, DOM day selection and hourly rendering, stale-source protection and API last-success behavior. Browser screenshots have not been verified.

To roll back the web service, restore `previous-emsforecast.service` from this release directory and reload/restart systemd. Disable the timer separately if rolling back the worker.
