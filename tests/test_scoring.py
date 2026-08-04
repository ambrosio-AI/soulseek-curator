from curator.models import CuratorConfig, TrackRequest, slskd_destination
from curator.scoring import choose_best


def test_choose_best_prefers_matching_quality_and_title():
    config = CuratorConfig()
    track = TrackRequest(artist="Corona", title="The Rhythm of the Night")
    responses = [
        {
            "username": "demo",
            "hasFreeUploadSlot": True,
            "queueLength": 0,
            "uploadSpeed": 512,
            "files": [
                {
                    "filename": "Corona - The Rhythm of the Night.flac",
                    "extension": "flac",
                    "size": 1000,
                },
                {
                    "filename": "Unrelated.mp3",
                    "extension": "mp3",
                    "bitRate": 320,
                    "size": 1000,
                },
            ],
        }
    ]
    candidates = choose_best(track, responses, config, "flac")
    assert candidates
    assert candidates[0].filename.endswith(".flac")
    assert candidates[0].score >= config.confidence_threshold


def test_choose_best_supports_wav_quality():
    config = CuratorConfig()
    track = TrackRequest(artist="Demo", title="Track")
    responses = [
        {
            "username": "demo",
            "hasFreeUploadSlot": True,
            "queueLength": 0,
            "uploadSpeed": 512,
            "files": [
                {
                    "filename": "Demo - Track.wav",
                    "extension": "wav",
                    "size": 42000000,
                },
            ],
        }
    ]
    candidates = choose_best(track, responses, config, "wav")
    assert candidates
    assert candidates[0].quality == "wav"


def test_slskd_destination_prefixes_category_inside_downloads():
    destination = slskd_destination("/downloads", "BBQ/verano-2026", "", "rock")
    assert destination == "BBQ/verano-2026/rock"


def test_slskd_destination_strips_absolute_slskd_root():
    destination = slskd_destination("/downloads", "BBQ", "/downloads/BBQ/90s", "90s")
    assert destination == "BBQ/90s"
