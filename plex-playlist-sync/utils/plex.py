import csv
import re
import logging
import pathlib
import sys
from difflib import SequenceMatcher
from typing import List

import plexapi
from plexapi.exceptions import BadRequest, NotFound
from plexapi.server import PlexServer
from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions, SpotifyOptions
import json
import os

from .helperClasses import Playlist, Track, UserInputs

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def get_config(config_path: str):
    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)

def _download_missing_tracks(tracks: List[Track], userInputs: UserInputs):
    spotdl_dir = userInputs.spotdl_dir
    config = get_config(os.path.join(spotdl_dir, "config.json"))
    spotifyOptions = SpotifyOptions(**config, cache_path=os.path.join(spotdl_dir, ".spotify"))
    config["output"] = os.path.join(userInputs.download_missing_tracks_dir, config["output"])
    downloaderOptions = DownloaderOptions(
        **config,
        cookie_file=os.path.join(spotdl_dir, "youtube_cookies.txt"),
    )
    spotdl = Spotdl(
        client_id=spotifyOptions["client_id"],
        client_secret=spotifyOptions["client_secret"],
        cache_path=spotifyOptions["cache_path"],
        downloader_settings=downloaderOptions
    )

    query = []
    for track in tracks:
        query.append(track.url)

    songs = spotdl.search(query)
    result = spotdl.download_songs(songs)
    print(result)


