import random
import os
import discord
import asyncio
import yt_dlp
import spotipy
from asyncio import Lock
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from discord.utils import get
from spotipy.oauth2 import SpotifyClientCredentials

def run_bot():
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

    spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))
    
    intents = discord.Intents.default()
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    tree = bot.tree

    global queues, loopSong, loopQueue
    queues = {}
    loopSong = False
    loopQueue = False
    voice_clients = {}
    yt_dl_options = {
        "format": "bestaudio[ext=webm]/bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "webm",
            "preferredquality": "320",
        }],
        "noplaylist": True  # Ensure we only get a single song if given a playlist
    }

    ytdl = yt_dlp.YoutubeDL(yt_dl_options)
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.5" -b:a 320k'
    }

    @bot.event
    async def on_ready():
        print(f"{bot.user} is now jamming")
        await tree.sync()

    @bot.event
    async def on_voice_state_update(member, before, after):
        if before.channel and len(before.channel.members) == 1:
            voice_data = voice_clients.get(before.channel.guild.id)
            if voice_data:
                voice_client = voice_data['voice_client']
                if voice_client and voice_client.is_connected():
                    await voice_client.disconnect()
                    del voice_clients[before.channel.guild.id]
                    channel = voice_data.get("text_channel")
                    if channel:
                        await channel.send("Left the voice channel as it was empty.")

    @tree.command(name="play", description="Enter the name, YouTube link, or Spotify link of the song/playlist you wish to play.")
    @app_commands.describe(song_info="Enter the name, YouTube link, or Spotify link of the song/playlist you wish to play.")
    async def play(interaction: discord.Interaction, song_info: str):
        global queues
        if interaction.user.voice:
            guild_id = interaction.guild.id
            if guild_id not in queues:
                queues[guild_id] = []

            await interaction.response.defer()
            await interaction.followup.send("Processing your request, please wait...")

            loop = asyncio.get_event_loop()

            try:
                if "spotify.com" in song_info:
                    if "track" in song_info:
                        track_id = song_info.split("/")[-1].split("?")[0]
                        track = spotify.track(track_id)
                        song_info = f"{track['name']} {track['artists'][0]['name']}"
                    elif "playlist" in song_info:
                        playlist_id = song_info.split("/")[-1].split("?")[0]
                        playlist = spotify.playlist(playlist_id)
                        
                        # Improved: Batch processing of Spotify playlist
                        track_names = [f"{item['track']['name']} {item['track']['artists'][0]['name']}" for item in playlist['tracks']['items']]
                        
                        # Batch YT search requests concurrently
                        data_list = await asyncio.gather(*[loop.run_in_executor(None, lambda query=f"ytsearch:{track}": ytdl.extract_info(query, download=False)) for track in track_names])
                        
                        # Add all tracks found to the queue
                        for data in data_list:
                            if 'entries' in data:
                                data = data['entries'][0]
                            title = data['title']
                            uploader = data.get('uploader', 'Unknown')
                            url = data['url']
                            queues[guild_id].append({'title': title, 'uploader': uploader, 'url': url})

                        await interaction.followup.send(f"Added {len(playlist['tracks']['items'])} songs to the queue from your Spotify playlist!")

                        # Check if we need to start playing
                        if len(queues[guild_id]) == len(playlist['tracks']['items']):
                            await playSong(interaction)
                        return

                if "http" in song_info or "youtube.com" in song_info or "youtu.be" in song_info:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_info, download=False))
                else:
                    search_query = f"ytsearch:{song_info}"
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))

                if 'entries' in data:
                    data = data['entries'][0]  # Take the first search result

                title = data['title']
                uploader = data.get('uploader', 'Unknown')
                url = data['url']
                queues[guild_id].append({'title': title, 'uploader': uploader, 'url': url})

                if len(queues[guild_id]) == 1:
                    await playSong(interaction)

                await interaction.followup.send(f"Added {title} by {uploader} to the queue!")
            except Exception as e:
                print(f"Error processing the song: {e}")
                await interaction.followup.send(f"An error occurred while processing your request: {e}")

        else:
            await interaction.response.send_message("You must be in a voice channel to play a song!", ephemeral=True)

    
    queue_locks = {}

    async def playSong(interaction):
        guild_id = interaction.guild.id
        if guild_id not in queue_locks:
            queue_locks[guild_id] = Lock()

        async with queue_locks[guild_id]:
            voice_client = voice_clients.get(guild_id, {}).get("voice_client")
            
            if not interaction.user.voice:
                await interaction.followup.send("You must be in a voice channel to play a song!", ephemeral=True)
                return
            
            if not voice_client or not voice_client.is_connected():
                voice_client = await interaction.user.voice.channel.connect()
                voice_clients[guild_id] = {
                    "voice_client": voice_client,
                    "text_channel": interaction.channel
                }
            
            if queues[guild_id]:
                song_info = queues[guild_id][0]
                try:
                    await interaction.followup.send(
                        f"Now playing {song_info['title']} by {song_info['uploader']}, in {interaction.user.voice.channel}, requested by {interaction.user.mention}"
                    )
                except discord.errors.HTTPException as e:
                    print(f"HTTPException when sending follow-up: {e}")
                    await interaction.channel.send(
                        f"Now playing {song_info['title']} by {song_info['uploader']}, in {interaction.user.voice.channel}, requested by {interaction.user.mention}"
                    )

                try:
                    print(f"Playing URL: {song_info['url']}")
                    player = discord.FFmpegOpusAudio(song_info['url'], **ffmpeg_options)
                    
                    def after_playing(error):
                        if error:
                            print(f"Error during playback: {error}")
                        asyncio.run_coroutine_threadsafe(onSongEnd(guild_id, interaction), bot.loop).result()

                    voice_client.play(player, after=after_playing)
                except Exception as e:
                    await interaction.followup.send(f"Error playing song: {e}")
                    await onSongEnd(guild_id, interaction)
            else:
                await interaction.followup.send("Queue is empty!")


    async def onSongEnd(guild_id, interaction):
        global queues, loopSong, loopQueue
        await asyncio.sleep(2)

        if guild_id in queues:
            if loopSong:
                await playSong(interaction)
            else:
                if loopQueue:
                    if queues[guild_id]:
                        queues[guild_id].append(queues[guild_id].pop(0))
                else:
                    if queues[guild_id]:
                        queues[guild_id].pop(0)

                if queues[guild_id]:
                    await playSong(interaction)
                else:
                    await interaction.channel.send("Queue is empty. Leaving voice channel.")
                    if guild_id in voice_clients:
                        voice_client = voice_clients[guild_id]['voice_client']
                        if voice_client and voice_client.is_connected():
                            await voice_client.disconnect()
                        del voice_clients[guild_id]
        else:
            await interaction.channel.send("Queue is empty. Leaving voice channel.")
            if guild_id in voice_clients:
                voice_client = voice_clients[guild_id]['voice_client']
                if voice_client and voice_client.is_connected():
                    await voice_client.disconnect()
                del voice_clients[guild_id]

    @tree.command(name="pause", description="Pause the currently playing song.")
    async def pause(interaction: discord.Interaction):
        guild_id = interaction.guild.id

        try:
            voice_client = voice_clients.get(guild_id, {}).get("voice_client")
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                await interaction.response.send_message("Paused the current song!")
            else:
                await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        except KeyError:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        except Exception as e:
            print(f"Error pausing: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while trying to pause the song.", ephemeral=True)

    @tree.command(name="resume", description="Resume the music.")
    async def resume(interaction: discord.Interaction):
        try:
            voice_clients[interaction.guild.id]['voice_client'].resume()
            await interaction.response.send_message("Resuming the current song!")
        except KeyError:
            await interaction.response.send_message("No song is currently paused!", ephemeral=True)
        except Exception as e:
            print(f"Error resuming: {e}")

    @tree.command(name="stop", description="Stop the music.")
    async def stop(interaction: discord.Interaction):
        try:
            global queues
            voice_clients[interaction.guild.id]['voice_client'].stop()
            queues.clear()
            await voice_clients[interaction.guild.id]['voice_client'].disconnect()
            await interaction.response.send_message("Stopping the current song and leaving the voice call!")
        except KeyError:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        except Exception as e:
            print(f"Error stopping: {e}")

    @tree.command(name="skip", description="Skip the current song.")
    async def skip(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        
        try:
            voice_client = voice_clients.get(guild_id, {}).get("voice_client")
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                await interaction.response.send_message("Skipping the current song...")
            else:
                await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        except KeyError:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        except Exception as e:
            print(f"Error skipping: {e}")

    @tree.command(name="shuffle", description="Shuffle the current song queue.")
    async def shuffle(interaction: discord.Interaction):
        global queues
        guild_id = interaction.guild.id
        
        if guild_id in queues and len(queues[guild_id]) > 1:
            current_song = queues[guild_id][0]
            remaining_songs = queues[guild_id][1:]
            random.shuffle(remaining_songs)
            queues[guild_id] = [current_song] + remaining_songs

            await interaction.response.send_message("Shuffled the queue!")
        else:
            await interaction.response.send_message("Not enough songs in the queue to shuffle.", ephemeral=True)

    @tree.command(name="loopsong", description="Enable loop on the current song")
    async def toggle_loop_song(interaction: discord.Interaction):
        global loopSong
        global loopQueue
        loopSong = not loopSong
        if loopSong:
            loopQueue = False
        status = "enabled" if loopSong else "disabled"
        await interaction.response.send_message(f"Loop song is now {status}.")

    @tree.command(name="loopqueue", description="Enable loop on the queue")
    async def toggle_loop_queue(interaction: discord.Interaction):
        global loopQueue
        global loopSong
        loopQueue = not loopQueue
        if loopQueue:
            loopSong = False
        status = "enabled" if loopQueue else "disabled"
        await interaction.response.send_message(f"Loop queue is now {status}.")

    @tree.command(name="queue", description="Display the current queue.")
    async def show_queue(interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in queues and len(queues[guild_id]) > 1:
            # Start numbering from the second song as the first in the queue
            queue_str = "\n".join([f"{i+1}. {song['title']} by {song['uploader']}" for i, song in enumerate(queues[guild_id][1:])])

            await interaction.response.defer()

            max_message_length = 2000
            for i in range(0, len(queue_str), max_message_length):
                chunk = queue_str[i:i+max_message_length]
                await interaction.followup.send(chunk)
        else:
            await interaction.response.send_message("The queue is empty!", ephemeral=True)

    @tree.command(name="nowplaying", description="Show the currently playing song.")
    async def nowplaying(interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in queues and queues[guild_id]:
            current_song = queues[guild_id][0]  # The currently playing song is always the first in the queue.
            await interaction.response.send_message(f"Currently playing: {current_song['title']} by {current_song['uploader']}")
        else:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)

    @tree.command(name="clearqueue", description="Clear the current song queue (Currently playing song will be unaffected)")
    async def clear_queue(interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in queues and len(queues[guild_id]) > 1:
            # Keep the currently playing song and clear the rest
            queues[guild_id] = queues[guild_id][:1]
            await interaction.response.send_message("Cleared the queue, but the currently playing song will continue.")
        else:
            await interaction.response.send_message("The queue is empty or only has the currently playing song.", ephemeral=True)

    @tree.command(name="removesong", description="Remove the song at a certain index.")
    @app_commands.describe(remove_index="Enter the index of the song in the queue you wish to remove.")
    async def removesong(interaction: discord.Interaction, remove_index: int):
        guild_id = interaction.guild.id
        global queues

        if guild_id not in queues or len(queues[guild_id]) <= 1:
            await interaction.response.send_message("No songs in the queue or only the currently playing song!", ephemeral=True)
            return

        try:
            # Since the queue numbering in your queue command starts from 1 for the second song
            index = remove_index  # No need to subtract 1 since we are skipping the currently playing song
            
            if index < 1 or index >= len(queues[guild_id]):
                await interaction.response.send_message(f"There is no song at index: {remove_index}!")
                return

            removed_song = queues[guild_id].pop(index)
            await interaction.response.send_message(f"Removed the song: {removed_song['title']} by {removed_song['uploader']} at index: {remove_index}.")
                    
        except Exception as e:
            print(f"Error removing song: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while trying to remove the song.", ephemeral=True)

    @tree.command(name="skipto", description="Skip to a certain song in the queue.")
    @app_commands.describe(song_index="Enter the index of the song in the queue you wish to skip to.")
    async def skipto(interaction: discord.Interaction, song_index: int):
        global loopQueue
        global loopSong
        global queues
        guild_id = interaction.guild.id

        try:
            voice_client = voice_clients.get(guild_id, {}).get("voice_client")
            if voice_client and voice_client.is_playing():
                # Check if the song index is within the valid range
                if song_index < 1 or song_index >= len(queues[guild_id]):
                    await interaction.response.send_message(f"There is no song at index: {song_index}!")
                    return
                
                # Handle looping scenarios
                if loopQueue:
                    # Slice and rearrange the queue
                    queues[guild_id] = queues[guild_id][song_index - 1:] + queues[guild_id][:song_index - 1]
                    voice_client.stop()

                elif loopSong:
                    loopSong = False  # Temporarily disable song looping
                    # Remove all songs before the target index
                    queues[guild_id] = queues[guild_id][song_index:]
                    voice_client.stop()
                    await asyncio.sleep(1)  # Adjust sleep as needed to avoid timing issues
                    loopSong = True  # Re-enable song looping

                else:
                    # For normal operation, remove songs before the target index
                    queues[guild_id] = queues[guild_id][song_index - 1:]
                    voice_client.stop()

                await interaction.response.send_message(f"Skipping to song at index: {song_index}..")
            
            else:
                await interaction.response.send_message("No song is currently playing!", ephemeral=True)

        except KeyError:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)
        
        except Exception as e:
            # Catch any other exceptions and notify the user
            await interaction.response.send_message(f"An error occurred while trying to skip: {e}")
            print(f"Error skipping: {e}")

    @tree.command(name="removeduplicates", description="Remove duplicate songs from the queue.")
    async def remove_duplicates(interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in queues and len(queues[guild_id]) > 1:
            seen = set()
            unique_queue = []
            current_song = queues[guild_id][0]
            
            for song in queues[guild_id][1:]:
                song_key = (song['title'], song['uploader'])
                if song_key not in seen:
                    seen.add(song_key)
                    unique_queue.append(song)

            queues[guild_id] = [current_song] + unique_queue
            await interaction.response.send_message("Removed duplicates from the queue!")
        else:
            await interaction.response.send_message("Not enough songs in the queue to remove duplicates.", ephemeral=True)

    bot.run(TOKEN)
