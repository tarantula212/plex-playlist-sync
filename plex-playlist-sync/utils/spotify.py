import logging
import re
from typing import List

import spotipy
from plexapi.server import PlexServer

from .helperClasses import Playlist, Track, UserInputs
from .plex import update_or_create_plex_playlist

from .spotdl import SpotDL


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
        for playlist in sp_playlists["items"]:
            playlists.append(
                Playlist(
                    id=playlist["uri"],
                    name=playlist["name"] + suffix,
                    description=playlist.get("description", ""),
                    # playlists may not have a poster in such cases return ""
                    poster=""
                    if len(playlist["images"]) == 0
                    else playlist["images"][0].get("url", ""),
                )
            )
    except:
        logging.error("Spotify User ID Error")
    return playlists

def _cleanup_title(title: str) -> str:
    title_match = re.search(r'^(.*?) (?:\(From|- From|\(Feat\.)', title, re.IGNORECASE)  
    return title_match.group(1).strip() if title_match else title

def _cleanup_album_name(album: str) -> str:
    album_match = re.search(r'\(From "(.*?)"\)|- From "(.*?)"', album, re.IGNORECASE)  # Updated regex to handle both cases
    return (album_match.group(1) or album_match.group(2)) if album_match else album


def _get_sp_tracks_from_playlist(
    sp: spotipy.Spotify, user_id: str, playlist: Playlist
) -> List[Track]:
    """Return list of tracks with metadata.

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        user_id (str): spotify user id
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

    sp_playlist_tracks = sp.user_playlist_tracks(user_id, playlist.id)

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
        user_id (str): spotify user id
        plex (PlexServer): A configured PlexServer instance
    """
    playlists = _get_sp_user_playlists(
        sp,
        userInputs.spotify_user_id,
        " - Spotify" if userInputs.append_service_suffix else "",
    )

    spotdl = SpotDL(userInputs.spotdl_dir, userInputs.download_missing_tracks_dir)
    playlists_filter = [
        "Top 50 - India - Spotify", 
        "Hot Hits Hindi - Spotify", 
        "Trending Now India - Spotify",
        "Discover Weekly - Spotify"
    ]

    downloaded = False
    if playlists:
        for playlist in playlists:
            if playlist.name not in playlists_filter:
                continue
            tracks = _get_sp_tracks_from_playlist(
                sp, userInputs.spotify_user_id, playlist
            )
            missing_tracks = update_or_create_plex_playlist(plex, playlist, tracks, userInputs)
            if missing_tracks and userInputs.download_missing_tracks:
                spotdl.download_tracks(missing_tracks)
                downloaded = True

        # refresh plex to scan for downloaded tracks
        if downloaded:
            librarySection = plex.library.section("Music")
            # scan for new media
            librarySection.update()


    else:
        logging.error("No spotify playlists found for given user")
