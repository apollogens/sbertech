import numpy as np
import pandas as pd
import pytest
from integration.ensemble_engine import align_components,convex_combine,postprocess

def test_alignment_permutation_and_weight_identity():
    a=pd.DataFrame({'date':['2026-01-01']*2,'warehouse_name':['w']*2,'article':['a','b'],'quantity':[1.,3.]})
    b=a.copy();b.quantity=[3.,5.]
    aligned=align_components({'a':a,'b':b.iloc[::-1]},a)
    first=convex_combine(aligned,{'a':.25,'b':.75})
    second=convex_combine(dict(reversed(list(aligned.items()))),{'b':.75,'a':.25})
    assert np.array_equal(first,[2.5,4.5]) and np.array_equal(first,second)
    for bad in [b.iloc[:1],pd.concat([b.iloc[:1],b.iloc[:1]])]:
        with pytest.raises(ValueError):align_components({'bad':bad},a)
    bad=b.copy();bad.loc[0,'date']='2026-01-02'
    with pytest.raises(ValueError):align_components({'bad':bad},a)

@pytest.mark.parametrize('weights',[{'a':-.1,'b':1.1},{'a':.2,'b':.2},{'a':np.nan,'b':1.},{'a':1.}])
def test_bad_weights(weights):
    with pytest.raises(ValueError):convex_combine({'a':np.ones(2),'b':np.ones(2)},weights)

def test_round_boundaries_and_operation_order():
    values=np.array([0.,np.nextafter(.25,0),.25,np.nextafter(.25,1),.5,np.nextafter(.5,1),1.5,2.5,1e12+.5])
    assert np.array_equal(postprocess(values,'nearest_even'),[0,0,0,0,0,1,2,2,1e12])
    assert postprocess(values,'threshold025')[1]==0 and postprocess(values,'threshold025')[2]==.25
    assert np.array_equal(postprocess(values,'nearest_even'),postprocess(values,'threshold_then_nearest_even'))
    x={'a':np.array([.24]),'b':np.array([.26])};w={'a':.5,'b':.5}
    assert convex_combine(x,w,output_policy='threshold025')[0]==.25
    assert convex_combine(x,w,component_policy='threshold025')[0]==.13
    assert np.array_equal(postprocess([.2,.6],'continuous'),[.2,.6])

@pytest.mark.parametrize('bad',[[np.nan],[np.inf],[-.1]])
def test_invalid_predictions(bad):
    with pytest.raises(ValueError):postprocess(bad)

def test_fractional_target_and_zero_case_are_distinct():
    from src.metrics import compute_metrics,smape_include_zero_zero
    truth=np.array([[0.],[.3]])
    exact=truth.copy();rounded=postprocess(exact,'nearest_even')
    assert compute_metrics(truth,exact)['rmse']==0
    assert compute_metrics(truth,rounded)['rmse']>0
    assert compute_metrics(truth,rounded)['smape']==200.
    assert smape_include_zero_zero(truth,rounded)==100.
