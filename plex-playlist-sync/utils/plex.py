import csv
import re
import pathlib
from difflib import SequenceMatcher
from typing import List

import plexapi
from plexapi.exceptions import BadRequest, NotFound
from plexapi.server import PlexServer
from plexapi.audio import Track as PlexTrack

import os

from .logger import setup_logger
from .helperClasses import Playlist, Track, UserInputs
from .playlistData import PlaylistDataHelper, TrackData

logging = setup_logger(name="Plex")


def _write_csv(tracks: List[Track], name: str, path: str) -> None:
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
        writer.writerow(["Title", "Artist", "Album", "URL"])
        for track in tracks:
            writer.writerow([track.title, track.artist, track.album, track.url])


def _delete_csv(name: str, path: str) -> None:
    """Delete file associated with given name

    Args:
        name (str): Name of the file to delete
        path (str, optional): Root directory to delete the file from
    """
    data_folder = pathlib.Path(path)
    file = data_folder / f"{name}.csv"
    file.unlink()


def _clean(str):
    # Replace all special characters with a space
    clean_str = re.sub(r"[^a-zA-Z0-9]", " ", str)
    # Replace multiple spaces with a single space
    clean_str = re.sub(r"\s+", " ", clean_str).strip()
    return clean_str


def _clean_album_name(album: str) -> str:
    """Clean the album name by removing specified phrases in any case and bracketed."""
    # Remove phrases
    phrases_to_remove = [
        "original motion picture soundtrack",
        "soundtrack from the netflix series",
        "deluxe edition",
        "dialogues version",
        "- EP",
    ]
    for phrase in phrases_to_remove:
        album = re.sub(
            r"\(?\s*" + re.escape(phrase) + r"\s*\)?", "", album, flags=re.IGNORECASE
        ).strip()

    # Replace words
    words_to_replace = [
        ["&", "And"],
        ["-", ""],
        ["(", ""],
        [")", ""],
    ]
    for word_pair in words_to_replace:  # Changed variable name for clarity
        album = album.replace(word_pair[0], word_pair[1]).strip()

    return _clean(album)


def _unique_strings(arr):
    return list(set(arr))


def _plex_track_search(plex_music_library, track_data: TrackData):
    search_strs = [f"{track_data.title} - {track_data.album}"] + _unique_strings(track_data.plex_search)
    search = []
    for item in search_strs:
        title = item.strip()
        try:
            logging.debug(f"Plex Search - (title={title})")
            search += plex_music_library.search(title=title, libtype="track", limit=30)
        except BadRequest:
            logging.info("failed to search title '%s' on plex", title)

    logging.debug(f"Search Result Count - {str(len(search))}")
    for s in search:
        logging.debug(
            f"* (title={s.title}) (album={s.album().title}) (artist={s.artist().title})"
        )

    return search


def _find_spotdl_track(plex_track: PlexTrack) -> bool:
    for media in plex_track.media:
        for part in media.parts:
            if "spotdl" in part.file.lower():
                return True
    return False


