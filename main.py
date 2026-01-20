import discord
import wavelink
import os
from discord.ext import commands
from discord import app_commands

# 1. ĐỔI PREFIX SANG '?'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot đã sẵn sàng: {bot.user}')
    nodes = [wavelink.Node(uri="http://localhost:2333", password="youshallnotpass")]
    await wavelink.Pool.connect(nodes=nodes, client=bot, cache_capacity=100)

# 1. Sự kiện tự động lấy bài từ hàng chờ khi bài cũ kết thúc
@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if not player: return

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

# 2. Sự kiện HIỂN THỊ FORM mỗi khi có bài mới bắt đầu (Dù là Skip hay Tự chuyển)
@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    track = payload.track
    
    # Lấy channel chúng ta đã lưu ở lệnh ?play
    channel = getattr(player, "home_channel", None)
    if not channel: return

    # THIẾT KẾ EMBED (Giống y hệt mẫu ?play của bạn)
    embed = discord.Embed(
        title="🎶 Đang phát nhạc",
        description=f"**[{track.title}]({track.uri})**",
        color=discord.Color.brand_green()
    )
    embed.add_field(name="👤 Tác giả", value=track.author, inline=True)
    
    minutes, seconds = divmod(int(track.length / 1000), 60)
    embed.add_field(name="⏰ Thời lượng", value=f"{minutes}:{seconds:02d}", inline=True)
    
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    
    embed.set_footer(text="Hệ thống tự động chuyển bài" if not player.queue.is_empty else "Đang phát nhạc")

    # Gửi Embed kèm theo Nút bấm
    view = MusicControlView(player)
    await channel.send(embed=embed, view=view)

# GIAO DIỆN NÚT BẤM (UI)
class MusicControlView(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.secondary, emoji="⏯️")
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.pause(not self.player.paused)
        await interaction.response.send_message(f"{'Đã tạm dừng' if self.player.paused else 'Tiếp tục phát'}!", delete_after=3)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.skip(force=True)
        await interaction.response.send_message("Đã bỏ qua bài hát!", delete_after=3)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Ngắt kết nối player
        await self.player.disconnect()
        # 2. Dừng View (Lúc này self.stop() sẽ gọi đúng hàm hệ thống của discord.ui.View)
        self.stop() 
        await interaction.response.send_message("Đã tắt nhạc và rời phòng!", delete_after=3)

# LỆNH PLAY VỚI GIAO DIỆN EMBED
@bot.command()
async def play(ctx: commands.Context, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ Bạn phải vào phòng voice trước!")

    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.enabled # THÊM DÒNG NÀY
    else:
        vc: wavelink.Player = ctx.voice_client
    vc.home_channel = ctx.channel
    # Tìm kiếm bài hát (Ưu tiên YouTube Music để âm thanh hay hơn)
    tracks = await wavelink.Playable.search(search)
    if not tracks:
        return await ctx.send("❌ Không tìm thấy bài hát.")

    track = tracks[0]
    
    if vc.playing:
        vc.queue.put(track)
        await ctx.send(f"➕ Đã thêm vào hàng chờ: **{track.title}**")
    else:
        await vc.play(track)
        
# 2. LỆNH ?vol ĐỂ SET ÂM LƯỢNG
@bot.command()
async def vol(ctx: commands.Context, value: int):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await ctx.send("❌ Bot chưa phát nhạc!")
    
    if 0 <= value <= 150:
        await vc.set_volume(value)
        await ctx.send(f"🔊 Đã chỉnh âm lượng thành: **{value}%**")
    else:
        await ctx.send("⚠️ Vui lòng nhập âm lượng từ 0 đến 150.")

@bot.command()
async def skip(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client

    if not vc or not vc.playing:
        return await ctx.send("❌ Hiện tại bot không phát nhạc để bỏ qua!")

    # Lưu tên bài hát cũ để thông báo
    old_track = vc.current.title
    
    # Thực hiện lệnh skip
    await vc.skip(force=True)
    
    await ctx.send(f"⏭️ Đã bỏ qua bài: **{old_track}**")

@bot.command()
async def stop(ctx: commands.Context):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Đã dừng phát nhạc.")

# Chạy bot
token = os.getenv('DISCORD_TOKEN')

if token:
    bot.run(token)
else:
    print("❌ LỖI: Không tìm thấy biến môi trường 'DISCORD_TOKEN'.")
    print("👉 Hãy đảm bảo bạn đã thêm DISCORD_TOKEN vào phần Environment Variables trên Koyeb.")