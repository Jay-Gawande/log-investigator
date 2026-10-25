import pandas as pd
import pytest

from app.investigator import anomaly


def minute_df(bad_by_minute, start="2026-10-01 10:00:00", minutes=120):
    """Build the frame minute_counts() would return; bad_by_minute maps offset -> count."""
    idx = pd.date_range(start, periods=minutes, freq="min")
    bad = [float(bad_by_minute.get(i, 0)) for i in range(minutes)]
    return pd.DataFrame({"minute": idx, "bad": bad, "total": [20] * minutes})


@pytest.fixture
def use_minutes(monkeypatch):
    def _use(df):
        monkeypatch.setattr(anomaly, "minute_counts", lambda s, e: df)
    return _use


def test_no_data_returns_none(use_minutes):
    use_minutes(pd.DataFrame({"minute": [], "bad": [], "total": []}))
    assert anomaly.find_anomalous_period("a", "b") is None


def test_quiet_baseline_returns_none(use_minutes):
    use_minutes(minute_df({}))
    assert anomaly.find_anomalous_period("a", "b") is None


def test_isolated_background_noise_is_not_an_anomaly(use_minutes):
    # one stray warning per minute on a few minutes must not trip the detector
    use_minutes(minute_df({5: 1, 40: 1, 77: 1}))
    assert anomaly.find_anomalous_period("a", "b") is None


def test_detects_single_incident_window(use_minutes):
    use_minutes(minute_df({i: 30 for i in range(65, 77)}))  # 11:05 - 11:16
    p = anomaly.find_anomalous_period("a", "b")
    assert p["start"] == pd.Timestamp("2026-10-01 11:05:00")
    assert p["end"] == pd.Timestamp("2026-10-01 11:17:00")  # end is exclusive
    assert p["bad_lines_in_window"] == 12 * 30
    assert p["peak_bad_per_minute"] == 30
    assert p["baseline_bad_per_minute"] == 0.0
    assert p["other_windows_found"] == 0


def test_small_gaps_are_merged_into_one_window(use_minutes):
    # flagged minutes 10:00 and 10:02 are two minutes apart -> same window
    use_minutes(minute_df({0: 20, 2: 20}))
    p = anomaly.find_anomalous_period("a", "b")
    assert p["start"] == pd.Timestamp("2026-10-01 10:00:00")
    assert p["end"] == pd.Timestamp("2026-10-01 10:03:00")
    assert p["other_windows_found"] == 0


def test_large_gaps_split_windows(use_minutes):
    # 10:00 and 10:05 are five minutes apart -> two windows
    use_minutes(minute_df({0: 20, 5: 20}))
    p = anomaly.find_anomalous_period("a", "b")
    assert p["other_windows_found"] == 1


def test_picks_window_with_most_bad_lines(use_minutes):
    small = {i: 10 for i in range(0, 3)}        # 30 bad lines
    big = {i: 10 for i in range(60, 66)}        # 60 bad lines
    use_minutes(minute_df({**small, **big}))
    p = anomaly.find_anomalous_period("a", "b")
    assert p["start"] == pd.Timestamp("2026-10-01 11:00:00")
    assert p["bad_lines_in_window"] == 60
    assert p["other_windows_found"] == 1


def test_threshold_is_configurable(use_minutes):
    use_minutes(minute_df({i: 4 for i in range(10, 14)}))
    # score for 4 bad lines is about 2.7: below the default threshold of 3
    assert anomaly.find_anomalous_period("a", "b") is None
    assert anomaly.find_anomalous_period("a", "b", threshold=2.0) is not None


def test_return_types_are_plain_python(use_minutes):
    use_minutes(minute_df({i: 30 for i in range(10, 15)}))
    p = anomaly.find_anomalous_period("a", "b")
    assert isinstance(p["bad_lines_in_window"], int)
    assert isinstance(p["peak_bad_per_minute"], int)
    assert isinstance(p["baseline_bad_per_minute"], float)
