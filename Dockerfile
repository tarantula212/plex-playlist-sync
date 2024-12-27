FROM spotdl/spotify-downloader:latest

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "./plex-playlist-sync/run.py"]

# docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t rnagabhyrava/plexplaylistsync:<tag> --push .