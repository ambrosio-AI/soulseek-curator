from curator.slskd import search_timeout_milliseconds


def test_search_timeout_is_sent_to_slskd_as_milliseconds():
    assert search_timeout_milliseconds(15) == 15000


def test_search_timeout_has_minimum_one_millisecond():
    assert search_timeout_milliseconds(0) == 1000
