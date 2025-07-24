import re
import json

from typing import List

from ytmusicapi import YTMusic
from plexapi.server import PlexServer

from .helperClasses import Playlist, Track, UserInputs
from .plex import update_or_create_plex_playlist
from .logger import setup_logger

from .spotdl import SpotDL

logging = setup_logger(name="Spotify")


def _get_tracks(yt_tracks) -> List[Track]:
    """Return list of tracks with metadata.

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        playlist (Playlist): Playlist object
    Returns:
        List[Track]: list of Track objects with track metadata fields
    """

    def extract_track_metadata(track) -> Track:
        # Title
        original_title = track["title"]
        title = _cleanup_title(original_title)

        # Artist
        artist = track["artists"][0]["name"]

        # Album
        original_album = track["album"]["name"] if track.get("album") else ""
        album = _cleanup_album_name(original_album)

        # Tracks may no longer be on spotify in such cases return ""
        # url = track["external_urls"].get("spotify", "")
        url = ""  # TODO

        return Track(title, original_title, artist, album, original_album, url)

    # Only processes first 100 tracks
    tracks = list(
        map(
            extract_track_metadata,
            [i for i in yt_tracks],
        )
    )

    # # If playlist contains more than 100 tracks this loop is useful
    # while sp_playlist_tracks["next"]:
    #     sp_playlist_tracks = sp.next(sp_playlist_tracks)
    #     tracks.extend(
    #         list(
    #             map(
    #                 extract_sp_track_metadata,
    #                 [i for i in sp_playlist_tracks["items"] if i.get("track")],
    #             )
    #         )
    #     )
    return tracks


def _get_poster_url(images) -> str:
    """Get the best thumbnail from the list of images.

    Args:
        images (list): List of images
    Returns:
        str: URL of the best thumbnail
    """
    if len(images) == 0:
        return ""

    # Sort images by width and return the largest one
    best_image = max(images, key=lambda x: x.get("width", 0))
    return best_image.get("url", "")


def _get_global_playlists(
    yt: YTMusic, playlist_ids: List[str], suffix: str = " - YTMusic"
) -> List[Playlist]:
    """Get metadata for playlists in the given user_id.

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        userId (str): UserId of the spotify account (get it from open.spotify.com/account)
        suffix (str): Identifier for source
    Returns:
        List[Playlist]: list of Playlist objects with playlist metadata fields
    """
    playlists = []
    count = 0
    total = len(playlist_ids)
    for playlist_id in playlist_ids:
        count += 1
        logging.info(f"({count}/{total}) - Fetching YTMusic Playlist ID: {playlist_id}")
        try:
            yt_playlist = yt.get_playlist(playlist_id)

            playlist = Playlist(
                id=f"ytmusic:playlist:{playlist_id}",
                name=yt_playlist["title"] + suffix,
                description=yt_playlist.get("description", ""),
                poster=_get_poster_url(yt_playlist["thumbnails"]),
                tracks=_get_tracks(yt_playlist["tracks"]),
            )
            playlists.append(playlist)
            # logging.success(json.dumps(playlist.__dict__, indent=4))
        except:
            logging.warning("YTMusic Playlist ID error:", playlist_id)

    return playlists


def _cleanup_title(title: str) -> str:
    title_match = re.search(r"^(.*?) (?:\(From|- From|\(Feat\.|\(Movie)", title, re.IGNORECASE)
    return title_match.group(1).strip() if title_match else title


def _cleanup_album_name(album: str) -> str:
    album_match = re.search(
        r'\(From\s*"(.*?)"\)|- From\s*"(.*?)"', album, re.IGNORECASE
    )  # Updated regex to handle both cases

    album = (album_match.group(1) or album_match.group(2)) if album_match else album

    album = re.sub(r"\(feat\.\s*.*?\)", "", album, re.IGNORECASE)

    return album.strip()


def ytmusic_playlist_sync(
    yt: YTMusic, plex: PlexServer, userInputs: UserInputs
) -> None:
    """Create/Update plex playlists with playlists from spotify.

    Args:
        yt (YTMusic): YTMusic configured instance
        plex (PlexServer): A configured PlexServer instance

    """
    playlists = _get_global_playlists(
        yt,
        userInputs.ytmusic_playlist_ids,
        " - YTMusic" if userInputs.append_service_suffix else "",
    )

    if not playlists:
        logging.error("No YTMusic playlists found")
        return

    spotdl = SpotDL(userInputs.spotdl_dir, userInputs.download_missing_tracks_dir)
    downloaded = False
    for playlist in playlists:
        missing_tracks = update_or_create_plex_playlist(plex, playlist, userInputs)
        if missing_tracks and userInputs.download_missing_tracks:
            spotdl.download_tracks(missing_tracks)
            downloaded = True

    # refresh plex to scan for downloaded tracks
    if downloaded:
        librarySection = plex.library.section("Music")
        # scan for new media
        librarySection.update()
