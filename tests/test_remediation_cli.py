"""Subprocess entrypoint integration with isolated real files and a real server."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]


def command(script, *args, cwd, env=None):
    return subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts'/script),*map(str,args)],
                          cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',timeout=90)


@pytest.fixture(scope='module')
def cli_files(tmp_path_factory):
    root=tmp_path_factory.mktemp('cli-real'); cache=root/'cache'; cache.mkdir()
    dates=pd.date_range('2024-01-01',periods=400)
    y=np.zeros((400,2),dtype='float32'); y[::3,0]=.5; y[::5,1]=1.2
    np.savez_compressed(cache/'panel.npz',dates=dates.to_numpy(),y=y,stock=np.ones_like(y))
    (cache/'catalogs.json').write_text(json.dumps({'warehouses':['w'],'articles':['a','b']}))
    selection=root/'selection.json'
    selection.write_text(json.dumps({'winner':'lgb_tweedie_z0.25','objectives':{'lgb_tweedie':'tweedie'},'rounds':3}))
    model=root/'model'
    result=command('train_final.py','--cache-dir',cache,'--selection',selection,'--output-dir',model,cwd=root)
    assert result.returncode==0,result.stderr
    sales=pd.DataFrame({'date':np.repeat(dates.strftime('%Y-%m-%d'),2),
                         'warehouse_name':'w','article':np.tile(['a','b'],400),'quantity':y.reshape(-1)})
    for col in ['composite_division','cities_name','category_lvl_1','category_lvl_2','category_lvl_3','characteristic']:
        sales[col]='x'
    sales['sales_sum']=sales['discount_sum']=0.
    sales.to_csv(root/'sales_dataset_hakaton_train.csv',index=False)
    stock=sales[['date','warehouse_name','article']].assign(stock=1.)
    stock.to_csv(root/'stock_dataset_hakaton_train.csv',index=False)
    return root,cache,selection,model


def test_train_entrypoint_traceable_and_deterministic(cli_files):
    root,cache,selection,model=cli_files
    repeat=root/'repeat_model'
    result=command('train_final.py','--cache-dir',cache,'--selection',selection,'--output-dir',repeat,cwd=root)
    assert result.returncode==0,result.stderr
    assert (repeat/'lightgbm.txt').read_bytes()==(model/'lightgbm.txt').read_bytes()
    manifest=json.loads((model/'manifest.json').read_text())
    assert manifest['provenance']['status']=='training_recorded'
    assert (model/'training_record.json').exists()


def test_audit_backtest_predict_validate_and_evaluate_entrypoints(cli_files):
    root,cache,selection,model=cli_files
    audit=root/'audit.json'
    result=command('audit_inputs.py','--data-dir',root,'--output',audit,cwd=root)
    assert result.returncode==0,result.stderr
    assert json.loads(audit.read_text(encoding='utf-8'))['sales']['rows']==800
    backtest=root/'backtest.csv'
    result=command('backtest_baselines.py','--cache-dir',cache,'--output',backtest,cwd=root)
    assert result.returncode==0,result.stderr
    assert len(pd.read_csv(backtest))==18
    files=[]
    for name in ['forecast.csv','repeat.csv']:
        file=root/name; files.append(file)
        result=command('predict.py','--sales',root/'sales_dataset_hakaton_train.csv','--stock',root/'stock_dataset_hakaton_train.csv',
                       '--model',model,'--output',file,cwd=root)
        assert result.returncode==0,result.stderr
    assert files[0].read_bytes()==files[1].read_bytes()
    frame=pd.read_csv(files[0]); assert len(frame)==128
    origin=str(pd.Timestamp('2024-01-01')+pd.Timedelta(days=399))[:10]
    result=command('validate_submission.py','--input',files[0],'--model',model,'--origin',origin,cwd=root)
    assert result.returncode==0,result.stderr
    leaderboard=root/'leaderboard.csv'
    result=command('official_score.py','--truth',files[0],'--submissions',files[1],'--method','rank','--output',leaderboard,cwd=root)
    assert result.returncode==0,result.stderr
    assert leaderboard.exists()
    frame.loc[0,'quantity']=-1; frame.to_csv(root/'bad.csv',index=False)
    result=command('validate_submission.py','--input',root/'bad.csv','--model',model,'--origin',origin,cwd=root)
    assert result.returncode==2 and 'Ошибка' in result.stderr


def test_package_entrypoint_explicit_legacy_status(cli_files):
    import shutil
    root,_,_,model=cli_files
    legacy=root/'legacy'; shutil.copytree(model,legacy)
    (legacy/'manifest.json').unlink()
    result=command('package_model.py','--model-dir',legacy,cwd=root)
    assert result.returncode==0,result.stderr
    assert json.loads((legacy/'manifest.json').read_text())['provenance']['status']=='reconstructed_unverified'


@pytest.mark.parametrize('script,args',[
    ('audit_inputs.py',['--data-dir','missing']),
    ('backtest_baselines.py',['--cache-dir','missing']),
    ('train_final.py',['--cache-dir','missing','--selection','missing']),
    ('package_model.py',['--model-dir','missing']),
    ('predict.py',['--sales','missing','--stock','missing']),
    ('validate_submission.py',['--input','missing']),
])
def test_missing_files_clear_exit_two(tmp_path,script,args):
    result=command(script,*args,cwd=tmp_path)
    assert result.returncode==2,result
    assert 'Ошибка' in result.stderr
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('script',['audit_inputs.py','backtest_baselines.py','train_final.py','package_model.py','predict.py','validate_submission.py','official_score.py','run_pipeline.py'])
def test_entrypoint_help_and_unknown_option(tmp_path,script):
    assert command(script,'--help',cwd=tmp_path).returncode==0
    assert command(script,'--nonexistent-option',cwd=tmp_path).returncode==2


def test_training_rejects_invalid_config_without_output(cli_files):
    root,cache,_,_=cli_files
    selection=root/'invalid_selection.json'; selection.write_text('{"winner":"bad"}')
    result=command('train_final.py','--cache-dir',cache,'--selection',selection,'--output-dir',root/'not_written',cwd=root)
    assert result.returncode==2 and not (root/'not_written').exists()
    result=command('train_final.py','--rounds','0',cwd=root)
    assert result.returncode==2


def test_real_api_startup_foreign_cwd_and_missing_bundle(cli_files):
    root,_,_,model=cli_files
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    env=dict(os.environ,MODEL_DIR=str(model),WEB_CONCURRENCY='1',UVICORN_WORKERS='1')
    args=[sys.executable,'-m','uvicorn','app.main:app','--app-dir',str(ROOT),'--host','127.0.0.1','--port',str(port),'--workers','1']
    process=subprocess.Popen(args,cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.5) as response:
                    assert json.load(response)['model_loaded']
                break
            except (OSError,ValueError):
                assert process.poll() is None
                time.sleep(.05)
        else:
            pytest.fail('API не запустился')
    finally:
        process.terminate(); process.wait(timeout=10)
    env['MODEL_DIR']=str(root/'missing')
    result=subprocess.run(args,cwd=root,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'Application startup failed' in result.stderr


def test_pipeline_real_entrypoint_isolated_outputs_and_invalid_inputs(tmp_path):
    from src.predict import load_bundle
    data=tmp_path/'source'; data.mkdir()
    dates=pd.date_range('2024-01-01',periods=600)
    sales=pd.DataFrame({'date':np.repeat(dates.strftime('%Y-%m-%d'),2),
                         'warehouse_name':'w','article':np.tile(['a','b'],600),
                         'quantity':np.tile([.3,1.],600)})
    sales.to_csv(data/'sales_dataset_hakaton_train.csv',index=False)
    sales.drop(columns='quantity').assign(stock=2.).to_csv(data/'stock_dataset_hakaton_train.csv',index=False)
    workspace=tmp_path/'pipeline'
    result=command('run_pipeline.py','--data-dir',data,'--work-dir',workspace,'--refresh','--rounds','2',cwd=tmp_path)
    assert result.returncode==0,result.stderr
    assert len(pd.read_csv(workspace/'submission.csv'))==128
    assert len(pd.read_csv(workspace/'reports/experiment_results.csv'))>=19
    assert load_bundle(workspace/'model')['manifest']['bundle_id']
    result=command('run_pipeline.py','--data-dir',tmp_path/'missing','--work-dir',tmp_path/'bad','--refresh','--rounds','2',cwd=tmp_path)
    assert result.returncode==2 and 'Ошибка pipeline' in result.stderr
    result=command('run_pipeline.py','--work-dir',tmp_path/'untouched','--rounds','0',cwd=tmp_path)
    assert result.returncode==2 and not (tmp_path/'untouched').exists()