def _get_available_plex_tracks(
    plex: PlexServer, playlist: Playlist, config_dir: str
) -> List:
    """Search and return list of tracks available in plex.

    Args:
        plex (PlexServer): A configured PlexServer instance
        tracks (List[Track]): list of track objects

    Returns:
        List: of plex track objects
    """
    playlist_data_helper = PlaylistDataHelper(os.path.join(config_dir, "data"))
    playlist_data_helper.load(playlist)

    plex_music_library = plex.library.section("Music")
    plex_tracks, missing_tracks = [], []

    tracks_data = []
    for count, track in enumerate(playlist.tracks, start=1):  # Added count
        logging.info(
            "Processing track %d of %d: %s (Album: %s)",
            count,
            len(playlist.tracks),
            track.title,
            track.album,
        )  # Log the track title and count

        track_data = playlist_data_helper.get_track_data(track) or TrackData(
            number=count,
            title=track.title,
            original_title=track.original_title,
            artist=track.artist,
            album=track.album,
            original_album=track.original_album,
            url=track.url,
            plex_search=_unique_strings([track.title, track.original_title]),
            status="missing",
            spotdl=False,
        )

        track_album_name = _clean_album_name(track_data.album)
        track_original_album_name = _clean_album_name(track_data.original_album)

        search = _plex_track_search(plex_music_library, track_data)
        found = False
        plex_track = None
        if search:
            for s in search:
                try:
                    plex_album_name = _clean_album_name(s.album().title)

                    # Match with album name
                    album_similarity = SequenceMatcher(
                        None, plex_album_name.lower(), track_album_name.lower()
                    ).quick_ratio()
                    logging.debug(
                        "Album Similarity - (Plex: %s, Track: %s) - %f",
                        plex_album_name,
                        track_album_name,
                        album_similarity,
                    )

                    if album_similarity >= 0.9:
                        logging.success("Adding Track: %s", track.title)
                        plex_tracks.extend(s)
                        found = True
                        plex_track = s
                        break

                    # Match with original album name
                    album_similarity = SequenceMatcher(
                        None, plex_album_name.lower(), track_original_album_name.lower()
                    ).quick_ratio()
                    logging.debug(
                        "Album Similarity - (Plex: %s, Track: %s) - %f",
                        plex_album_name,
                        track_original_album_name,
                        album_similarity,
                    )

                    if album_similarity >= 0.9:
                        logging.success("Adding Track: %s", track.title)
                        plex_tracks.extend(s)
                        plex_track = s
                        found = True
                        break

                    # artist_similarity = SequenceMatcher(
                    #     None, s.artist().title.lower(), track.artist.lower()
                    # ).quick_ratio()
                    # logging.debug("=> Artist Similarity - (Plex: %s, Track: %s) - %f", s.artist().title, track.artist, artist_similarity)

                    # if artist_similarity >= 0.9:
                    #     logging.success("Adding Track: %s", track.title)
                    #     plex_tracks.extend(s)
                    #     found = True
                    #     break

                except IndexError:
                    logging.info(
                        "Looks like plex mismatched the search for %s,"
                        " retrying with next result",
                        track.title,
                    )
        if not found:
            logging.error("Missing: %s (Album: '%s')", track.title, track.album)
            missing_tracks.append(track)

        track_data.spotdl = _find_spotdl_track(plex_track) if plex_track else False
        track_data.status = "found" if found else "missing"
        tracks_data.append(track_data)

    playlist_data_helper.update_tracks(tracks_data)
    playlist_data_helper.save()

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
    userInputs: UserInputs,
) -> List[Track]:
    """Update playlist if exists, else create a new playlist.

    Args:
        plex (PlexServer): A configured PlexServer instance
        available_tracks (List): List of plex.audio.track objects
        playlist (Playlist): Playlist object
    """
    tracks = playlist.tracks

    available_tracks, missing_tracks = _get_available_plex_tracks(
        plex, playlist, userInputs.config_dir
    )
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
        if user == admin_user:  # already synced before
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

    csv_dir = os.path.join(userInputs.config_dir, "data")
    if missing_tracks and userInputs.write_missing_as_csv:
        try:
            _write_csv(missing_tracks, playlist.name, csv_dir)
            logging.info("Missing tracks written to %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to write missing tracks for %s, likely permission issue",
                playlist.name,
            )
    if (not missing_tracks) and userInputs.write_missing_as_csv:
        try:
            # Delete playlist created in prev run if no tracks are missing now
            _delete_csv(playlist.name, csv_dir)
            logging.info("Deleted old %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to delete %s.csv, likely permission issue",
                playlist.name,
            )

    return missing_tracks


def _get_users_list(plex: PlexServer, users: List[str]) -> List[str]:
    """Get list of users from Plex.

    Args:
        plex (PlexServer): A configured PlexServer instance
        users (str): comma separated list of users

    Returns:
        List[str]: list of users
    """
    account = plex.myPlexAccount()
    users_list = []
    input_users = users
    if "all" in input_users:
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
                logging.info("Failed to update poster for playlist %s", playlist.name)
        logging.info("Updated playlist %s with summary and poster", playlist.name)

    else:
        logging.info(
            "No songs for playlist %s were found on plex, skipping the"
            " playlist creation",
            playlist.name,
        )
