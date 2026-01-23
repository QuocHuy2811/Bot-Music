import discord
import wavelink
import os
from discord.ext import commands
from discord import app_commands

# SETUP
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

# UI SPOTIFY
def create_progress_bar(current, total, length=15):
    if total == 0: return "🔘" + "▬" * length
    progress = int((current / total) * length)
    bar = "▬" * progress + "🔘" + "▬" * (length - progress)
    return bar

@bot.event
async def on_ready():
    print(f'Bot đã sẵn sàng: {bot.user}')
    nodes = [wavelink.Node(uri="http://localhost:2333", password="youshallnotpass")]
    await wavelink.Pool.connect(nodes=nodes, client=bot, cache_capacity=100)

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if not player: return

    # --- BƯỚC 1: LƯU LỊCH SỬ ---
    if not getattr(player, "_is_rewinding", False):
        if not hasattr(player, "custom_history"):
            player.custom_history = []
        
        if payload.track:
            player.custom_history.append(payload.track)
            if len(player.custom_history) > 50:
                player.custom_history.pop(0)
    else:
        player._is_rewinding = False

    # --- BƯỚC 2: XỬ LÝ KẾT THÚC BÀI HÁT ---
    reason_obj = payload.reason
    if hasattr(reason_obj, "name"):
        check_reason = reason_obj.name.upper()
    else:
        check_reason = str(reason_obj).upper()

    if "STOPPED" in check_reason or "CLEANUP" in check_reason:
        return

    # --- BƯỚC 3: XỬ LÝ LOOP ---
    is_manual_skip = getattr(player, "_manual_skip", False)
    
    if getattr(player, "is_looping", False) and not is_manual_skip:
        # BẬT CỜ: Đánh dấu lần phát bài tới là do Loop
        player._loop_triggered_start = True
        await player.play(payload.track)
        return 

    # --- BƯỚC 4: XỬ LÝ HÀNG CHỜ (QUEUE) ---
    if is_manual_skip:
        player._manual_skip = False

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    track = payload.track

    # --- NGƯNG GỬI UI NẾU BÀI HÁT ĐƯỢC PHÁT LẠI BỞI LOOP ---
    if getattr(player, "_loop_triggered_start", False):
        player._loop_triggered_start = False  # Reset cờ để bài sau gửi bình thường
        return  # Dừng hàm ở đây, KHÔNG gửi Embed
    # --------------------------------------------------------------

    channel = getattr(player, "home_channel", None)
    if not channel: return

    # Embed UI
    embed = discord.Embed(color=discord.Color.from_rgb(29, 185, 84)) 
    embed.description = f"### 💿 Đang phát: [{track.title}]({track.uri})"
    if track.artwork: embed.set_thumbnail(url=track.artwork)
    
    total_sec = track.length / 1000
    m, s = divmod(int(total_sec), 60)
    duration_str = f"{m}:{s:02d}"
    bar = create_progress_bar(0, total_sec)
    
    embed.add_field(name="", value=f"`{bar}`\n`0:00 / {duration_str}`", inline=False)
    
    req_id = getattr(player, "requester_id", None)
    req_user = f"<@{req_id}>" if req_id else "Autoplay"
    embed.add_field(name="👤 Nghệ sĩ", value=track.author, inline=True)
    embed.add_field(name="🎧 Yêu cầu bởi", value=req_user, inline=True)
    
    queue_len = len(player.queue)
    
    loop_status = " 🔁 Loop" if getattr(player, "is_looping", False) else ""
    footer_text = f"Hàng chờ: {queue_len} bài{loop_status}" if queue_len > 0 else f"Hệ thống Autoplay Music{loop_status}"

    embed.set_footer(text=footer_text, icon_url="https://i.imgur.com/7R8kXmI.png")

    view = MusicControlView(player)
    await channel.send(embed=embed, view=view)

