"""Audit MEDIC assignment intervals and prepare empirical vehicle busy times."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ems.paths import OUTPUT_DIR


COLUMNS = ["call_number", "incident_number", "unit_id", "unit_type",
           "received_dttm", "dispatch_dttm", "available_dttm"]
TIME_COLUMNS = ["received_dttm", "dispatch_dttm", "available_dttm"]


def audit_records(raw, max_calibration_hours=24):
    """Preserve every MEDIC record and annotate, rather than fix, bad timestamps.

    Duplicate means identical task-relevant fields, not merely the same call.
    Conflicting versions of a call/unit assignment are excluded for manual review.
    """
    if max_calibration_hours <= 0 or not np.isfinite(max_calibration_hours):
        raise ValueError("max_calibration_hours must be positive and finite")
    frame = raw.loc[raw.unit_type.str.strip().str.upper().eq("MEDIC")].copy()
    frame = frame.reset_index(drop=True)
    if frame.empty:
        raise ValueError("No MEDIC records in input")
    for name in COLUMNS:
        frame[name] = frame[name].fillna("").astype(str).str.strip()
    frame["duplicate_record"] = frame.duplicated(COLUMNS, keep="first")
    unique = frame.loc[~frame.duplicate_record]
    conflicts = unique.loc[unique.duplicated(["call_number", "unit_id"], keep=False)]
    frame["conflicting_assignment_key"] = pd.MultiIndex.from_frame(
        frame[["call_number", "unit_id"]]).isin(
            pd.MultiIndex.from_frame(conflicts[["call_number", "unit_id"]]))
    frame["missing_assignment_id"] = frame[["call_number", "unit_id"]].eq("").any(axis=1)
    for name in TIME_COLUMNS:
        original = frame[name].copy()
        frame[f"raw_{name}"] = original
        frame[f"missing_{name}"] = original.eq("")
        parsed = pd.to_datetime(original, format="ISO8601", errors="coerce")
        if not pd.api.types.is_datetime64_any_dtype(parsed.dtype) or parsed.dt.tz is not None:
            raise ValueError("Expected consistent naive local timestamps; timezone conversion requires explicit policy")
        frame[name] = parsed
        frame[f"invalid_{name}"] = parsed.isna() & ~frame[f"missing_{name}"]
    frame["busy_minutes"] = (frame.available_dttm - frame.dispatch_dttm).dt.total_seconds() / 60
    frame["dispatch_delay_minutes"] = (frame.dispatch_dttm - frame.received_dttm).dt.total_seconds() / 60
    frame["negative_busy_time"] = frame.busy_minutes.lt(0)
    frame["zero_busy_time"] = frame.busy_minutes.eq(0)
    frame["short_busy_time_under_1_minute"] = frame.busy_minutes.gt(0) & frame.busy_minutes.lt(1)
    frame["long_busy_time"] = frame.busy_minutes.gt(max_calibration_hours * 60)
    frame["negative_dispatch_delay"] = frame.dispatch_delay_minutes.lt(0)
    frame["dispatch_delay_over_24h"] = frame.dispatch_delay_minutes.gt(24 * 60)
    frame["usable_assignment"] = ~(frame.duplicate_record | frame.conflicting_assignment_key
                                    | frame.missing_assignment_id)
    frame["usable_busy_interval"] = frame.usable_assignment & frame.busy_minutes.gt(0)
    # The upper limit is an explicit calibration filter, not a claim of impossibility.
    frame["eligible_busy_calibration"] = frame.usable_busy_interval & ~frame.long_busy_time
    frame["usable_dispatch_delay"] = frame.usable_assignment & frame.dispatch_delay_minutes.ge(0)
    return frame


def union_intervals(records):
    """Union half-open [dispatch, available) intervals for each unit ID."""
    intervals, overlap_rows = [], []
    valid = records.loc[records.usable_busy_interval].sort_values(["unit_id", "dispatch_dttm", "available_dttm"])
    for unit, group in valid.groupby("unit_id", sort=False):
        start, end = None, None
        for row in group.itertuples():
            if start is None:
                start, end = row.dispatch_dttm, row.available_dttm
            elif row.dispatch_dttm <= end:
                if row.dispatch_dttm < end:
                    overlap_rows.append({"source_file": row.source_file,
                                         "source_record": row.source_record,
                                         "unit_id": unit, "call_number": row.call_number,
                                         "dispatch_dttm": row.dispatch_dttm,
                                         "previous_union_end": end,
                                         "overlap_minutes": (min(end, row.available_dttm) - row.dispatch_dttm).total_seconds() / 60})
                end = max(end, row.available_dttm)
            else:
                intervals.append({"unit_id": unit, "start": start, "end": end})
                start, end = row.dispatch_dttm, row.available_dttm
        if start is not None:
            intervals.append({"unit_id": unit, "start": start, "end": end})
    return (pd.DataFrame(intervals, columns=["unit_id", "start", "end"]),
            pd.DataFrame(overlap_rows, columns=["source_file", "source_record", "unit_id", "call_number",
                                                "dispatch_dttm", "previous_union_end", "overlap_minutes"]))


def hourly_workload(records, intervals):
    """Exact vehicle-hours and simultaneous busy counts; not roster capacity."""
    events = defaultdict(int)
    for row in intervals.itertuples():
        events[row.start] += 1
        events[row.end] -= 1
    hours = defaultdict(lambda: [0.0, 0])
    active, previous = 0, None
    for timestamp, change in sorted(events.items()):
        if previous is not None and active:
            cursor = previous
            while cursor < timestamp:
                hour = cursor.floor("h")
                stop = min(timestamp, hour + pd.Timedelta(hours=1))
                hours[hour][0] += active * (stop - cursor).total_seconds() / 3600
                hours[hour][1] = max(hours[hour][1], active)
                cursor = stop
        active += change
        previous = timestamp
    if active != 0:
        raise ValueError("Unbalanced interval events")
    observed_times = pd.concat([records.received_dttm, records.dispatch_dttm,
                                intervals.get("end", pd.Series(dtype="datetime64[ns]"))]).dropna()
    if observed_times.empty:
        raise ValueError("No valid times to build hourly series")
    index = pd.date_range(observed_times.min().floor("h"), observed_times.max().floor("h"), freq="h")
    result = pd.DataFrame(index=index)
    result.index.name = "hour"
    result["observed_busy_vehicle_hours"] = [hours[h][0] for h in index]
    result["mean_simultaneously_busy_units"] = result.observed_busy_vehicle_hours
    result["peak_simultaneously_busy_units"] = [hours[h][1] for h in index]
    usable = records.loc[records.usable_assignment].copy()
    received = usable.dropna(subset=["received_dttm"]).copy()
    received["hour"] = received.received_dttm.dt.floor("h")
    result["medic_response_rows_by_received_hour"] = received.groupby("hour").size().reindex(index, fill_value=0)
    result["unique_calls_by_received_hour"] = received.groupby("hour").call_number.nunique().reindex(index, fill_value=0)
    dispatched = usable.dropna(subset=["dispatch_dttm"])
    result["dispatch_starts"] = dispatched.groupby(dispatched.dispatch_dttm.dt.floor("h")).size().reindex(index, fill_value=0)
    result["received_span_boundary_hour"] = False
    for _, group in received.groupby("source_file"):
        result.loc[result.index.isin([group.hour.min(), group.hour.max()]), "received_span_boundary_hour"] = True
    if received.empty:
        result["outside_received_span"] = True
    else:
        result["outside_received_span"] = (index < received.hour.min()) | (index > received.hour.max())
    return result.reset_index()


def distribution(values):
    values = pd.Series(values, dtype=float).dropna()
    if values.empty:
        return {"count": 0}
    return {"count": len(values), "mean_minutes": float(values.mean()),
            "std_minutes": float(values.std()) if len(values) > 1 else None,
            "min_minutes": float(values.min()),
            **{f"p{q}_minutes": float(values.quantile(q / 100)) for q in (25, 50, 75, 90, 95, 99)},
            "max_minutes": float(values.max())}


def prepare(raw_files, output_dir=OUTPUT_DIR / "capacity/medic_busy_time",
            calibration_start="2025-01-01", calibration_end="2026-01-01",
            max_calibration_hours=24):
    start, end = pd.Timestamp(calibration_start), pd.Timestamp(calibration_end)
    if start >= end or start.tzinfo is not None or end.tzinfo is not None:
        raise ValueError("Need naive calibration_start < calibration_end (exclusive)")
    paths = [Path(path).resolve() for path in raw_files]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Supply distinct raw CSV paths")
    if len({path.name for path in paths}) != len(paths):
        raise ValueError("Source filenames must be distinct for audit provenance")
    output_dir = Path(output_dir)
    if any(output_dir.resolve() == path.parent for path in paths):
        raise ValueError("Keep generated outputs separate from raw source directory")
    manifest, frames = [], []
    for path in paths:
        raw = pd.read_csv(path, usecols=COLUMNS, dtype=str, keep_default_na=False)
        raw["source_file"] = path.name
        raw["source_record"] = np.arange(1, len(raw) + 1)
        manifest.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "raw_rows": len(raw), "medic_rows": int(raw.unit_type.str.strip().str.upper().eq("MEDIC").sum())})
        frames.append(raw.loc[raw.unit_type.str.strip().str.upper().eq("MEDIC")])
    records = audit_records(pd.concat(frames, ignore_index=True), max_calibration_hours)
    # A duration is known only after the vehicle has become available.
    window = records.dispatch_dttm.ge(start) & records.dispatch_dttm.lt(end) & records.available_dttm.le(end)
    records["in_busy_calibration"] = records.eligible_busy_calibration & window
    delay_window = records.received_dttm.ge(start) & records.received_dttm.lt(end) & records.dispatch_dttm.lt(end)
    records["in_delay_calibration"] = (records.usable_dispatch_delay & delay_window
                                        & ~records.dispatch_delay_over_24h)
    busy_stats = distribution(records.loc[records.in_busy_calibration, "busy_minutes"])
    delay_stats = distribution(records.loc[records.in_delay_calibration, "dispatch_delay_minutes"])
    if not busy_stats["count"]:
        raise ValueError("No eligible busy durations in the selected historical calibration window")
    intervals, overlaps = union_intervals(records)
    hourly = hourly_workload(records, intervals)
    flag_cols = ["duplicate_record", "conflicting_assignment_key", "missing_assignment_id",
                 *[f"{prefix}_{name}" for name in TIME_COLUMNS for prefix in ("missing", "invalid")],
                 "negative_busy_time", "zero_busy_time", "short_busy_time_under_1_minute",
                 "long_busy_time", "negative_dispatch_delay", "dispatch_delay_over_24h",
                 "usable_assignment", "usable_busy_interval", "eligible_busy_calibration",
                 "in_busy_calibration", "in_delay_calibration"]
    summary_rows, distributions = [], []
    for source, group in records.groupby("source_file", sort=False):
        summary_rows.append({"source_file": source, "medic_rows": len(group),
                             "unique_calls": group.call_number.replace("", pd.NA).nunique(),
                             "distinct_unit_ids_in_period": group.unit_id.replace("", pd.NA).nunique(),
                             **{name: int(group[name].sum()) for name in flag_cols}})
        distributions.append({"scope": source, "purpose": "descriptive_only_not_future_calibration",
                              **distribution(group.loc[group.eligible_busy_calibration, "busy_minutes"])})
    distributions.append({"scope": "historical_calibration", "purpose": "parameters_for_origins_at_or_after_calibration_end",
                          **busy_stats})
    parameters = {
        "unit_type": "MEDIC", "duration_definition": "available_dttm - dispatch_dttm, minutes",
        "calibration_start_inclusive": str(start), "calibration_end_exclusive": str(end),
        "not_usable_for_forecast_origins_before": str(end),
        "known_duration_rule": "Dispatch in calibration window and available <= calibration end",
        "max_busy_hours_for_calibration": max_calibration_hours,
        "max_dispatch_delay_hours_for_calibration": 24,
        "busy_time": busy_stats, "dispatch_delay": delay_stats,
        "mean_service_rate_per_vehicle_hour": 60 / busy_stats["mean_minutes"],
        "note_service_rate": "Descriptive inverse mean only; does not validate exponential service or an Erlang-C model",
        "time_convention": "Naive local timestamps preserved; DST ambiguity unresolved",
        "financial_costs_available": False, "on_duty_roster_available": False,
    }
    report_data = {
        "sources": manifest, "scope": "MEDIC only", "medic_rows": len(records),
        "quality": summary_rows, "calibration": parameters,
        "overlapping_assignment_records": len(overlaps),
        "sum_valid_assignment_vehicle_hours": float(records.loc[records.usable_busy_interval, "busy_minutes"].sum() / 60),
        "unioned_observed_vehicle_hours": float(hourly.observed_busy_vehicle_hours.sum()),
        "maximum_observed_busy_units": int(hourly.peak_simultaneously_busy_units.max()),
        "limitations": [
            "Observed busy units are not on-duty inventory or optimal required fleet.",
            "Invalid durations are retained with flags, never made positive or imputed.",
            "The 24h default is a configurable calibration threshold; flagged long intervals remain in observed interval accounting.",
            "Overlaps of one unit are unioned for workload; they are not silently removed from assignment-duration statistics.",
            "Raw call-received cohort boundaries can omit carry-in jobs and future cohorts; boundary workload is incomplete.",
            "No timezone/DST correction; investigate negative/overlapping timestamps before operational use.",
            "No evidence of unmet demand, idle fleet, staffing rosters or monetary costs is inferred.",
            "2026 descriptive statistics must not be used to tune 2026 forecasting/capacity parameters.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    records.to_csv(output_dir / "medic_busy_records.csv", index=False)
    records.loc[~records.eligible_busy_calibration | records.negative_dispatch_delay
                | records.dispatch_delay_over_24h | records.short_busy_time_under_1_minute].to_csv(
        output_dir / "records_for_review.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(output_dir / "quality_summary.csv", index=False)
    pd.DataFrame(distributions).to_csv(output_dir / "busy_time_distribution.csv", index=False)
    intervals.to_csv(output_dir / "unioned_busy_intervals.csv", index=False)
    overlaps.to_csv(output_dir / "overlapping_assignments.csv", index=False)
    hourly.to_csv(output_dir / "hourly_observed_workload.csv", index=False)
    for filename, content in (("calibration_parameters.json", parameters), ("audit.json", report_data)):
        (output_dir / filename).write_text(json.dumps(content, indent=2, allow_nan=False), encoding="utf-8")
    plot_distribution(output_dir, records.loc[records.in_busy_calibration, "busy_minutes"])
    write_report(output_dir, report_data, distributions)
    print(json.dumps({"output_dir": str(output_dir), "medic_rows": len(records),
                      "busy_time_calibration": busy_stats, "overlapping_assignments": len(overlaps)}, indent=2), flush=True)
    return report_data


def plot_distribution(output_dir, values):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(10, 4.8))
    bins = np.arange(0, np.ceil(values.max() / 10) * 10 + 10, 10)
    axis.hist(values, bins=bins, color="#217c83", edgecolor="white", linewidth=0.5)
    axis.axvline(values.mean(), color="#ad4a28", linewidth=1.5, label=f"Mean: {values.mean():.2f} min")
    axis.axvline(values.median(), color="#22354d", linestyle="--", linewidth=1.5,
                 label=f"Median: {values.median():.2f} min")
    axis.set(title=f"MEDIC busy time - historical calibration ({len(values):,} assignments)",
             xlabel="Dispatch to available (minutes)", ylabel="Assignments")
    axis.legend(frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_dir / "busy_time_distribution.png", dpi=150)
    plt.close(fig)


def write_report(output_dir, audit, distributions):
    lines = ["# Chuẩn bị thời gian xe MEDIC bận từ raw", "",
             "Phân tích riêng dữ liệu nguồn; không sửa CSV dự báo, checkpoint hoặc kết quả mô hình.", "",
             "## Chất lượng dữ liệu", "",
             "Các cờ có thể trùng nhau, không cộng các cột cờ thành tổng số hàng lỗi.", "",
             "| Nguồn | Dòng MEDIC | Thiếu available | Bận âm | Bận bằng 0 | Bận > ngưỡng | Khoảng bận hợp lệ |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in audit["quality"]:
        lines.append(f"| {row['source_file']} | {row['medic_rows']} | {row['missing_available_dttm']} | {row['negative_busy_time']} | {row['zero_busy_time']} | {row['long_busy_time']} | {row['usable_busy_interval']} |")
    lines += ["", "## Phân bố thời gian bận", "",
              "Thời gian bận = available_dttm - dispatch_dttm; đơn vị phút.", "",
              "| Phạm vi | Số lượt dùng | Trung bình | Trung vị | P90 | P95 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in distributions:
        if row["count"]:
            lines.append(f"| {row['scope']} | {row['count']} | {row['mean_minutes']:.4f} | {row['p50_minutes']:.4f} | {row['p90_minutes']:.4f} | {row['p95_minutes']:.4f} |")
    calibration = audit["calibration"]
    lines += ["", "## Quy tắc dùng tham số", "",
              f"- Cửa sổ hiệu chỉnh: từ {calibration['calibration_start_inclusive']} đến trước {calibration['calibration_end_exclusive']}.",
              "- Chỉ dùng thời lượng đã biết tại mốc chốt: available không sau mốc kết thúc hiệu chỉnh.",
              "- Chỉ dùng tham số này cho thời điểm dự báo từ mốc chốt trở đi. Không dùng tham số 2025 cho validation năm 2025.",
              f"- Loại khỏi hiệu chỉnh các lượt bận không dương hoặc vượt {calibration['max_busy_hours_for_calibration']} giờ. Đây là ngưỡng kiểm tra có thể đổi, không phải giới hạn nghiệp vụ đã xác minh.",
              "- Số liệu 2026 là mô tả/đối chiếu, không tham gia ước lượng tham số cho dự báo 2026.",
              "- Các lượt bận dưới 1 phút được gắn cờ để xem lại nhưng vẫn giữ trong thống kê nếu thời gian dương. Chưa tự loại nhiệm vụ hủy hoặc chỉ phục vụ tại hiện trường.",
              "- Độ trễ nhận cuộc gọi đến điều động trên 24 giờ được gắn cờ và không dùng hiệu chỉnh độ trễ. Không tự đổi ngày/thời gian gốc.",
              "", "## Khối lượng xe bận theo giờ", "",
              "Mỗi xe được gộp các khoảng [dispatch, available) chồng nhau trước khi tính số xe bận đồng thời. Nhiệm vụ kéo dài qua giờ được chia đúng số phút cho từng giờ.",
              f"- Có {audit['overlapping_assignment_records']} bản ghi bắt đầu khi cùng unit_id vẫn còn khoảng bận trước đó.",
              f"- Tổng thời gian bận sau khi gộp: {audit['unioned_observed_vehicle_hours']:.4f} xe-giờ.",
              f"- Số xe bận đồng thời quan sát cao nhất: {audit['maximum_observed_busy_units']}.",
              "- Đây không phải số xe đang trực, số xe còn rảnh hay số xe tối ưu cần bố trí.",
              "", "## Các file để sử dụng", "",
              "- `medic_busy_records.csv`: từng bản ghi MEDIC, thời lượng, cờ chất lượng và nguồn/bản ghi gốc.",
              "- `records_for_review.csv`: các hàng cần kiểm tra; không tự sửa thời gian âm.",
              "- `quality_summary.csv`, `busy_time_distribution.csv`: bảng thống kê.",
              "- `calibration_parameters.json`: tham số lịch sử để dùng tiếp cho năng lực.",
              "- `unioned_busy_intervals.csv`, `overlapping_assignments.csv`: các khoảng đã gộp và bằng chứng chồng thời gian.",
              "- `hourly_observed_workload.csv`: xe-giờ bận, số xe bận đồng thời cao nhất, lượt đáp ứng theo giờ nhận cuộc gọi và số bắt đầu điều động.",
              "- `audit.json`: hash nguồn, quy tắc và giới hạn để tái lập.",
              "", "## Giới hạn", "",
              "- Giữ nguyên timestamp không timezone; chưa xử lý giờ mùa hè DST. Không kết luận thời gian âm đều do một nguyên nhân.",
              "- Raw theo giai đoạn nhận cuộc gọi có thể thiếu nhiệm vụ từ giai đoạn trước và các lượt của giai đoạn sau. Giờ biên được đánh dấu, không coi là đầy đủ.",
              "- Chưa có roster/xe rảnh hoặc đơn giá tiền thật. Không tự suy ra từ số unit_id khác nhau.",
              "- Chưa chọn mô hình hàng đợi, mức dự phòng, lập lịch hay tính chi phí. Đây chỉ là phần chuẩn bị dữ liệu.", ""]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-files", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "capacity/medic_busy_time")
    parser.add_argument("--calibration-start", default="2025-01-01")
    parser.add_argument("--calibration-end", default="2026-01-01", help="Exclusive historical cutoff")
    parser.add_argument("--max-calibration-hours", type=float, default=24)
    args = parser.parse_args(argv)
    prepare(args.raw_files, args.output_dir, args.calibration_start, args.calibration_end,
            args.max_calibration_hours)


if __name__ == "__main__":
    main()
