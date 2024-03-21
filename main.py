import asyncio

import discord
import os

from discord.ext import commands
from discord.ext.commands.context import Context

from ydl import ytdl, YDLInfo

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot('$', intents=intents)


def default_embed_msg(title: str, description: str = None, url: str = None, footer: str = None):
    e = discord.Embed(
        color=discord.Colour.orange(),
        title=title,
        description=description,
        url=url,
    )
    e.set_footer(text=footer)
    return e


def default_error_msg(title: str):
    return discord.Embed(
        title=title,
        color=discord.Colour.red()
    )


class MusicPlayer:
    _volume: float = 1.0

    def __init__(self):
        self._volume: float = 1.0
        self.end_playing = asyncio.Event()
        self.queue: list[YDLInfo] = []
        self.worker: asyncio.Task | None = None
        self.vc: discord.VoiceClient | None = None
        self.playing_now: YDLInfo | None = None

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value
        if self.playing_now:
            self.vc.source.volume = value

    async def add(self, ctx: Context, player: YDLInfo):
        self.queue.append(player)
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self.player(ctx), name='Player')

    async def player(self, ctx: Context):
        while len(self.queue) > 0:
            self.vc = ctx.voice_client

            if self.vc is None:
                self.vc = await ctx.author.voice.channel.connect()

            self.playing_now = self.queue.pop(0)
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening,
                                                                name=self.playing_now.title))

            self.playing_now.volume = self.volume
            await ctx.send(embed=default_embed_msg(
                title=self.playing_now.title,
                description='Now playing',
                url=self.playing_now.url
            ))
            self.vc.play(self.playing_now.init_source(), after=lambda e: self.send_end_playing())

            await self.end_playing.wait()

    async def stop_playing(self):
        await bot.change_presence(activity=None, status=None)
        if len(self.queue) == 0:
            await self.vc.disconnect()

    def send_end_playing(self):
        asyncio.run_coroutine_threadsafe(self.stop_playing(), bot.loop)
        self.playing_now = None
        self.end_playing.set()
        self.end_playing.clear()

    async def add_music_by_url(self, ctx: Context, url: str):
        player = await YDLInfo.from_url(url, self.volume, loop=bot.loop)
        await self.add(ctx, player)
        await ctx.send(embed=default_embed_msg(
            title=player.title,
            description='Successfully added to queue',
            url=player.url
        ))


music_player = MusicPlayer()


@bot.command()
async def play(ctx: Context, url: str | None = discord.ext.commands.param(
    default=None,
    description='URL на трек для проигрывания, если не указан, то эквивалентно $resume'
)):
    """
    Проигрывание музыки (Поддерживается только youtube)
    """
    if url is None:
        return await resume(ctx)
    async with ctx.typing():
        if ctx.author.voice is None:
            return await ctx.send(embed=default_error_msg('You must join voice channel to play...'))

        if 'playlist' in url:
            info = ytdl.extract_info(url, download=False, process=False)
            tasks = []
            for v in info['entries']:
                t = YDLInfo.from_url(v.get('url'), music_player.volume, loop=bot.loop)
                tasks.append(t)

            players = await asyncio.gather(*tasks)
            msg = ''
            for i, player in enumerate(players):
                if player is None:
                    continue
                await music_player.add(ctx, player)
                msg += f'**{i}.** {player.title}\n'

            return await ctx.send(embed=default_embed_msg(
                title=f'{len(players)} tracks added to queue',
                description=f'{msg}',
            ))

        await music_player.add_music_by_url(ctx, url)


@bot.command(aliases=['q'])
async def queue(ctx: Context):
    """
    Отображение очереди
    """
    if music_player.playing_now is None:
        return await ctx.send(embed=default_error_msg('Queue is empty...'))

    msg = ''
    for i, v in enumerate(music_player.queue):
        msg += f'{i + 1}. {v.title}\n'

    embed = default_embed_msg(
        title=f'Playing now: {music_player.playing_now.title}',
        description=msg,
        footer='Queue status',
    )

    await ctx.send(embed=embed)


@bot.command()
async def pause(ctx: Context):
    """
    Пауза, resume для продолжения
    """
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    music_player.vc.pause()


@bot.command()
async def resume(ctx: Context):
    """
    Возобновление воспроизведения, pause для остановки
    """
    if music_player.vc is None or not music_player.vc.is_paused():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    music_player.vc.resume()


@bot.command()
async def skip(ctx: Context, n: int | None = discord.ext.commands.param(
    default=1,
    description='Количество треков для пропуска'
)):
    """
    Пропустить трек
    """
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    if n < 1:
        return await ctx.send(embed=default_error_msg('Invalid number...'))

    music_player.queue = music_player.queue[n-1:]

    await ctx.send(embed=default_embed_msg(
        title=music_player.playing_now.title,
        description=f'Skipped {n} tracks',
        url=music_player.playing_now.url
    ))
    music_player.vc.stop()


@bot.hybrid_command()
async def clear(ctx: Context):
    """
    Очистка очереди
    """
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing to clear...'))

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect(force=True)

    music_player.queue = []
    music_player.send_end_playing()

    await music_player.vc.disconnect()

    return await ctx.send(embed=default_embed_msg('Successfully cleared...'))


@bot.command()
async def reset(ctx: Context):
    """
    Восстановление воспроизведения
    """
    if music_player.vc is None:
        return await ctx.send(embed=default_error_msg('Nothing to reset...'))

    music_player.vc.pause()
    music_player.vc.resume()

    return await ctx.send(embed=default_embed_msg('Reset'))


@bot.command()
async def volume(ctx: Context, value: int | None = discord.ext.commands.param(
    default=100,
    description='Уровень громкости (0 - 100)'
)):
    """Установка громкости"""
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))
    if value < 0 or value > 200:
        return await ctx.send(embed=default_error_msg('Invalid volume (must be 0 - 100)...'))

    music_player.volume = value / 100
    await ctx.send(embed=default_embed_msg(f'Volume set to {value}%'))


if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    bot.run(token)
