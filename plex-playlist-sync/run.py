import os
import time

import yaml

# import spotipy
# from spotipy_anon import SpotifyAnon

from ytmusicapi import YTMusic

from plexapi.server import PlexServer

from utils.helperClasses import UserInputs
from utils.logger import setup_logger

# from utils.spotify import spotify_playlist_sync
from utils.ytmusic import ytmusic_playlist_sync

logging = setup_logger(name="Run")


def get_config():
    config_dir = os.getenv("CONFIG_DIR", "/config")

    # Load configuration from config.yaml
    config_path = os.path.join(config_dir, "config.yaml")
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)

    # Read configuration variables
    userInputs = UserInputs(
        # general config
        config_dir=config_dir,
        # plex config
        plex_url=config.get("PLEX_URL"),
        plex_token=config.get("PLEX_TOKEN"),
        plex_users=config.get("PLEX_USERS", []),  # comma separated list of users
        # download config
        spotdl_dir=config.get("SPOTDL_DIR"),
        download_missing_tracks=config.get("DOWNLOAD_MISSING_TRACKS", True),
        download_missing_tracks_dir=config.get("DOWNLOAD_MISSING_TRACKS_DIR", "/music"),
        # sync config
        write_missing_as_csv=config.get("WRITE_MISSING_AS_CSV", False),
        append_service_suffix=config.get("APPEND_SERVICE_SUFFIX", True),
        add_playlist_poster=config.get("ADD_PLAYLIST_POSTER", True),
        add_playlist_description=config.get("ADD_PLAYLIST_DESCRIPTION", True),
        append_instead_of_sync=config.get("APPEND_INSTEAD_OF_SYNC", False),
        wait_seconds=config.get("SECONDS_TO_WAIT", 86400),

        # spotify config
        # spotify_sync_enabled=config.get("SPOTIFY_SYNC_ENABLED", True),
        # spotipy_client_id=config.get("SPOTIFY_CLIENT_ID"),
        # spotipy_client_secret=config.get("SPOTIFY_CLIENT_SECRET"),
        # spotify_user_id=config.get("SPOTIFY_USER_ID"),
        # spotify_playlist_ids=config.get("SPOTIFY_PLAYLIST_IDS", []),

        # ytmusic config
        ytmusic_sync_enabled=config.get("YTMUSIC_SYNC_ENABLED", True),
        ytmusic_playlist_ids=config.get("YTMUSIC_PLAYLIST_IDS", []),
    )

    return userInputs


# def spotify_sync():
#     logging.info("Starting Spotify playlist sync")

#     SP_AUTHSUCCESS = False

#     if (
#         userInputs.spotipy_client_id
#         and userInputs.spotipy_client_secret
#         and userInputs.spotify_user_id
#     ):
#         try:
#             sp = spotipy.Spotify(auth_manager=SpotifyAnon())
#             SP_AUTHSUCCESS = True
#         except:
#             logging.info("Spotify Authorization error, skipping spotify sync")

#     else:
#         logging.info(
#             "Missing one or more Spotify Authorization Variables, skipping spotify sync"
#         )

#     if SP_AUTHSUCCESS:
#         spotify_playlist_sync(sp, plex, userInputs)

#     logging.info("Spotify playlist sync complete")


def ytmusic_sync():
    logging.info("Starting YTMusic playlist sync")

    config_dir = os.getenv("CONFIG_DIR", "/config")

    # Load configuration from config.yaml
    browser_auth_file_path = os.path.join(config_dir, "ytmusic_browser.json")

    yt = YTMusic(browser_auth_file_path)

    ytmusic_playlist_sync(yt, plex, userInputs)

    logging.info("YTMusic playlist sync complete")


while True:
    logging.info("Starting playlist sync")
    userInputs = get_config()

    if userInputs.plex_url and userInputs.plex_token:
        try:
            plex = PlexServer(userInputs.plex_url, userInputs.plex_token)
        except:
            logging.error("Plex Authorization error")
            break
    else:
        logging.error("Missing Plex Authorization Variables")
        break

    ########## SPOTIFY SYNC ##########
    # if userInputs.spotify_sync_enabled:
    #     spotify_sync()

    ########## YT-MUSIC SYNC ##########
    if userInputs.ytmusic_sync_enabled:
        ytmusic_sync()

    time.sleep(userInputs.wait_seconds)
