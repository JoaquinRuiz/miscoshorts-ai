from miscoshorts.smartcrop import smooth_track


def test_smooth_track_fills_gaps_and_ignores_jitter():
    times = [0, 1, 2, 3, 4, 5]
    centers = [None, 500, 505, None, 495, 500]
    track = smooth_track(times, centers, default=960, dead_zone=50)
    assert all(abs(x - 500) < 1e-6 for x in track)  # first face backfills the start


def test_smooth_track_follows_big_moves():
    track = smooth_track(list(range(20)), [500] * 5 + [1200] * 15, default=960, dead_zone=50, alpha=0.5)
    assert track[4] == 500
    assert 500 < track[5] < 1200
    assert abs(track[-1] - 1200) < 1


def test_smooth_track_without_faces_uses_default():
    assert smooth_track([0, 1], [None, None], default=960, dead_zone=50) == [960, 960]
