from dataclasses import dataclass

@dataclass
class Track:
    title: str
    original_title: str
    artist: str
    album: str
    original_album: str
    url: str


@dataclass
class Playlist:
    id: str
    name: str
    description: str
    poster: str


@dataclass
class UserInputs:
    plex_url: str
    plex_token: str
    plex_users: str

    download_missing_tracks: bool
    download_missing_tracks_dir: str
    spotdl_dir: str

    write_missing_as_csv: bool
    append_service_suffix: bool
    add_playlist_poster: bool
    add_playlist_description: bool
    append_instead_of_sync: bool
    wait_seconds: int

    spotipy_client_id: str
    spotipy_client_secret: str
    spotify_user_id: str

    deezer_user_id: str
    deezer_playlist_ids: str
