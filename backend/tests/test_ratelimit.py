from qanoun_api.ratelimit import RateLimit


def test_sliding_window_blocks_then_recovers():
    limit = RateLimit("t", limit=2, window=60)
    assert limit.check("ip", now=0) is None
    assert limit.check("ip", now=1) is None
    assert limit.check("ip", now=2) == 58  # third hit within the window: wait for the first to expire
    assert limit.check("other", now=2) is None  # per client
    assert limit.check("ip", now=60.5) is None  # first hit has left the window
