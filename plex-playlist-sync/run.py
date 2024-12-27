import logging
import os
import time

import deezer
import spotipy
from spotipy_anon import SpotifyAnon
from plexapi.server import PlexServer
from spotipy.oauth2 import SpotifyClientCredentials

from utils.deezer import deezer_playlist_sync
from utils.helperClasses import UserInputs
from utils.spotify import spotify_playlist_sync
import yaml

def get_config():
    # Load configuration from config.yaml
    config_path = "/config/config.yaml"
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    # Read configuration variables
    userInputs = UserInputs(
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
        spotipy_client_id=config.get("SPOTIFY_CLIENT_ID"),
        spotipy_client_secret=config.get("SPOTIFY_CLIENT_SECRET"),
        spotify_user_id=config.get("SPOTIFY_USER_ID"),
        spotify_playlist_ids=config.get("SPOTIFY_PLAYLIST_IDS", []),

        # deezer config
        deezer_user_id=config.get("DEEZER_USER_ID"),
        deezer_playlist_ids=config.get("DEEZER_PLAYLIST_ID"),
    )

    return userInputs

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

    logging.info("Starting Spotify playlist sync")

    SP_AUTHSUCCESS = False

    if (
        userInputs.spotipy_client_id
        and userInputs.spotipy_client_secret
        and userInputs.spotify_user_id
    ):
        try:
            sp = spotipy.Spotify(
                auth_manager=SpotifyAnon()
            )
            SP_AUTHSUCCESS = True
        except:
            logging.info("Spotify Authorization error, skipping spotify sync")

    else:
        logging.info(
            "Missing one or more Spotify Authorization Variables, skipping"
            " spotify sync"
        )

    if SP_AUTHSUCCESS:
        spotify_playlist_sync(sp, plex, userInputs)

    logging.info("Spotify playlist sync complete")

    ########## DEEZER SYNC ##########

    # logging.info("Starting Deezer playlist sync")
    # dz = deezer.Client()
    # deezer_playlist_sync(dz, plex, userInputs)
    # logging.info("Deezer playlist sync complete")

    # logging.info("All playlist(s) sync complete")
    # logging.info("sleeping for %s seconds" % userInputs.wait_seconds)

    time.sleep(userInputs.wait_seconds)