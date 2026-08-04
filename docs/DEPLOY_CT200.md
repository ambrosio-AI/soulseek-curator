# Deploy on the Torrent CT

The intended local target is the torrent container/server or a nearby LAN host that can
reach slskd. In the current Ambrosio environment Curator runs on Proxmox CT `200`,
hostname `Torrent`, IP `192.168.1.23`. The real slskd instance is on
`192.168.1.4:5030`.

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

If Curator and slskd run in the same Docker stack, review `docker-compose.yml` and keep:

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
slskd URL in settings.

If existing slskd already downloads to a NAS path, do not mount the NAS into Curator just
for queueing. Curator sends slskd-relative destination folders such as
`BBQ/verano-2026/rock`; slskd resolves them inside its own configured download directory.

Set `slskd download root` only as a reference for converting absolute paths that may
appear in imported CSV/JSON files. Normal imports should use relative destination folders.

## Current CT200 Note

On the current CT200 LXC, Docker containers run, but Docker image builds may fail with an
AppArmor profile error. In that case use [SYSTEMD_DEPLOY.md](SYSTEMD_DEPLOY.md).
