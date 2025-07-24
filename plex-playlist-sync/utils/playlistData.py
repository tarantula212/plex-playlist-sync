import os
import json
from typing import List
from dataclasses import dataclass, asdict

from .logger import setup_logger
from .helperClasses import Track, Playlist

logging = setup_logger(name="PlaylistData")


@dataclass
class TrackData:
    number: int
    title: str
    original_title: str
    alternate_titles: List[str]
    artist: str
    album: str
    original_album: str
    alternate_albums: List[str]
    url: str
    plex_search: List[str]
    status: str
    spotdl: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class PlaylistData:
    id: str
    name: str
    description: str
    poster: str
    tracks: List[TrackData]

    @staticmethod
    def from_json(json_str: str) -> "PlaylistData":
        data = json.loads(json_str)
        tracks = [
            TrackData(
                number=track["number"],
                title=track.get("title", ""),
                original_title=track.get("original_title", ""),
                alternate_titles=track.get("alternate_titles", []),
                artist=track.get("artist", ""),
                album=track.get("album", ""),
                original_album=track.get("original_album", ""),
                alternate_albums=track.get("alternate_albums", []),
                url=track.get("url", ""),
                plex_search=track.get("plex_search", []),
                status=track.get("status", ""),
            )
            for track in (data["tracks"] or [])
        ]
        return PlaylistData(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            poster=data.get("poster", ""),
            tracks=tracks,
        )

    def to_json(self) -> str:
        data_dict = asdict(self)
        data_dict["tracks"] = [track.to_dict() for track in self.tracks]
        return json.dumps(data_dict, indent=4)


class PlaylistDataHelper:
    def __init__(self, file_dir: str):
        """
        Initialize the Data class with a path to the JSON file.
        """
        self.file_dir = file_dir
        self._data: PlaylistData = None  # Default to an empty dictionary
        self._tracks_index: List[TrackData] = None

    def load(self, playlist: Playlist) -> None:
        """
        Load JSON data from the specified file. If the file is missing, initialize with an empty dictionary.
        """
        file_path = os.path.join(self.file_dir, f"{playlist.id}.json")
        try:
            with open(file_path, "r") as file:
                json_content = file.read()
                self._data = PlaylistData.from_json(json_content)
                logging.debug(f"Data successfully loaded from {file_path}")
        except FileNotFoundError:
            logging.debug(
                f"File not found: {file_path}. Initializing with an empty dictionary."
            )
        except json.JSONDecodeError as e:
            logging.error(
                f"Error decoding JSON: {e}. Initializing with an empty dictionary."
            )

        if not self._data:
            self._data = PlaylistData(
                id="",
                name="",
                description="",
                poster="",
                tracks=[],
            )

        # override the playlist id and name with the given playlist
        self._data.id = playlist.id
        self._data.name = playlist.name
        self._data.description = playlist.description
        self._data.poster = playlist.poster

    def _gen_track_key(self, original_title: str, original_album: str) -> str:
        """
        Generate a key for the given track.
        """
        return f"{original_title} - {original_album}"

    def _index_tracks(self) -> None:
        """
        Index the given list of tracks by their key.
        """
        self._tracks_index = {}
        for track in self._data.tracks:
            key = self._gen_track_key(track.original_title, track.original_album)
            self._tracks_index[key] = track

    def get_track_data(self, track: Track) -> TrackData:
        """
        Get the TrackData object for the given key.
        """
        if not self._tracks_index:
            self._index_tracks()

        key = self._gen_track_key(track.original_title, track.original_album)
        if key in self._tracks_index:
            return self._tracks_index[key]

        return None

    def update_tracks(self, tracks: List[TrackData]) -> None:
        """
        Update the tracks in the data with the given list of tracks.
        """
        self._data.tracks = tracks
        self._tracks_index = None

    def save(self) -> None:
        """
        Save the current data to the specified file in JSON format.
        """
        try:
            file_path = os.path.join(self.file_dir, f"{self._data.id}.json")
            with open(file_path, "w") as file:
                file.write(self._data.to_json())
                logging.info(f"Data successfully saved to {file_path}")
        except Exception as e:
            logging.error(f"Error saving data: {e}")
