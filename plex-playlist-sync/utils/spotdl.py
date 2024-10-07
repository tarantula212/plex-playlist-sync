import os
import json

from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions, SpotifyOptions
from typing import List

from .helperClasses import Track

class SpotDL:
    def __init__(self, spotdl_dir: str, download_dir: str):
        config = self._get_config(os.path.join(spotdl_dir, "config.json"))
        spotifyOptions = SpotifyOptions(**config, cache_path=os.path.join(spotdl_dir, ".spotify"))
        config["output"] = os.path.join(download_dir, config["output"])
        downloaderOptions = DownloaderOptions(
            **config,
            cookie_file=os.path.join(spotdl_dir, "youtube_cookies.txt"),
        )
        self._spotdl = Spotdl(
            client_id=spotifyOptions["client_id"],
            client_secret=spotifyOptions["client_secret"],
            cache_path=spotifyOptions["cache_path"],
            downloader_settings=downloaderOptions
        )

    def _get_config(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as config_file:
            return json.load(config_file)

    def download_tracks(self, tracks: List[Track]):
         # tracks to download
        query = []
        for track in tracks:
            query.append(track.url)

        # download tracks
        songs = self._spotdl.search(query)
        result = self._spotdl.download_songs(songs)
        print(result)


