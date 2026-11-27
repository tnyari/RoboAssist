from collections import deque

import pytest

from offline_stt.system_metrics import ProcessCounters, ProcessTreeSampler


class FakeProvider:
    def __init__(self, snapshots):
        self.snapshots = deque(snapshots)

    def snapshot(self, root_pid):
        assert root_pid == 10
        return self.snapshots.popleft()


def test_process_tree_cpu_is_normalized_to_full_machine_and_memory_is_aggregated():
    provider = FakeProvider(
        [
            {
                10: ProcessCounters(1, 1.0, 100),
                11: ProcessCounters(2, 0.5, 50),
            },
            {
                10: ProcessCounters(1, 1.5, 120),
                11: ProcessCounters(2, 0.75, 80),
            },
        ]
    )
    sampler = ProcessTreeSampler(root_pid=10, logical_cpu_count=2, provider=provider)

    baseline = sampler.sample(1_000_000_000)
    measured = sampler.sample(2_000_000_000)

    assert baseline.cpu_percent is None
    assert baseline.working_set_bytes == 150
    assert measured.process_count == 2
    assert measured.working_set_bytes == 200
    assert measured.cpu_percent == pytest.approx(37.5)
    assert sampler.summary.average_cpu_percent == pytest.approx(37.5)
    assert sampler.summary.peak_working_set_bytes == 200
    assert sampler.summary.process_sample_count == 2
    assert sampler.summary.cpu_interval_count == 1


def test_new_descendant_cpu_time_is_counted_and_pid_reuse_gets_a_new_identity():
    provider = FakeProvider(
        [
            {10: ProcessCounters(1, 2.0, 100)},
            {10: ProcessCounters(1, 2.2, 100), 11: ProcessCounters(2, 0.2, 40)},
            {10: ProcessCounters(1, 2.4, 100), 11: ProcessCounters(3, 0.1, 60)},
        ]
    )
    sampler = ProcessTreeSampler(root_pid=10, logical_cpu_count=1, provider=provider)
    sampler.sample(0)
    first = sampler.sample(1_000_000_000)
    second = sampler.sample(2_000_000_000)

    assert first.cpu_percent == pytest.approx(40)
    assert second.cpu_percent == pytest.approx(30)
    assert sampler.summary.average_cpu_percent == pytest.approx(35)


def test_sampler_rejects_missing_root_and_nonincreasing_time():
    missing = ProcessTreeSampler(
        root_pid=10,
        logical_cpu_count=1,
        provider=FakeProvider([{11: ProcessCounters(1, 0, 1)}]),
    )
    with pytest.raises(RuntimeError, match="Root process"):
        missing.sample(1)

    sampler = ProcessTreeSampler(
        root_pid=10,
        logical_cpu_count=1,
        provider=FakeProvider([{10: ProcessCounters(1, 0, 1)}, {10: ProcessCounters(1, 0.1, 1)}]),
    )
    sampler.sample(10)
    with pytest.raises(ValueError, match="timestamps"):
        sampler.sample(10)
