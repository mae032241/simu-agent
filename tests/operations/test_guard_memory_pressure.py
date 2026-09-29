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


def test_memory_sampling_does_not_require_dirty(monkeypatch):
    monkeypatch.setattr(guard.Path, 'read_text', lambda _: 'MemAvailable: 12000000 kB\n')
    assert guard.memory()=={'MemAvailable':12_000_000*1024}


def test_ram_shortage_and_drop_are_immediate():
    config=limits();baseline=snapshot(config)
    watch=guard.MemoryPressure(baseline,config)
    assert watch.sample(snapshot(config,dirty=4_000_000_000))==[]
    low=snapshot(config,available=config['minimum_available_bytes']-1)
    assert 'available_below_minimum' in watch.sample(low)
    drop=snapshot(config,available=baseline['MemAvailable']-config['available_drop_stop_bytes']-1)
    assert watch.sample(drop)==['available_drop']


@pytest.mark.process_e2e
@pytest.mark.parametrize('scenario', ['sustained_dirty','dirty_at_start','rss','timeout','low_available','runtime_low_available','runtime_drop'])
def test_guard_process_limits_remain_effective(tmp_path,monkeypatch,scenario):
    config=limits();config.update(sample_interval_seconds=.01,timeout_seconds=3)
    clean=snapshot(config);high=snapshot(config,dirty=4_000_000_000)
    count=0
    def memory():
        nonlocal count
        count+=1
        if scenario=='dirty_at_start':return high
        if scenario=='low_available':return snapshot(config,available=config['minimum_available_bytes']-1)
        if count==1:return clean
        if scenario=='runtime_low_available':return snapshot(config,available=config['minimum_available_bytes']-1)
        if scenario=='runtime_drop':return snapshot(config,available=clean['MemAvailable']-config['available_drop_stop_bytes']-1)
        return high
    monkeypatch.setattr(guard,'memory',memory)
    if scenario=='rss':
        monkeypatch.setattr(guard,'_descendant_rss_kib',lambda _: (set(),config['observed_tree_rss_stop_bytes']//1024+1))
    if scenario=='timeout':config['timeout_seconds']=.03
    marker=tmp_path/'child_started'
    script="import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(.25)"
    with (tmp_path/'inherited').open('w') as lock:
        result=guard.run_one([sys.executable,'-c',script,str(marker)],dict(os.environ),config,tmp_path,lock.fileno())
    if scenario in {'sustained_dirty','dirty_at_start'}:
        assert result['returncode']==0 and result['stop_reason']=='exited'
        assert result['memory_stop_triggers']==[]
        assert marker.exists()
        assert 'dirty_pressure' not in result
    elif scenario=='low_available':
        assert result['stop_reason']=='system_memory_admission'
        assert not marker.exists()
        assert result['memory_stop_triggers']==['available_below_minimum']
    elif scenario in {'runtime_low_available','runtime_drop'}:
        assert result['stop_reason']=='system_memory_stop'
        expected=['available_below_minimum','available_drop'] if scenario=='runtime_low_available' else ['available_drop']
        assert result['memory_stop_triggers']==expected
    else:
        assert result['stop_reason']=={'rss':'observed_tree_rss_limit','timeout':'timeout'}[scenario]
        assert result['memory_stop_triggers']==[]



def test_resource_configuration_is_part_of_acceptance_fingerprint(tmp_path,monkeypatch):
    from scripts import accept_b6
    for name in ('test_resources.json','root_host_resources.json'):
        (tmp_path/name).write_text('{}')
    monkeypatch.setattr(accept_b6,'SCRIPTS',tmp_path)
    original=accept_b6.harness_digest()
    (tmp_path/'test_resources.json').write_text('{"limits":{"timeout_seconds":10}}')
    assert accept_b6.harness_digest()!=original
