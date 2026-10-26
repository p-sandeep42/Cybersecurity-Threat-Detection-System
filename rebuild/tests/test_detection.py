import random

from platform_app.detection import evaluate


def test_brute_force_threshold_and_inclusive_boundary(event_factory):
    events = [event_factory(seconds=second) for second in (0, 1, 2, 3)]
    assert evaluate(events) == []
    events.append(event_factory(seconds=300))
    episodes = evaluate(events)
    assert len(episodes) == 1
    assert episodes[0].rule_id == "AUTH-001"
    assert len(episodes[0].evidence) == 5
    events[-1] = event_factory(seconds=300.001)
    assert evaluate(events) == []


def test_spray_counts_distinct_subjects(event_factory):
    same_account = [event_factory(seconds=index) for index in range(10)]
    assert not any(alert.rule_id == "AUTH-002" for alert in evaluate(same_account))
    spray = [event_factory(seconds=index, subject_id=f"account-{index}") for index in range(10)]
    assert [alert.rule_id for alert in evaluate(spray)] == ["AUTH-002"]


def test_success_rule_requires_strictly_preceding_failures(event_factory):
    events = [event_factory(seconds=0) for _ in range(5)]
    assert not any(
        alert.rule_id == "AUTH-003"
        for alert in evaluate(
            [
                *events,
                event_factory(seconds=0, outcome="success"),
            ]
        )
    )
    assert any(
        alert.rule_id == "AUTH-003"
        for alert in evaluate(
            [
                *events,
                event_factory(seconds=600, outcome="success"),
            ]
        )
    )
    assert not any(
        alert.rule_id == "AUTH-003"
        for alert in evaluate(
            [
                *events,
                event_factory(seconds=600.001, outcome="success"),
            ]
        )
    )


def test_order_independence_and_separate_incidents(event_factory):
    events = [event_factory(seconds=second) for second in (*range(5), *range(1000, 1005))]
    expected = evaluate(events)
    random.Random(17).shuffle(events)
    assert evaluate(events) == expected
    assert len(expected) == 2
    assert expected[0].evidence.isdisjoint(expected[1].evidence)


def test_legitimate_spaced_logins_and_high_latency_do_not_alert(event_factory):
    events = [
        event_factory(seconds=index * 400, response_duration_ms=60000.0) for index in range(5)
    ]
    assert evaluate(events) == []
