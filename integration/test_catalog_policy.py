import numpy as np
import pandas as pd
import pytest

from src.data import Panel, load_panel
from integration.catalog_policy import asof_panel, safe_snapshot, stable_codes, expand_to_output


def fixture_panel():
    dates = pd.date_range("2024-01-01", periods=210)
    y = np.arange(210 * 4, dtype=np.float32).reshape(210, 4) % 5
    p = Panel(dates, y, y.copy(), dict(warehouses=["w1", "w2"], articles=["b", "d"]))
    first = pd.DataFrame([
        ["sales", "warehouse_name", "w1", "2024-01-01"],
        ["sales", "warehouse_name", "w2", "2024-01-01"],
        ["sales", "article", "b", "2024-01-01"],
        ["sales", "article", "d", "2024-07-09"],
    ], columns=["source", "key_type", "key", "first_date"])
    return p, first


def test_future_catalog_append_does_not_change_historical_features_or_active_metadata():
    p, first = fixture_panel()
    before, idx = safe_snapshot(p, 179, first)
    # Insert lexicographically earlier warehouse/article, not simply append columns.
    extended = Panel(p.dates, np.zeros((210, 9), np.float32), np.full((210, 9), np.nan, np.float32),
                     dict(warehouses=["a_future", "w1", "w2"], articles=["a_future", "b", "d"]))
    oldpositions = extended.pairs.get_indexer(p.pairs)
    extended.y[:, oldpositions] = p.y
    extended.stock[:, oldpositions] = p.stock
    extra = pd.DataFrame([["sales", "warehouse_name", "a_future", "2024-07-10"],
                          ["sales", "article", "a_future", "2024-07-10"]], columns=first.columns)
    after, idx2 = safe_snapshot(extended, 179, pd.concat([first, extra]))
    pd.testing.assert_frame_equal(before, after, check_exact=True)
    q1, _ = asof_panel(p, 179, first)
    q2, _ = asof_panel(extended, 179, pd.concat([first, extra]))
    assert q1.catalogs == q2.catalogs
    assert np.array_equal(q1.y, q2.y)
    assert len(q1.dates) == 180
    assert p.pairs[idx].equals(extended.pairs[idx2])


def test_unknown_id_fallback_and_mapping():
    p, first = fixture_panel()
    _, idx = safe_snapshot(p, 179, first)
    prediction = np.ones((64, len(idx)), np.float32)
    output = expand_to_output(prediction, idx, width=4)
    assert output.shape == (64, 4)
    assert np.all(output[:, idx] == 1)
    assert np.all(output[:, [1, 3]] == 0)


def test_known_codes_stable_across_origin_and_catalog_growth():
    p, first = fixture_panel()
    earlier, _ = safe_snapshot(p, 179, first)
    later, _ = safe_snapshot(p, 200, first)
    assert earlier.article_id.dtype == np.int32
    assert earlier.warehouse_id.dtype == np.int32
    assert earlier.article_id[0] == later.article_id[0]
    assert earlier.warehouse_id[1] == later.warehouse_id[2]
    assert stable_codes(["b"], "article")[0] == stable_codes(["a", "b"], "article")[1]
    assert max(stable_codes(["a", "b"], "article")) < 2**20 - 1


def test_inner_catalog_excludes_id_known_only_at_outer_cutoff():
    p, first = fixture_panel()
    early, _ = asof_panel(p, 179, first)
    late, _ = asof_panel(p, 200, first)
    assert early.catalogs["articles"] == ["b"]
    assert late.catalogs["articles"] == ["b", "d"]


def test_full_output_contract_real_catalog():
    panel = load_panel("cache")
    _, idx = asof_panel(panel, panel.dates.get_loc("2025-09-14"))
    output = expand_to_output(np.ones((64, len(idx)), np.float32), idx)
    assert output.shape == (64, 8789)
    assert len(idx) == 8668
    assert np.count_nonzero(output[0] == 0) == 121


def test_invalid_origin_and_forecast_rejected():
    p, first = fixture_panel()
    with pytest.raises(ValueError):
        asof_panel(p, -1, first)
    with pytest.raises(ValueError):
        expand_to_output(np.array([np.nan]), [0])
    with pytest.raises(ValueError):
        expand_to_output(np.ones(2), [0, 0])
