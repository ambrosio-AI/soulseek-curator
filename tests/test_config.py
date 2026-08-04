from curator.config import load_config


def test_load_config_adds_wav_to_existing_fallback_order(tmp_path):
    path = tmp_path / "curator.yaml"
    path.write_text(
        """
slskd_url: http://example:5030
fallback_order:
  - flac
  - mp3_320
  - mp3_v0
  - mp3_any
quality_profiles:
  flac:
    extensions: [flac]
  mp3_320:
    extensions: [mp3]
    min_bitrate: 300
  mp3_v0:
    extensions: [mp3]
    min_bitrate: 220
  mp3_any:
    extensions: [mp3]
    min_bitrate: 128
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert "wav" in config.quality_profiles
    assert config.fallback_order == ["flac", "wav", "mp3_320", "mp3_v0", "mp3_any"]


def test_load_config_defaults_deep_lossless_search_on_for_old_files(tmp_path):
    path = tmp_path / "curator.yaml"
    path.write_text("slskd_url: http://example:5030\n", encoding="utf-8")

    config = load_config(path)

    assert config.deep_lossless_search is True
