"""No real memory pressure: inject /proc samples into the serial supervisor."""
import json
import os
import sys

import pytest

from scripts import run_tests as guard


def limits():
    return json.loads(guard.DEFAULT_CONFIG.read_text())['limits']


def snapshot(config, *, dirty=0, available=None):
    return dict(Dirty=dirty, MemAvailable=available if available is not None else config['minimum_available_bytes']+4_000_000_000)


def test_transient_dirty_resets_continuous_window_and_keeps_peak():
    config=limits();watch=guard.MemoryPressure(snapshot(config),config)
    high=snapshot(config,dirty=config['dirty_stop_bytes']+1)
    assert watch.sample(high,10)==[]
    assert watch.sample(high,14.9)==[]
    assert watch.sample(snapshot(config),15)==[]
    assert watch.sample(high,16)==[]
    assert watch.sample(high,20.9)==[]
    assert watch.sample(high,21)==['dirty_sustained']
    assert watch.evidence()['episodes']==2
    assert watch.evidence()['high_water_bytes']==high['Dirty']
    assert watch.evidence()['longest_observed_seconds']==5


def test_ram_shortage_and_drop_are_immediate_during_dirty_grace():
    config=limits();baseline=snapshot(config)
    watch=guard.MemoryPressure(baseline,config)
    dirty=config['dirty_stop_bytes']+1
    assert watch.sample(snapshot(config,dirty=dirty),0)==[]
    low=snapshot(config,dirty=dirty,available=config['minimum_available_bytes']-1)
    assert 'available_below_minimum' in watch.sample(low,.01)
    drop=snapshot(config,dirty=dirty,available=baseline['MemAvailable']-config['available_drop_stop_bytes']-1)
    assert watch.sample(drop,.02)==['available_drop']


@pytest.mark.process_e2e
@pytest.mark.parametrize('scenario', ['transient','sustained','admission','rss','timeout','low_available'])
def test_guard_process_limits_remain_effective(tmp_path,monkeypatch,scenario):
    config=limits();config.update(dirty_stop_grace_seconds=.1,sample_interval_seconds=.01,timeout_seconds=3)
    clean=snapshot(config);high=snapshot(config,dirty=config['dirty_stop_bytes']+1)
    count=0
    def memory():
        nonlocal count
        count+=1
        if scenario=='admission':return high
        if scenario=='low_available':return snapshot(config,available=config['minimum_available_bytes']-1)
        if count==1:return clean
        if scenario=='transient':return high if count<=3 else clean
        return high
    monkeypatch.setattr(guard,'memory',memory)
    if scenario=='rss':
        monkeypatch.setattr(guard,'_descendant_rss_kib',lambda _: (set(),config['observed_tree_rss_stop_bytes']//1024+1))
    if scenario=='timeout':config['timeout_seconds']=.03
    marker=tmp_path/'child_started'
    script="import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(.25)"
    with (tmp_path/'inherited').open('w') as lock:
        result=guard.run_one([sys.executable,'-c',script,str(marker)],dict(os.environ),config,tmp_path,lock.fileno())
    if scenario=='transient':
        assert result['returncode']==0 and result['stop_reason']=='exited'
        assert result['memory_stop_triggers']==[]
        assert result['dirty_pressure']['episodes']==1
    elif scenario in {'admission','low_available'}:
        assert result['stop_reason']=='system_memory_admission'
        assert not marker.exists()
        assert result['memory_stop_triggers']==(['dirty_sustained'] if scenario=='admission' else ['available_below_minimum'])
    elif scenario=='sustained':
        assert result['stop_reason']=='system_memory_stop'
        assert result['memory_stop_triggers']==['dirty_sustained']
    else:
        assert result['stop_reason']=={'rss':'observed_tree_rss_limit','timeout':'timeout'}[scenario]
        assert result['memory_stop_triggers']==[]


@pytest.mark.parametrize('grace', [0,-1,True,float('nan'),float('inf')])
def test_invalid_grace_cannot_disable_stop_or_make_admission_wait_forever(grace):
    config=limits();config['dirty_stop_grace_seconds']=grace
    with pytest.raises(ValueError,match='finite and positive'):
        guard.MemoryPressure(snapshot(config),config)


def test_resource_configuration_is_part_of_acceptance_fingerprint(tmp_path,monkeypatch):
    from scripts import accept_b6
    for name in ('test_resources.json','root_host_resources.json'):
        (tmp_path/name).write_text('{}')
    monkeypatch.setattr(accept_b6,'SCRIPTS',tmp_path)
    original=accept_b6.harness_digest()
    (tmp_path/'test_resources.json').write_text('{"limits":{"dirty_stop_grace_seconds":10}}')
    assert accept_b6.harness_digest()!=original
