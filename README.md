# Discord Music Bot

A Discord bot designed for managing music playback in voice channels with advanced features like playlists, queue management, looping, shuffling, and audio filters.

## Features

- 🎵 **Music Playback**: Play songs from YouTube, Spotify, or other supported platforms.
- ⏯️ **Play, Pause, Stop**: Control music playback with simple commands.
- ⏩ **Skip and Skip To**: Skip the current song or jump to a specific position in the queue.
- 🔁 **Loop**: Toggle between no loop, looping the current song, or looping the entire queue.
- 🔀 **Shuffle**: Randomize the order of songs in the queue.
- 📜 **Queue Management**: View, add, remove, and reorder songs in the queue.
- 🎚️ **Filters**: Apply audio filters to songs that are currently playing or queued.
- 🔧 **Custom Slash Commands**: Easy-to-use slash commands with interactive options for seamless control.

## Getting Started

### Prerequisites

- **Python 3.8+**
- [Discord Application and Bot Token](https://discord.com/developers/applications)
- YouTube Data API (optional for advanced YouTube functionality)
- [Spotify API Credentials](https://developer.spotify.com/) (optional for Spotify support)

### Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/yourbotrepo.git
    cd yourbotrepo
    ```

2. **Create a virtual environment (optional but recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install dependencies:**

    Install the required Python packages using `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```

4. **Set up environment variables:**

    Create a `.env` file in the root directory of the project and add your credentials:

    ```env
    DISCORD_TOKEN=your-discord-bot-token
    SPOTIPY_CLIENT_ID=your-spotify-client-id
    SPOTIPY_CLIENT_SECRET=your-spotify-client-secret
    SPOTIPY_REDIRECT_URI=http://localhost/
    ```

### Usage

1. **Run the bot:**

    ```bash
    python main.py
    ```

2. **Invite the bot to your server:**

    Use the following link template to invite your bot:

    ```
    https://discord.com/oauth2/authorize?client_id=your_client_id&scope=bot+applications.commands&permissions=8
    ```
