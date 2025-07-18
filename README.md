# Syre - CTF Discord Bot

Syre is a customizable Discord bot designed to host **Capture The Flag (CTF)** competitions. It features challenge registration, dynamic Docker-based deployment, and user score tracking — all integrated into an easy-to-use Discord interface.

---

## 🚀 Features

- **Category-based challenges** – Crypto, Forensics, Web, Pwn, and more.
- **User registration and scoreboard** – Compete with others and track your progress.
- **Dynamic container management** – Challenges (e.g. Web/Pwn) spin up Docker containers per user.
- **Admin utilities** – Create, start, stop, and test challenges directly from Discord.

---

## ⚙️ Tech Stack

- **Language**: Python (Nextcord)
- **Containerization**: Docker
- **Database**: MongoDB
- **Others**: PyMongo, Discord bot API

## 📂 Project Structure

```
syre/
├── challenges/          # Challenge config files
├── misc.py              # Utility functions (e.g., Docker control)
├── database.py          # MongoDB wrapper class
├── app.py               # Bot entry point
└── config.py            # Secrets and config (excluded from Git)
```

## 🛠️ Setup Instructions

> Make sure you have **Python 3.10+**, **Docker**, and **MongoDB** installed and running.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/s0ur4v116/syre
   cd syre
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   - Create a `config.py` file and add your:
     - Discord bot token
     - MongoDB URI
     - Admin role names

4. **Run the bot**:
   ```bash
   python app.py
   ```

## 🧠 Challenges are stored as:

```json
{
  "name": "easycrypto",
  "category": "cryptography",
  "flag": "CTF{example}",
  "points": 100,
  "description": "Decrypt this to get the flag.",
  "docker": true
}
```

## 📌 Future Improvements

- Add JWT-based web dashboard for managing challenges
- Container auto-cleanup for resource management
- Support for timed competitions and team scores

---

## 🤝 Contributions

PRs are welcome! If you'd like to contribute, just fork the repo and create a feature branch.

---