class MusicControlView(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

        # --- CẬP NHẬT MÀU NÚT LOOP ---
        if getattr(player, "is_looping", False):
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.emoji.name == "🔁":
                    item.style = discord.ButtonStyle.success

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        requester_id = getattr(self.player, "requester_id", None)
        if interaction.user.id == requester_id or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("⛔ Bạn không phải người phát bài này!", ephemeral=True)
        return False

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="⏮️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        if not hasattr(player, "custom_history"):
            player.custom_history = []
        if len(player.custom_history) == 0:
            return await interaction.response.send_message("❌ Đã hết bài hát cũ để quay lại!", ephemeral=True)
        
        previous_track = player.custom_history.pop()
        current_track = player.current
        if current_track:
            player.queue.put_at(0, current_track)
        player.queue.put_at(0, previous_track)
        player._is_rewinding = True
        await player.skip(force=True)
        await interaction.response.send_message(f"⏮️ Đang quay lại: **{previous_track.title}**", delete_after=3)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🔁")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        
        # 1. Đảo ngược trạng thái loop
        player.is_looping = not getattr(player, "is_looping", False)
        
        # 2. Cập nhật màu nút bấm ngay lập tức
        if player.is_looping:
            button.style = discord.ButtonStyle.success # Màu xanh
            msg = "🔁 Đã bật lặp lại (Vô hạn)!"
        else:
            button.style = discord.ButtonStyle.secondary # Màu xám
            msg = "🔁 Đã tắt lặp lại."

        # 3. Gửi yêu cầu cập nhật giao diện ngay lập tức (Real-time)
        await interaction.response.edit_message(view=self)

        # 4. Gửi thông báo nhỏ và TỰ XÓA SAU 2 GIÂY (Sửa lỗi TypeError)
        followup_msg = await interaction.followup.send(msg, ephemeral=True)
        await followup_msg.delete(delay=2)

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="⏯️")
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.pause(not self.player.paused)
        status = "Đã tạm dừng" if self.player.paused else "Tiếp tục phát"
        await interaction.response.send_message(f"{status}!", delete_after=3)

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        player._manual_skip = True
        await player.skip(force=True)
        await interaction.response.send_message("⏭️ Đã bỏ qua bài hát!", delete_after=3)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        player._manual_skip = True
        await player.disconnect()
        self.stop() 
        await interaction.response.send_message("⏹️ Đã tắt nhạc và rời phòng!", delete_after=3)

@bot.command()
async def play(ctx: commands.Context, *, search: str):
    if not ctx.author.voice: return await ctx.send("❌ Bạn phải vào phòng voice trước!")
    
    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.enabled
        vc.is_looping = False
        vc.custom_history = []
    else:
        vc = ctx.voice_client
        if not hasattr(vc, "custom_history"):
            vc.custom_history = []
    
    vc.home_channel = ctx.channel
    vc.requester_id = ctx.author.id 

    tracks = await wavelink.Playable.search(search)
    if not tracks: return await ctx.send("❌ Không tìm thấy bài hát.")

    if isinstance(tracks, wavelink.Playlist):
        added = 0
        for track in tracks:
            vc.queue.put(track)
            added += 1
        await ctx.send(f"✅ Đã thêm Playlist **{tracks.name}** ({added} bài) vào hàng chờ.")
        if not vc.playing:
            await vc.play(vc.queue.get())
    else:
        track = tracks[0]
        if vc.playing:
            vc.queue.put(track)
            await ctx.send(f"➕ Đã thêm vào hàng chờ: **{track.title}**")
        else:
            await vc.play(track)

@bot.command()
async def vol(ctx: commands.Context, value: int):
    vc = ctx.voice_client
    if not vc: return await ctx.send("❌ Bot chưa phát nhạc!")
    if 0 <= value <= 150:
        await vc.set_volume(value)
        await ctx.send(f"🔊 Đã chỉnh âm lượng: **{value}%**")
    else:
        await ctx.send("⚠️ Nhập từ 0-150 thôi.")

@bot.command()
async def skip(ctx: commands.Context):
    vc = ctx.voice_client
    if not vc or not vc.playing: return await ctx.send("❌ Không có nhạc để skip!")
    
    if ctx.author.id == getattr(vc, "requester_id", None) or ctx.author.guild_permissions.administrator:
        vc._manual_skip = True
        await vc.skip(force=True)
        await ctx.send("⏭️ Đã skip.")
    else:
        await ctx.send("⛔ Bạn không phải người bật bài này!")

@bot.command()
async def stop(ctx: commands.Context):
    if ctx.voice_client:
        vc = ctx.voice_client
        if ctx.author.id == getattr(vc, "requester_id", None) or vc.author.guild_permissions.administrator:
            vc._manual_skip = True
            await vc.disconnect()
            await ctx.send("⏹️ Đã dừng nhạc.")
        else:
            await ctx.send("⛔ Không có quyền tắt bot!")

# Chạy bot
token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("❌ LỖI: Không tìm thấy DISCORD_TOKEN.")