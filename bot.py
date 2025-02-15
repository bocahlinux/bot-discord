import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import config

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options={
    'format' : 'bestaudio/best',
    'outtmpl' : '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames' : True,
    'noplaylist' : True,
    'nocheckertificate' : True,
    'ignoreerrors': False,
    'logtostderr' : False,
    'quite' : True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_adress': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -timeout 500 -bufsize 64k',
    'executable': './ffmpeg_linux/bin/ffmpeg'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

queues = {}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume =0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
    
def play_next(ctx, guild_id):
    if guild_id in queues:
        if queues[guild_id]:
            player = queues[guild_id].pop(0)
            ctx.voice_client.play(player, after= lambda e: play_next(ctx, guild_id))
    
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='join', help='Bot joins the voice channel (!join)')
async def join(ctx):
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
        if not ctx.author.voice:
            await ctx.send(f'{ctx.message.author.name} is not connected to a voice channel')
            return
        else:
            channel = ctx.message.author.voice.channel
        vc = await channel.connect()
        await ctx.send(f'Muzik has joined {channel} successfully!!')

        while True:
            silent_frame = bytes(3840)
            vc.send_audio_packet(silent_frame, encode=False)
            await asyncio.sleep(120)

    except Exception as e:
        print(f'An error occurred in the join command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='play', help='Bot plays a requested song (!play)')
async def play(ctx, *, search:str):
    async with ctx.typing():
        try:
            vc = ctx.voice_client

            if not vc:
                await ctx.invoke(join)

            player = await YTDLSource.from_url(f"ytsearch:{search}", loop = bot.loop, stream=True)
            await ctx.send(f'Added to queue: {player.title}')
            if ctx.guild.id in queues:
                queues[ctx.guild.id].append(player)
            else:
                queues[ctx.guild.id] = [player]
            if not vc.is_playing():
                ctx.voice_client.play(queues[ctx.guild.id].pop(0), after= lambda e: play_next(ctx, ctx.guild.id))

        except Exception as e:
            print(f'An error occurred in the play command: {e}')
            await ctx.send(f'An error occurred: {e}')

@bot.command(name='leave', help='Bot leaves the voice channel (!leave)')
async def leave(ctx):
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
        else:
            await ctx.send('Bot is not in a voice channel')
    except Exception as e:
        print(f'An error occurred in the leave command: {e}')
        await ctx.send(f'An error occurred:{e}')

@bot.command(name='stop',help='Stops the current song (!stop)')
async def stop(ctx):
    try:
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send('Stopped the current song')
        else:
            await ctx.send('No song is currently playing')
    except Exception as e:
        print(f'An error occurred in the stop command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='next', help='Switches to the next queued song (!next)')
async def next(ctx):
    try:
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send('Playing the next song :3')
        elif not vc.is_playing() and queues.get(ctx.guild.id):
            play_next(ctx,ctx.guild.id)
            await ctx.send('Playing the next song :3')
        else:
            await ctx.send('The queue is empty :0')
    except Exception as e:
        print(f'An error occurred in the next command: {e}')
        await ctx.send(f'And error occurred: {e}')

@bot.command(name='show', help='Shows the current song playing and the queue (!show)')
async def show(ctx):
    try:
        vc = ctx.voice_client
        if vc and vc.is_playing() and hasattr(vc.source, 'data'):
            current_song_title = vc.source.data["title"]
            current_song_thumbnail = vc.source.data["thumbnail"]
            embed = discord.Embed(title="Now playing", description= current_song_title, color= discord.Color.blurple())
            embed.set_thumbnail(url=current_song_thumbnail)
            await ctx.send(embed=embed)
        else:
            await ctx.send('No song is currently being played')
        if queues.get(ctx.guild.id):
            for index, song in enumerate(queues[ctx.guild.id], start= 1):
                embed = discord.Embed(title=f'Queue #{index}', description= song.data["title"], color= discord.Color.green())
                embed.set_thumbnail(url= song.data["thumbnail"])
                await ctx.send(embed=embed)
        else:
            await ctx.send('The queue is empty :0')
    except Exception as e:
        print(f'An error occurred in the show command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='pause', help="Pauses the current song (!pause)")
async def pause(ctx):
    try:
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send('Paused the song hehe')
        else:
            await ctx.send('No song is being played')
    except Exception as e:
        print(f'An error occurred in the pause command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='resume', help='Resumes the current song (!resume)')
async def resume(ctx):
    try:
        vc = ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send('Resumed the current song UwU')
        else:
            await ctx.send('No song was played')
    except Exception as e:
        print(f'An error occurred in the resume command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='clear', help='Clears the current queue (!clear)')
async def clear(ctx):
    try:
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send('Queue cleared')
        else:
            await ctx.send('Noting in queue')
    except Exception as e:
        print(f'An error occurred in the clear command: {e}')
        await ctx.send(f'An error occurred: {e}')

@bot.command(name='commands', help='Shows all available commands (!commands)')
async def show_commands(ctx):
    try:
        command_list = []
        for command in bot.commands:
            if command.hidden:
                continue
            command_list.append(f'{command.name}: {command.help}')
        commands_text = '\n'.join(command_list)
        await ctx.send(f'```Available commands:\n{commands_text}```')
    except Exception as e:
        print(f'An error occurred in the show commands command: {e}')
        await ctx.send(f'An error occurred: {e}')



bot.run(config.token)
