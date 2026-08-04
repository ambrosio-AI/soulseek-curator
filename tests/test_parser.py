from curator.parser import parse_track_list


def test_parse_txt_artist_title_category():
    tracks = parse_track_list("list.txt", b"Corona - The Rhythm of the Night | 90s dance\n")
    assert len(tracks) == 1
    assert tracks[0].artist == "Corona"
    assert tracks[0].title == "The Rhythm of the Night"
    assert tracks[0].category == "90s dance"


def test_parse_csv_spanish_headers():
    payload = "categoria,artista,tema\nrock,System of a Down,Chop Suey!\n".encode()
    tracks = parse_track_list("list.csv", payload)
    assert tracks[0].artist == "System of a Down"
    assert tracks[0].title == "Chop Suey!"
    assert tracks[0].category == "rock"


def test_parse_json_objects():
    payload = b'[{"artist":"A","title":"B","category":"C"}]'
    tracks = parse_track_list("list.json", payload)
    assert tracks[0].display_name == "A - B"
    assert tracks[0].category == "C"