def _write_csv(tracks: List[Track], name: str, path: str = "/config/data") -> None:
    """Write given tracks with given name as a csv.

    Args:
        tracks (List[Track]): List of Track objects
        name (str): Name of the file to write
        path (str): Root directory to write the file
    """
    # pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    data_folder = pathlib.Path(path)
    data_folder.mkdir(parents=True, exist_ok=True)
    file = data_folder / f"{name}.csv"

    with open(file, "w", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(Track.__annotations__.keys())
        for track in tracks:
            writer.writerow(
                [track.title, track.artist, track.album, track.url]
            )


def _delete_csv(name: str, path: str = "/config/data") -> None:
    """Delete file associated with given name

    Args:
        name (str): Name of the file to delete
        path (str, optional): Root directory to delete the file from
    """
    data_folder = pathlib.Path(path)
    file = data_folder / f"{name}.csv"
    file.unlink()

def _clean_album_name(album: str) -> str:
    """Clean the album name by removing specified phrases in any case and bracketed."""

    # Remove phrases
    phrases_to_remove = [
        'original motion picture soundtrack',
        'deluxe edition',
    ]
    for phrase in phrases_to_remove:
        album = re.sub(r'\(?\s*' + re.escape(phrase) + r'\s*\)?', '', album, flags=re.IGNORECASE).strip()

    # Replace words
    words_to_replace = [
        ['&', 'And'],
        ['-', ''],
        ['(', ''],
        [')', ''],
    ]
    for word_pair in words_to_replace:  # Changed variable name for clarity
        album = album.replace(word_pair[0], word_pair[1]).strip()

    return album


def _get_available_plex_tracks(plex: PlexServer, tracks: List[Track]) -> List:
    """Search and return list of tracks available in plex.

    Args:
        plex (PlexServer): A configured PlexServer instance
        tracks (List[Track]): list of track objects

    Returns:
        List: of plex track objects
    """
    plex_tracks, missing_tracks = [], []
    for count, track in enumerate(tracks, start=1):  # Added count
        logging.info("Processing track %d of %d: %s (Album: %s)", count, len(tracks), track.title, track.album)  # Log the track title and count
        try:
            search = plex.search(track.title, mediatype="track", limit=5)
        except BadRequest:
            logging.info("failed to search title '%s' on plex", track.title)
        if (not search) or len(track.title.split("(")) > 1:
            cleaned_title = track.title.split("(")[0].strip()
            logging.info("retrying search with title (cleaned) '%s'", cleaned_title)
            try:
                search += plex.search(
                    cleaned_title, mediatype="track", limit=5
                )
                logging.info("search for %s successful", cleaned_title)
            except BadRequest:
                logging.info("failed to search for title (cleaned) '%s' on plex", cleaned_title)

        found = False
        if search:
            for s in search:
                try:
                    artist_similarity = SequenceMatcher(
                        None, s.artist().title.lower(), track.artist.lower()
                    ).quick_ratio()
                    logging.info("=> Artist Similarity - (Plex: %s, Track: %s) - %f", s.artist().title, track.artist, artist_similarity)

                    if artist_similarity >= 0.9:
                        logging.info("++++++ Adding Track: %s", track.title)
                        plex_tracks.extend(s)
                        found = True
                        break

                    plex_album_name = _clean_album_name(s.album().title)
                    track_album_name = _clean_album_name(track.album)
                    album_similarity = SequenceMatcher(
                        None, plex_album_name.lower(), track_album_name.lower()
                    ).quick_ratio()
                    logging.info("=> Album Similarity - (Plex: %s, Track: %s) - %f", plex_album_name, track_album_name, album_similarity)

                    if album_similarity >= 0.9:
                        logging.info("++++++++ Adding Track: %s", track.title)
                        plex_tracks.extend(s)
                        found = True
                        break

                except IndexError:
                    logging.info(
                        "Looks like plex mismatched the search for %s,"
                        " retrying with next result",
                        track.title,
                    )
        if not found:
            logging.error("Missing: %s (Album: '%s')", track.title, track.album)
            missing_tracks.append(track)

    return plex_tracks, missing_tracks


def _update_plex_playlist(
    plex: PlexServer,
    available_tracks: List,
    playlist: Playlist,
    append: bool = False,
) -> plexapi.playlist.Playlist:
    """Update existing plex playlist with new tracks and metadata.

    Args:
        plex (PlexServer): A configured PlexServer instance
        available_tracks (List): list of plex track objects
        playlist (Playlist): Playlist object
        append (bool): Boolean for Append or sync

    Returns:
        plexapi.playlist.Playlist: plex playlist object
    """
    plex_playlist = plex.playlist(playlist.name)
    if not append:
        plex_playlist.removeItems(plex_playlist.items())
    plex_playlist.addItems(available_tracks)
    return plex_playlist


def update_or_create_plex_playlist(
    plex: PlexServer,
    playlist: Playlist,
    tracks: List[Track],
    userInputs: UserInputs,
) -> None:
    """Update playlist if exists, else create a new playlist.

    Args:
        plex (PlexServer): A configured PlexServer instance
        available_tracks (List): List of plex.audio.track objects
        playlist (Playlist): Playlist object
    """
    available_tracks, missing_tracks = _get_available_plex_tracks(plex, tracks)
    logging.info("(Total: %d, Missing: %d)", len(tracks), len(missing_tracks))

    admin_user = plex.myPlexAccount().username

    # sync playlist for admin_user
    logging.info("Syncing Playlist for user %s", admin_user)
    _update_or_create_user_plex_playlist(
        plex,
        playlist,
        available_tracks,
        missing_tracks,
        userInputs,
    )

    # sync playlist for other users
    users = _get_users_list(plex, userInputs.plex_users)
    for user in users:
        if user == admin_user: # already synced before
            continue

        logging.info("Syncing Playlist for user %s", user)
        try:
            user_plex = plex.switchUser(user)
            _update_or_create_user_plex_playlist(
                user_plex,
                playlist,
                available_tracks,
                missing_tracks,
                userInputs,
            )
        except Exception as e:
            logging.info("Error while sync Playlist %s", e)

    if missing_tracks and userInputs.download_missing_tracks:
        try:
            _download_missing_tracks(missing_tracks, userInputs)
            logging.info("Missing tracks download to %s", playlist.name)
        except Exception as e:
            logging.error("Failed to download missing tracks %s", e)


    if missing_tracks and userInputs.write_missing_as_csv:
        try:
            _write_csv(missing_tracks, playlist.name)
            logging.info("Missing tracks written to %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to write missing tracks for %s, likely permission"
                " issue",
                playlist.name,
            )
    if (not missing_tracks) and userInputs.write_missing_as_csv:
        try:
            # Delete playlist created in prev run if no tracks are missing now
            _delete_csv(playlist.name)
            logging.info("Deleted old %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to delete %s.csv, likely permission issue",
                playlist.name,
            )

def _get_users_list(plex: PlexServer, users: str) -> List[str]:
    """Get list of users from Plex.

    Args:
        plex (PlexServer): A configured PlexServer instance
        users (str): comma separated list of users

    Returns:
        List[str]: list of users
    """
    account = plex.myPlexAccount()
    users_list = []
    input_users = users.split(',')
    if 'all' in input_users:
        for user in account.users():
            users_list.append(user.username)
    else:
        for user in input_users:
            users_list.append(user)

    return users_list

def _update_or_create_user_plex_playlist(
    plex: PlexServer,
    playlist: Playlist,
    available_tracks: List[Track],
    missing_tracks: List[Track],
    userInputs: UserInputs,
) -> None:
    if available_tracks:
        try:
            plex_playlist = _update_plex_playlist(
                plex=plex,
                available_tracks=available_tracks,
                playlist=playlist,
                append=userInputs.append_instead_of_sync,
            )
            logging.info("Updated playlist %s", playlist.name)
        except NotFound:
            plex.createPlaylist(title=playlist.name, items=available_tracks)
            logging.info("Created playlist %s", playlist.name)
            plex_playlist = plex.playlist(playlist.name)

        if playlist.description and userInputs.add_playlist_description:
            try:
                plex_playlist.edit(summary=playlist.description)
            except:
                logging.info(
                    "Failed to update description for playlist %s",
                    playlist.name,
                )
        if playlist.poster and userInputs.add_playlist_poster:
            try:
                plex_playlist.uploadPoster(url=playlist.poster)
            except:
                logging.info(
                    "Failed to update poster for playlist %s", playlist.name
                )
        logging.info(
            "Updated playlist %s with summary and poster", playlist.name
        )

    else:
        logging.info(
            "No songs for playlist %s were found on plex, skipping the"
            " playlist creation",
            playlist.name,
        )

