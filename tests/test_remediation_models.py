"""Leakage and structural tests for experimental two-part expected volume."""
import numpy as np
import pandas as pd
import pytest
from src.data import Panel
from src.remediation_models import fit_two_part, predict_two_part


def test_two_part_training_and_features_ignore_future():
    rng=np.random.default_rng(73)
    y=(rng.random((360,2))<.3)*rng.uniform(.1,2,(360,2))
    panel=Panel(pd.date_range('2024-01-01',periods=360),y.astype('float32'),
                np.full((360,2),np.nan,dtype='float32'),{'warehouses':['w'],'articles':['a','b']})
    fitted=fit_two_part(panel,280,rounds=3)
    expected,p,m=predict_two_part(panel,280,fitted)
    assert expected.shape==(64,2)
    assert np.array_equal(expected,p*m)
    assert 0<fitted['positive_training_rows']<fitted['training_rows']
    assert max(pd.Timestamp(d)+pd.Timedelta(days=64) for d in fitted['origins'])<=panel.dates[280]
    panel.y[281:]=1e6
    panel.stock[281:]=1e6
    fitted_changed=fit_two_part(panel,280,rounds=3)
    actual,_,_=predict_two_part(panel,280,fitted_changed)
    np.testing.assert_array_equal(actual,expected)


def test_two_part_rejects_unidentifiable_occurrence():
    panel=Panel(pd.date_range('2024-01-01',periods=300),np.zeros((300,1),dtype='float32'),
                np.full((300,1),np.nan,dtype='float32'),{'warehouses':['w'],'articles':['a']})
    with pytest.raises(ValueError,match='both binary classes'):
        fit_two_part(panel,280,rounds=2)
