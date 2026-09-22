"""Regression coverage for Vaisala SHP geometry assembly."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shapely.geometry import LineString

from routers.vaisala import _merge_feature_geometries


def test_merge_feature_geometries_preserves_disconnected_wscc_segments():
    """One WSCC section key may own multiple, physically disconnected line features."""
    merged = _merge_feature_geometries([
        LineString([(0, 0), (10, 0)]),
        LineString([(100, 0), (103, 0)]),
    ])

    assert merged.geom_type == "MultiLineString"
    assert len(merged.geoms) == 2
    assert merged.length == 13
