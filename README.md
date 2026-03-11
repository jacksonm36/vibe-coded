# Ansible Control Panel (vibe-coded)

A self-hosted Ansible web UI with a **Red Hat Ansible–style** interface and database-backed storage. Run playbooks, manage inventories, credentials, and job templates from a single dashboard. Supports Git/GitHub for remote playbooks and SSH (key or password) for connecting to servers.

---

## Features

- **Projects** – Organize playbooks and inventories by project
- **Git / GitHub** – Clone playbooks from any repo; paste browser URLs (e.g. `github.com/owner/repo/blob/main/...`) and use **Pull** to sync
- **Inventories** – Store INI/YAML inventories in the database
- **Credentials** – Encrypted in DB: SSH key, SSH password, Ansible Vault, Git HTTPS token
- **Job templates** – Playbook + inventory + credentials; launch and view logs
- **Job history** – Status, duration, and full output for every run
- **Red Hat–style UI** – Dark theme, sidebar, dashboard

---

## Requirements

- **Python 3.10+**
- **Ansible** – included in `requirements.txt`; installs natively on **Windows, Linux, and macOS** with `pip install -r requirements.txt` (no separate step)
- **Git** (optional; for cloning playbooks from GitHub/GitLab)

---

## Install & run by platform

### Windows

1. **Install Python 3.10+**  
   [python.org/downloads](https://www.python.org/downloads/) – tick “Add Python to PATH”.

2. **Clone or download the repo**
   ```powershell
   cd C:\Users\YourName
   git clone https://github.com/jacksonm36/vibe-coded.git
   cd vibe-coded
   ```

3. **Create a virtual environment and install dependencies** (Ansible is included)
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run the app**
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

5. Open **http://localhost:8000** in your browser.

---

### Linux (Debian / Ubuntu)

1. **Install Python, venv, and Git** (Ansible installs via pip with the app)
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv git
   ```

2. **Clone the repo**
   ```bash
   cd ~
   git clone https://github.com/jacksonm36/vibe-coded.git
   cd vibe-coded
   ```

3. **Create venv and install Python dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the app**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

5. Open **http://localhost:8000** (or **http://\<server-ip\>:8000** from another machine).

---

### Linux (RHEL / CentOS / Fedora)

1. **Install Python and Git** (Ansible installs via pip with the app)
   ```bash
   # Fedora / RHEL 8+
   sudo dnf install -y python3 python3-pip python3-virtualenv git
   ```

2. **Clone and run** (Ansible is in requirements.txt)
   ```bash
   git clone https://github.com/jacksonm36/vibe-coded.git
   cd vibe-coded
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

---

### macOS

1. **Install Python** (if needed)
   ```bash
   brew install python@3.11
   ```

2. **Clone and run** (Ansible is in requirements.txt)
   ```bash
   git clone https://github.com/jacksonm36/vibe-coded.git
   cd vibe-coded
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. Open **http://localhost:8000**.

---

## Database

- **Default:** SQLite at `./data/ansible_ui.db` (created automatically).
- **PostgreSQL:** set before run:
  ```bash
  export DATABASE_URL="postgresql://user:password@host:5432/dbname"
  pip install psycopg2-binary
  ```

---

## Run as a systemd service (Linux)

A unit file is included: **`ansible-ui.service`**.

### 1. Install the app (e.g. under `/opt/ansible-ui`)

```bash
sudo mkdir -p /opt/ansible-ui
sudo git clone https://github.com/jacksonm36/vibe-coded.git /opt/ansible-ui
cd /opt/ansible-ui
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
```

### 2. (Optional) Create a dedicated user

```bash
sudo useradd -r -s /bin/false ansible-ui
sudo chown -R ansible-ui:ansible-ui /opt/ansible-ui
```

If you skip this, edit the service file and set `User=` and `Group=` to your own user (e.g. `User=pi`), and set `WorkingDirectory=` and paths in `Environment=`/`ExecStart=` to your install path (e.g. `/home/pi/vibe-coded`).

### 3. Install and enable the service

```bash
sudo cp /opt/ansible-ui/ansible-ui.service /etc/systemd/system/
# If you used a different path or user, edit the file first:
# sudo nano /etc/systemd/system/ansible-ui.service

sudo systemctl daemon-reload
sudo systemctl enable ansible-ui
sudo systemctl start ansible-ui
sudo systemctl status ansible-ui
```

### 4. Useful commands

```bash
sudo systemctl stop ansible-ui      # stop
sudo systemctl start ansible-ui     # start
sudo systemctl restart ansible-ui   # restart
sudo journalctl -u ansible-ui -f    # follow logs
```

---

## First use

1. **Projects** → Add a project (e.g. name, optional Git URL and branch).
2. **Inventories** → Add an inventory (e.g. `[all]\nlocalhost ansible_connection=local` for localhost).
3. **Credentials** → Add SSH key, SSH password, Vault, or Git token if needed.
4. **Job templates** → Create a template: playbook path (absolute or relative to Git repo), inventory, optional credential.
5. **Launch** a job from the template and view the log.

Sample playbook: `playbooks/ping.yml`.

---

## API

- **OpenAPI (Swagger):** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  

---

## Project layout

```
vibe-coded/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   ├── runners.py
│   ├── git_support.py
│   ├── secrets.py
│   └── api/
├── static/
├── playbooks/
├── requirements.txt
└── README.md
```

---

## License

MIT
