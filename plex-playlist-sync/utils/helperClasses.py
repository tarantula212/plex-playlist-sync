from dataclasses import dataclass
from typing import List


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
    tracks: List[Track]


@dataclass
class UserInputs:
    config_dir: str

    plex_url: str
    plex_token: str
    plex_users: List[str]

    download_missing_tracks: bool
    download_missing_tracks_dir: str
    spotdl_dir: str

    write_missing_as_csv: bool
    append_service_suffix: bool
    add_playlist_poster: bool
    add_playlist_description: bool
    append_instead_of_sync: bool
    wait_seconds: int

    # ytmusic config
    ytmusic_sync_enabled: bool
    ytmusic_playlist_ids: List[str]