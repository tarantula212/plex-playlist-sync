import re
import json

from typing import List

import spotipy
from plexapi.server import PlexServer

from .helperClasses import Playlist, Track, UserInputs
from .plex import update_or_create_plex_playlist
from .logger import setup_logger

from .spotdl import SpotDL

logging = setup_logger(name="Spotify")


def _get_poster_url(images: List[dict]) -> str:
    """Get the first image URL from the list of images.

    Args:
        images (List[dict]): List of image dictionaries
    Returns:
        str: URL of the first image or empty string if no images are available
    """
    return images[0].get("url", "") if len(images) > 0 else ""


def _get_sp_user_playlists(
    sp: spotipy.Spotify, user_id: str, suffix: str = " - Spotify"
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

    try:
        sp_playlists = sp.user_playlists(user_id)
        for sp_playlist in sp_playlists["items"]:
            playlist = Playlist(
                id=sp_playlist["uri"],
                name=sp_playlist["name"] + suffix,
                description=sp_playlist.get("description", ""),
                # playlists may not have a poster in such cases return ""
                poster=_get_poster_url(sp_playlist["images"]),
                tracks=[],
            )
            playlist.tracks = _get_sp_tracks_from_playlist(sp, playlist)
            playlists.append()
    except:
        logging.error("Spotify User ID Error")
    return playlists


def _get_sp_global_playlists(
    sp: spotipy.Spotify, playlist_ids: List[str], suffix: str = " - Spotify"
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
        logging.info(f"({count}/{total}) - Fetching Spotify Playlist ID: {playlist_id}")
        try:
            sp_playlist = sp.playlist(playlist_id)
            playlist = Playlist(
                id=sp_playlist["uri"],
                name=sp_playlist["name"] + suffix,
                description=sp_playlist.get("description", ""),
                # playlists may not have a poster in such cases return ""
                poster=_get_poster_url(sp_playlist["images"]),
            )
            playlist.tracks = _get_sp_tracks_from_playlist(sp, playlist)
            playlists.append(playlist)
            logging.success(json.dumps(playlist.__dict__, indent=4))
        except:
            logging.warning("Spotify Playlist ID error:", playlist_id)

    return playlists


def _cleanup_title(title: str) -> str:
    title_match = re.search(r"^(.*?) (?:\(From|- From|\(Feat\.)", title, re.IGNORECASE)
    return title_match.group(1).strip() if title_match else title


def _cleanup_album_name(album: str) -> str:
    album_match = re.search(
        r'\(From "(.*?)"\)|- From "(.*?)"', album, re.IGNORECASE
    )  # Updated regex to handle both cases

    album = (album_match.group(1) or album_match.group(2)) if album_match else album

    album = re.sub(r"\(feat\.\s*.*?\)", "", album, re.IGNORECASE)

    return album.strip()


def _get_sp_tracks_from_playlist(
    sp: spotipy.Spotify, playlist: Playlist
) -> List[Track]:
    """Return list of tracks with metadata.

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        playlist (Playlist): Playlist object
    Returns:
        List[Track]: list of Track objects with track metadata fields
    """

    def extract_sp_track_metadata(track) -> Track:
        # Title
        original_title = track["track"]["name"]
        title = _cleanup_title(original_title)

        # Artist
        artist = track["track"]["artists"][0]["name"]

        # Album
        original_album = track["track"]["album"]["name"]
        album = _cleanup_album_name(original_album)

        # Tracks may no longer be on spotify in such cases return ""
        url = track["track"]["external_urls"].get("spotify", "")

        return Track(title, original_title, artist, album, original_album, url)

    sp_playlist_tracks = sp.playlist_tracks(playlist.id)

    # Only processes first 100 tracks
    tracks = list(
        map(
            extract_sp_track_metadata,
            [i for i in sp_playlist_tracks["items"] if i.get("track")],
        )
    )

    # If playlist contains more than 100 tracks this loop is useful
    while sp_playlist_tracks["next"]:
        sp_playlist_tracks = sp.next(sp_playlist_tracks)
        tracks.extend(
            list(
                map(
                    extract_sp_track_metadata,
                    [i for i in sp_playlist_tracks["items"] if i.get("track")],
                )
            )
        )
    return tracks


def spotify_playlist_sync(
    sp: spotipy.Spotify, plex: PlexServer, userInputs: UserInputs
) -> None:
    """Create/Update plex playlists with playlists from spotify.

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        plex (PlexServer): A configured PlexServer instance
    """
    # user_playlists = _get_sp_user_playlists(
    #     sp,
    #     userInputs.spotify_user_id,
    #     userInputs.spotify_playlist_ids,
    #     " - Spotify" if userInputs.append_service_suffix else "",
    # )
    spotify_playists = _get_sp_global_playlists(
        sp,
        userInputs.spotify_playlist_ids,
        " - Spotify" if userInputs.append_service_suffix else "",
    )

    if not spotify_playists:
        logging.error("No Spotify playlists found")
        return

    playlists = spotify_playists
    spotdl = SpotDL(userInputs.spotdl_dir, userInputs.download_missing_tracks_dir)
    downloaded = False

    for playlist in playlists:
        missing_tracks = update_or_create_plex_playlist(
            plex, playlist, playlist.tracks, userInputs
        )
        if missing_tracks and userInputs.download_missing_tracks:
            spotdl.download_tracks(missing_tracks)
            downloaded = True

    # refresh plex to scan for downloaded tracks
    if downloaded:
        librarySection = plex.library.section("Music")
        # scan for new media
        librarySection.update()
