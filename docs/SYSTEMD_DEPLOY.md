# Systemd Deployment

Use this path when Docker builds are blocked by the host or LXC runtime, for example
AppArmor failures while building inside an unprivileged container.

## Install

```bash
git clone https://github.com/ambrosio-AI/soulseek-curator.git /opt/soulseek-curator
cd /opt/soulseek-curator
cp .env.example .env
cp config.example.yaml config/curator.yaml
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

If venv creation fails on Ubuntu/Debian:

```bash
apt-get update
apt-get install -y python3.10-venv
```

## Service

Create `/etc/systemd/system/soulseek-curator.service`:

```ini
[Unit]
Description=Soulseek Curator local web app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/soulseek-curator
EnvironmentFile=-/opt/soulseek-curator/.env
Environment=CURATOR_HOST=0.0.0.0
Environment=CURATOR_PORT=8088
Environment=CURATOR_CONFIG=/opt/soulseek-curator/config/curator.yaml
Environment=CURATOR_DATA_DIR=/opt/soulseek-curator/data
ExecStart=/opt/soulseek-curator/.venv/bin/soulseek-curator
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start:

```bash
systemctl daemon-reload
systemctl enable --now soulseek-curator.service
systemctl status soulseek-curator.service
```

Open:

```text
http://<server-ip>:8088
```

## Update

```bash
cd /opt/soulseek-curator
git pull --ff-only
. .venv/bin/activate
pip install -e .
systemctl restart soulseek-curator.service
```

