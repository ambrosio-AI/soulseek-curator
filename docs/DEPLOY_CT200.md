# Deploy on the Torrent CT

The intended local target is the torrent container/server where the media paths are
available. In the current Ambrosio environment that is Proxmox CT `200`, hostname
`Torrent`, IP `192.168.1.23`, with music visible at `/mnt/music`.

## Prepare

```bash
git clone https://github.com/ambrosio-AI/soulseek-curator.git /srv/projects/soulseek-curator
cd /srv/projects/soulseek-curator
cp .env.example .env
cp config.example.yaml config/curator.yaml
```

Edit `.env` and set:

```bash
SLSKD_API_KEY=...
```

Review `docker-compose.yml` and keep:

```yaml
- /mnt/music:/downloads
```

## Start

```bash
docker compose up -d --build
```

Open:

```text
http://192.168.1.23:8088
```

slskd:

```text
http://192.168.1.23:5030
```

## If slskd Already Exists

Remove the `slskd` service from `docker-compose.yml`, connect Curator to the existing
slskd URL in settings, and make sure both services agree on the same download root.

