from curator.models import CuratorConfig, TrackRequest
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

