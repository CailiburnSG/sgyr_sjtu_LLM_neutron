"""Extract observable zero and spike events directly from a time-series CSV.

This is deliberately deterministic.  It creates observations, not diagnoses.
Thresholds are command-line parameters and must be frozen before final testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import math

import pandas as pd


def read_timeseries_csv(csv_path: str | Path) -> tuple[pd.DataFrame, str, list[str]]:
    """Read, time-sort and return numeric channels from a neutron-current CSV."""
    csv_path = Path(csv_path)
    last_error: Exception | None = None
    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            frame = pd.read_csv(csv_path, encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        raise RuntimeError(f"Unable to decode {csv_path}") from last_error
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("CSV must contain a time column and at least one channel.")
    time_column = frame.columns[0]
    frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
    frame = frame.dropna(subset=[time_column]).sort_values(time_column).reset_index(drop=True)
    channels = [column for column in frame.columns[1:] if pd.api.types.is_numeric_dtype(frame[column])]
    if not channels:
        raise ValueError("CSV contains no numeric signal channels.")
    return frame, time_column, channels


def _zero_observations(
    frame: pd.DataFrame,
    time_column: str,
    channels: list[str],
    record_id: str,
    csv_path: Path,
    zero_tolerance: float,
    max_isolated_zero_samples: int,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for channel in channels:
        values = frame[channel]
        zero_mask = values.notna() & values.abs().le(zero_tolerance)
        run_id = zero_mask.ne(zero_mask.shift()).cumsum()
        for _, run in frame.loc[zero_mask].groupby(run_id[zero_mask]):
            run_length = len(run)
            if run_length > max_isolated_zero_samples:
                continue
            start = run[time_column].iloc[0]
            end = run[time_column].iloc[-1]
            observations.append(
                {
                    "record_id": record_id,
                    "event_type": "isolated_zero",
                    "channel": channel,
                    "time_text": start.isoformat(sep=" "),
                    "time_order": start.isoformat(),
                    "source": {
                        "kind": "csv_detector",
                        "path": str(csv_path),
                        "detector": "zero_run",
                        "zero_tolerance": zero_tolerance,
                        "max_isolated_zero_samples": max_isolated_zero_samples,
                        "run_end": end.isoformat(sep=" "),
                        "run_samples": run_length,
                    },
                }
            )
    return observations


def _spike_observations(
    frame: pd.DataFrame,
    time_column: str,
    channels: list[str],
    record_id: str,
    csv_path: Path,
    window: int,
    mad_multiplier: float,
    range_fraction: float,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    if window < 3 or window % 2 == 0:
        raise ValueError("spike window must be an odd integer of at least 3")
    for channel in channels:
        values = frame[channel].astype(float)
        dynamic_range = values.max() - values.min()
        if not math.isfinite(dynamic_range) or dynamic_range <= 0:
            continue
        local_median = values.rolling(window=window, center=True, min_periods=1).median()
        deviation = (values - local_median).abs()
        local_mad = deviation.rolling(window=window, center=True, min_periods=1).median()
        spike_mask = (deviation > mad_multiplier * local_mad) & (deviation > range_fraction * dynamic_range)
        run_id = spike_mask.ne(spike_mask.shift()).cumsum()
        for _, run in frame.loc[spike_mask].groupby(run_id[spike_mask]):
            indices = run.index
            peak_index = deviation.loc[indices].idxmax()
            start = run[time_column].iloc[0]
            end = run[time_column].iloc[-1]
            peak_time = frame.at[peak_index, time_column]
            observations.append(
                {
                    "record_id": record_id,
                    "event_type": "spike",
                    "channel": channel,
                    "time_text": peak_time.isoformat(sep=" "),
                    "time_order": peak_time.isoformat(),
                    "source": {
                        "kind": "csv_detector",
                        "path": str(csv_path),
                        "detector": "rolling_median_mad",
                        "window": window,
                        "mad_multiplier": mad_multiplier,
                        "range_fraction": range_fraction,
                        "run_start": start.isoformat(sep=" "),
                        "run_end": end.isoformat(sep=" "),
                        "run_samples": len(run),
                        "peak_value": float(frame.at[peak_index, channel]),
                        "peak_deviation": float(deviation.at[peak_index]),
                    },
                }
            )
    return observations


def extract_csv_observations(
    csv_path: str | Path,
    record_id: str,
    *,
    zero_tolerance: float = 0.0,
    max_isolated_zero_samples: int = 2,
    spike_window: int = 31,
    spike_mad_multiplier: float = 5.0,
    spike_range_fraction: float = 0.05,
) -> list[dict[str, Any]]:
    """Extract v1 isolated-zero and spike observations from one CSV."""
    csv_path = Path(csv_path)
    frame, time_column, channels = read_timeseries_csv(csv_path)
    return _zero_observations(
        frame, time_column, channels, record_id, csv_path, zero_tolerance, max_isolated_zero_samples
    ) + _spike_observations(
        frame,
        time_column,
        channels,
        record_id,
        csv_path,
        spike_window,
        spike_mad_multiplier,
        spike_range_fraction,
    )

