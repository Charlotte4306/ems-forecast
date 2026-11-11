# Automatic forecast: canonical target and operation

Current release: `20261111-190149-daily-forecast`; archive SHA-256 `96c1b0b83ae12dfc4b42fd8d6eb6892ceb6c2f22000a4d76132dca58d2ce95ee`. Real worker rerun succeeded and public API reports received-time dispatch forecasts: 168 hours/seven days, observed through 2026-11-10 23:00 San Francisco. Its separate live-model holdout MAE is 3.232 dispatches/hour. The daily timer remains enabled. Public HTML/JS matched local files; Python/JS tests passed. These results supersede the earlier dispatch-time automatic forecast.

## Corrected definition (2026-11-12)

The shared research target is **vehicle dispatch response records grouped by call-received hour**. Only `unit_type = MEDIC` is included. Multiple vehicles responding to the same call remain multiple dispatches. The name `call_count` in historical CSVs does not mean that the values are distinct calls.

The live DataSF query now uses `count(distinct rowid)` with both date grouping and filtering on `received_dttm`. Snapshot metadata is `target=medic-dispatches`, `unit=dispatches`, `timeField=received_dttm`, `identityField=rowid`. Server and client reject snapshots with the former call-count target or dispatch-time clock.

Previous automatic versions that counted distinct calls, and the subsequent version grouped by `dispatch_dttm`, are superseded. Their archive files remain identifiable by target/timeField metadata. New input history archives use `history-medic-dispatches-received-YYYYMMDD.json`; issued forecasts end in `-medic-dispatches-received.json`.

## Independent checks

- Frozen validation CSV: 8,760 hours, 100,320 dispatches. Current DataSF gives 100,320 dispatches and 94,420 distinct calls over the same year.
- Frozen test CSV: 6,796 hours, 79,348 dispatches. Current DataSF agrees on 6,795 hours. The final hour, 2026-10-11 03:00, contains 4 dispatches in the frozen snapshot and 7 in the current source; current total is 79,351. The frozen research snapshot is retained unchanged.
- The specific 2026-01-02 08:00 hour has 13 rows/distinct RowIDs versus 12 distinct calls on the source, matching target 13 in the CSV.
- The earlier assertion that historical models were necessarily trained on distinct calls was incorrect. Notebook descriptions alone were insufficient; raw-to-CSV checks establish the target.

## Forecasts versus research experiments

The three historical model pipelines, scalers, checkpoints, and MAE/MAPE results are unchanged. Their shared target uses received-time dispatch counts. Research comparison keeps the 1h and 24h protocols separate, fits parameters through 2024, selects on validation 2025 and evaluates 2026 without test tuning. Forecast scores cover 6,796 hours; complete-shift evaluation covers 6,792 hours. These rules must not be replaced with the live worker's rolling retraining protocol.

The automatic worker is a separate seasonal Prophet model refitted on the latest 180 complete days; it is not the historical Prophet/LSTM/SARIMAX comparison. It reports a separate 14-day holdout MAE and forecasts 168 hourly model slots over seven calendar days. Its forecasts are dispatch workload estimates, not staffing counts or a capacity/cost decision. Raw busy time remains `available_dttm - dispatch_dttm`; this physical duration is distinct from the received-time bucketing of the forecast target.

The live job downloads hourly aggregates from DataSF, not complete raw response rows. The latest source day is excluded, and a source lag greater than three days prevents publication. A failed refresh retains the most recent compatible forecast; the UI reports failure/staleness. JSON publication is atomic. DST days are explicitly represented as 24 wall-clock model slots rather than claimed to be 24 elapsed operating hours.

## Deployment and scheduling

- Page: https://emsforecast.live/daily-forecast
- API: https://emsforecast.live/api/live-forecast
- Shared data: `/home/charlotte/apps/emsforecast-live` (outside immutable releases).
- Current code link: `/home/charlotte/apps/emsforecast-current`.
- Worker venv: `/home/charlotte/apps/emsforecast-live-venv`.
- Web environment: `EMS_LIVE_DIR=/home/charlotte/apps/emsforecast-live`.
- `emsforecast-update.timer`: daily at 07:00 America/Los_Angeles, up to five minutes randomized delay, persistent after reboot.
- `emsforecast-update.service`: retries after 30 minutes, up to two starts per two hours.
- Inputs are archived per day; forecasts are archived with issuance timestamps. Old incompatible archives are not reused for training.

```bash
systemctl list-timers emsforecast-update.timer
sudo systemctl start emsforecast-update.service
sudo journalctl -u emsforecast-update.service -n 50 --no-pager
curl -fsS https://emsforecast.live/api/live-forecast
```

Future releases must include `ems/live`, `web/live.mjs` and worker units. `activate_release.py` preserves shared data configuration and updates the code symlink. Do not switch worker code while a refresh is running. Restore a release's `previous-emsforecast.service` to roll back the web; manage the current-code symlink and timer separately when rolling back the worker.
