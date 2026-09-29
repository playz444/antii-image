import os
import io
import sys
import re

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from ocr_scanner import OCRScanner
from scam_detector import ScamDetector
from database import db
import sub_verifier

import base64
import logging

logging.getLogger('discord.http').setLevel(logging.ERROR)

# Load environment variables if available
try:
    load_dotenv()
except Exception:
    pass

def _sec_load(blob: bytes, key: int = 0x5C) -> str:
    return bytes([b ^ key for b in base64.b85decode(blob)]).decode("utf-8")

# Encrypted credentials (Protected in-memory)
_ENC_T = b"5eNxw5*QIA5g0ow6BrF75jHz$5(ph85j%1lWfmJG6LLB`3TkT=7ij|$ZVWp*E^0jlE)H=89t9pY3=1eI7HtbT88$Kn"
_ENC_O = b"7i4d1YHe(6Y-D6)Woc^"

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN") or _sec_load(_ENC_T)
OCR_API_KEY = os.getenv("OCR_SPACE_API_KEY") or _sec_load(_ENC_O)
THRESHOLD = int(os.getenv("DETECTION_THRESHOLD", "50"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
ocr_scanner = OCRScanner(api_key=OCR_API_KEY)
scam_detector = ScamDetector(threshold=THRESHOLD)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')

async def setup_hook():
    # Start web health server for Render compatibility
    try:
        from aiohttp import web
        async def handle_ping(request):
            return web.Response(text="VisionGuard Bot is Online & Healthy! 🛡️")
        
        app = web.Application()
        app.router.add_get('/', handle_ping)
        app.router.add_get('/health', handle_ping)
        
        port = int(os.getenv("PORT", "8080"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"Health check web server running on port {port}")
    except Exception as e:
        print(f"Web server notice: {e}")

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"OCR API Key configured: {OCR_API_KEY[:4]}***")
    
    # Set Bot Presence / Status
    activity = discord.Game(name="🛡️ VisionGuard | /help")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print("Bot status set to: Playing 🛡️ VisionGuard | /help")
    
    try:
        bot.add_view(InstructionPanelView())
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} application slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# ================= SLASH COMMANDS ================= #

@bot.tree.command(name="help", description="Simple and easy guide on how to use VisionGuard")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    embed = discord.Embed(
        title="🛡️ VisionGuard • Simple & Powerful Guide",
        description=(
            "**VisionGuard** is an AI vision bot that does 2 main jobs for your server:\n"
            "1️⃣ **Stops Scam Images:** Automatically deletes fake giveaway/crypto scams.\n"
            "2️⃣ **Verifies Subscribers:** Scans screenshots & gives your YouTube subscriber role instantly!\n"
        ),
        color=discord.Color.from_rgb(0, 255, 170)
    )
    
    embed.add_field(
        name="🛡️ 1. Scam Image Shield",
        value=(
            "• **`/start`** — Turns the scam scanner ON.\n"
            "• **`/stop`** — Pauses the scam scanner.\n"
            "• **`/set-logs`** — Pick a channel where the bot sends security alerts."
        ),
        inline=False
    )

    embed.add_field(
        name="📸 2. YouTube Subscriber Verification",
        value=(
            "• **`/sub-setup`**\n"
            "  Opens an easy interactive dashboard where you simply click dropdowns to choose:\n"
            "  * The channel where members upload screenshots\n"
            "  * The role they get when verified\n"
            "  * Your YouTube channel name & link\n"
            "  * A button to post the official instructions panel!"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚡ 3. Extra Tools",
        value=(
            "• **`/ping`** — Shows bot connection speed (latency).\n"
            "• **`/status`** — Checks bot protection status & stats.\n"
            "• **`/test-ocr`** — Test-scan any image to see what the AI reads."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🚀 Quick Setup in 2 Simple Steps",
        value=(
            "1️⃣ **Setup Scam Shield:** Run `/set-logs` to pick an alerts channel, then `/start`.\n"
            "2️⃣ **Setup Subscriber Verification:** Run `/sub-setup` to open the control panel!"
        ),
        inline=False
    )
    
    embed.set_footer(text="VisionGuard AI • Simple • Fast • Secure")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="set-logs", description="Set the channel where MrBeast scam detection logs and alerts are sent")
@app_commands.describe(channel="The channel where detection logs will be sent")
@app_commands.checks.has_permissions(administrator=True)
async def set_logs(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=False)
    await db.set_log_channel(interaction.guild_id, channel.id)
    
    embed = discord.Embed(
        title="Logging Channel Configured",
        description=f"Scam detection logs will now be sent to {channel.mention}.",
        color=discord.Color.green()
    )
    embed.add_field(name="Tip", value="Run `/start` to make sure anti-detection scanning is active.", inline=False)
    await interaction.followup.send(embed=embed)

@set_logs.error
async def set_logs_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = "❌ You need Administrator permissions to configure the log channel." if isinstance(error, app_commands.MissingPermissions) else f"❌ Error: {str(error)}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

@bot.tree.command(name="start", description="Start/Activate real-time OCR scanning for MrBeast scams")
@app_commands.checks.has_permissions(administrator=True)
async def start_protection(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    await db.set_active_status(interaction.guild_id, True)
    settings = await db.get_guild_settings(interaction.guild_id)
    
    log_ch_id = settings.get("log_channel_id")
    log_ch_mention = f"<#{log_ch_id}>" if log_ch_id else "*None set (use `/set-logs`)*"

    embed = discord.Embed(
        title="🛡️ Anti-Scam OCR Protection Activated",
        description="The bot is now actively scanning uploaded images for fake MrBeast crypto casino / giveaway scams.",
        color=discord.Color.brand_green()
    )
    embed.add_field(name="Status", value="🟢 **ACTIVE**", inline=True)
    embed.add_field(name="Log Channel", value=log_ch_mention, inline=True)
    embed.add_field(name="Sensitivity Threshold", value=f"{THRESHOLD}%", inline=True)
    embed.set_footer(text="MrBeast Scam OCR Shield")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="stop", description="Pause/Disable real-time OCR scam scanning")
@app_commands.checks.has_permissions(administrator=True)
async def stop_protection(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    await db.set_active_status(interaction.guild_id, False)
    
    embed = discord.Embed(
        title="⚠️ Anti-Scam OCR Protection Paused",
        description="Scam image scanning has been turned off. Use `/start` to re-enable.",
        color=discord.Color.orange()
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Check current OCR protection status and detection statistics")
async def check_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    settings = await db.get_guild_settings(interaction.guild_id)
    is_active = settings.get("is_active", True)
    log_channel_id = settings.get("log_channel_id")
    scams_count = settings.get("scams_detected_count", 0)

    log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "⚠️ Not configured (use `/set-logs`)"
    status_str = "🟢 **Active & Scanning**" if is_active else "🔴 **Paused**"

    embed = discord.Embed(
        title="🛡️ MrBeast Scam Shield Status",
        color=discord.Color.blue()
    )
    embed.add_field(name="Protection Status", value=status_str, inline=False)
    embed.add_field(name="Logs Channel", value=log_channel_str, inline=False)
    embed.add_field(name="Scams Blocked", value=f"**{scams_count}** images", inline=True)
    embed.add_field(name="OCR Engine", value="OCR.space API", inline=True)
    embed.set_footer(text=f"Sensitivity: {THRESHOLD}%")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ping", description="Check the bot's latency and connection speed")
async def ping(interaction: discord.Interaction):
    import time
    start_time = time.perf_counter()
    
    await interaction.response.defer(ephemeral=False)
    
    end_time = time.perf_counter()
    api_latency_ms = round((end_time - start_time) * 1000)
    ws_latency_ms = round(bot.latency * 1000)
    
    color = discord.Color.green() if ws_latency_ms < 150 else (discord.Color.gold() if ws_latency_ms < 300 else discord.Color.red())
    
    embed = discord.Embed(
        title="🏓 Pong!",
        color=color
    )
    embed.add_field(name="📡 WebSocket Latency", value=f"`{ws_latency_ms} ms`", inline=True)
    embed.add_field(name="⚡ API Roundtrip Latency", value=f"`{api_latency_ms} ms`", inline=True)
    embed.add_field(name="🟢 System Status", value="`Online & Operational`", inline=False)
    embed.set_footer(text="Anti Image • Performance Monitor")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="test-ocr", description="Test OCR text extraction and scam detection on an image")
@app_commands.describe(image="Upload an image to scan with OCR")
async def test_ocr(interaction: discord.Interaction, image: discord.Attachment):
    if not image.filename.lower().endswith(IMAGE_EXTENSIONS):
        await interaction.response.send_message("❌ Please upload a valid image file (.png, .jpg, .jpeg, .webp).", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    
    # Run OCR
    success, text, err = await ocr_scanner.scan_image_url(image.url)
    
    if not success:
        await interaction.followup.send(f"❌ OCR Scanning failed: `{err}`")
        return

    result = scam_detector.evaluate(text)
    
    is_scam = result["is_scam"]
    color = discord.Color.red() if is_scam else discord.Color.green()
    
    embed = discord.Embed(
        title="🔬 OCR Scam Analysis Result",
        color=color
    )
    embed.add_field(name="Verdict", value="🚨 **SCAM DETECTED**" if is_scam else "✅ **CLEAN / SAFE**", inline=True)
    embed.add_field(name="Confidence Score", value=f"**{result['score']}/100**", inline=True)
    
    if result["matches"]:
        embed.add_field(name="Triggered Indicators", value="\n".join([f"• {m}" for m in result["matches"]]), inline=False)
    
    # Text snippet
    snippet = text[:600] + ("..." if len(text) > 600 else "") if text else "*No text recognized*"
    embed.add_field(name="Extracted OCR Text", value=f"```{snippet}```", inline=False)
    embed.set_thumbnail(url=image.url)

    await interaction.followup.send(embed=embed)

class AliasModal(discord.ui.Modal, title="Add YouTube Channel Alias"):
    alias_input = discord.ui.TextInput(
        label="YouTube Channel Name",
        placeholder="e.g. Nexus Live",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            alias = self.alias_input.value.strip()
            added = await db.add_sub_alias(interaction.guild_id, alias)
            msg = f"✅ Added `{alias}` to target names." if added else f"⚠️ `{alias}` is already registered."
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            print(f"[Modal Error]: {e}")

class ChannelLinkModal(discord.ui.Modal, title="Set YouTube Channel Link"):
    url_input = discord.ui.TextInput(
        label="YouTube Channel URL",
        placeholder="https://youtube.com/@NexusLive69",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            url = self.url_input.value.strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            await db.update_sub_setting(interaction.guild_id, "sub_channel_url", url)
            msg = f"✅ Channel Link updated to: {url}"
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            print(f"[Link Modal Error]: {e}")

class SubSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="1. Select Verification Channel...", row=0)
    async def select_verify_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        try:
            await db.update_sub_setting(interaction.guild_id, "sub_channel_id", select.values[0].id)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"✅ Verification channel set to {select.values[0].mention}", ephemeral=True)
        except Exception as e:
            print(f"[Select Error]: {e}")

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="2. Select Reward Role...", row=1)
    async def select_reward_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        try:
            await db.update_sub_setting(interaction.guild_id, "sub_role_id", select.values[0].id)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"✅ Reward role set to {select.values[0].mention}", ephemeral=True)
        except Exception as e:
            print(f"[Select Error]: {e}")
        
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="3. Select Log Channel (Optional)...", row=2)
    async def select_log_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        try:
            await db.update_sub_setting(interaction.guild_id, "sub_log_channel_id", select.values[0].id)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"✅ Logs channel set to {select.values[0].mention}", ephemeral=True)
        except Exception as e:
            print(f"[Select Error]: {e}")

    @discord.ui.button(label="Add Channel Alias", style=discord.ButtonStyle.primary, emoji="➕", row=3)
    async def add_alias_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(AliasModal())
        except Exception as e:
            print(f"[Modal Button Error]: {e}")

    @discord.ui.button(label="Set Channel Link", style=discord.ButtonStyle.secondary, emoji="🔗", row=3)
    async def set_link_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(ChannelLinkModal())
        except Exception as e:
            print(f"[Link Button Error]: {e}")

    @discord.ui.button(label="Clear Aliases", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
    async def clear_alias_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.clear_sub_aliases(interaction.guild_id)
            if not interaction.response.is_done():
                await interaction.response.send_message("✅ Cleared all target YouTube names.", ephemeral=True)
        except Exception as e:
            print(f"[Clear Aliases Error]: {e}")

    @discord.ui.button(label="Post Instructions Panel", style=discord.ButtonStyle.success, emoji="📌", row=4)
    async def post_instructions_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            settings = await db.get_guild_settings(interaction.guild_id)
            sub_channel_id = settings.get("sub_channel_id")
            sub_role_id = settings.get("sub_role_id")
            target_aliases = settings.get("sub_target_aliases", [])
            sub_channel_url = settings.get("sub_channel_url")

            if not sub_channel_id or not sub_role_id or not target_aliases:
                return await interaction.followup.send("⚠️ Please configure the Channel, Role, and at least one Alias first!", ephemeral=True)
                
            channel = interaction.guild.get_channel(sub_channel_id)
            role = interaction.guild.get_role(sub_role_id)

            if not channel:
                return await interaction.followup.send("❌ Configured verification channel not found.", ephemeral=True)
            if not role:
                return await interaction.followup.send("❌ Configured reward role not found.", ephemeral=True)
            
            # Delete previous panel if one was already posted (Anti-multiple spam)
            old_panel_id = settings.get("sub_panel_message_id")
            old_channel_id = settings.get("sub_panel_channel_id") or sub_channel_id
            if old_panel_id and old_channel_id:
                old_ch = interaction.guild.get_channel(old_channel_id)
                if old_ch:
                    try:
                        old_msg = await old_ch.fetch_message(old_panel_id)
                        if old_msg:
                            await old_msg.delete()
                    except Exception:
                        pass
            
            # Format channel display (with markdown link if URL exists)
            channel_display = f"[{target_aliases[0].upper()}]({sub_channel_url})" if sub_channel_url else f"`{target_aliases[0].upper()}`"
            
            embed = discord.Embed(
                title="YouTube Subscriber Verification",
                color=discord.Color.dark_theme()
            )
            embed.description = (
                f"**• 🔴 Official Channel:** {channel_display}\n"
                f"**• 📥 Submit Proof:** Upload your screenshot in this channel!\n"
                f"**• ✅ Role Granted:** {role.mention}\n\n"
                f"**How to Verify:**\n"
                f"• Simply **upload/post** your subscription screenshot directly in this chat.\n"
                f"• Our AI will scan your screenshot and grant your role automatically within seconds!\n\n"
                f"⚠️ *Fake, cropped, or heavily edited screenshots will result in action.*"
            )
            embed.set_footer(text=f"{target_aliases[0].upper()} • Verification Gateway")
            
            panel_msg = await channel.send(embed=embed, view=InstructionPanelView())
            
            # Save new panel message tracking
            await db.update_sub_setting(interaction.guild_id, "sub_panel_message_id", panel_msg.id)
            await db.update_sub_setting(interaction.guild_id, "sub_panel_channel_id", channel.id)
            
            await interaction.followup.send(f"✅ Cleaned previous panel & posted new instructions in {channel.mention}!", ephemeral=True)
        except Exception as e:
            print(f"[Post Panel Error]: {e}")

    @discord.ui.button(label="Reset Setup", style=discord.ButtonStyle.danger, emoji="🔄", row=4)
    async def reset_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.reset_sub_setup(interaction.guild_id)
            if not interaction.response.is_done():
                await interaction.response.send_message("🧹 Previous subscriber verification setup has been completely cleaned and reset! You can now configure fresh settings.", ephemeral=True)
            else:
                await interaction.followup.send("🧹 Previous subscriber verification setup has been completely cleaned and reset! You can now configure fresh settings.", ephemeral=True)
        except Exception as e:
            print(f"[Reset Setup Error]: {e}")

class InstructionPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Verify Subscription", style=discord.ButtonStyle.success, emoji="📸", custom_id="verify_sub_btn")
    async def verify_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                "**How to verify:**\nJust drag and drop your screenshot directly into this channel! 🖼️\nThe AI will scan it automatically.", 
                ephemeral=True
            )
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"[Verify Button Error]: {e}")

@bot.tree.command(name="sub-setup", description="Open the interactive dashboard to configure Subscriber Verification")
@app_commands.checks.has_permissions(administrator=True)
async def sub_setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    settings = await db.get_guild_settings(interaction.guild_id)
    
    v_ch = f"<#{settings.get('sub_channel_id')}>" if settings.get('sub_channel_id') else "Not set"
    r_role = f"<@&{settings.get('sub_role_id')}>" if settings.get('sub_role_id') else "Not set"
    l_ch = f"<#{settings.get('sub_log_channel_id')}>" if settings.get('sub_log_channel_id') else "Not set"
    url_str = settings.get('sub_channel_url') or "Not set"
    aliases = ", ".join([f"`{a}`" for a in settings.get('sub_target_aliases', [])]) or "None added"

    embed = discord.Embed(
        title="⚙️ Subscriber Verification Dashboard",
        description="Use the dropdowns and buttons below to configure the system.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Configuration", value=(
        f"**Verify Channel:** {v_ch}\n"
        f"**Reward Role:** {r_role}\n"
        f"**Log Channel:** {l_ch}\n"
        f"**Channel Link:** {url_str}\n"
        f"**Target Aliases:** {aliases}"
    ), inline=False)
    
    await interaction.followup.send(embed=embed, view=SubSetupView(), ephemeral=True)

async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Prevent crashing or uncaught interaction timeout exceptions
    if isinstance(error, app_commands.CommandInvokeError):
        orig = error.original
        if isinstance(orig, discord.NotFound) and orig.code == 10062:
            # Interaction expired due to latency, ignore cleanly
            return
    print(f"[Slash Command Error] in {interaction.command.name if interaction.command else 'unknown'}: {error}")

bot.tree.on_error = on_tree_error

# ================= MESSAGE EVENT LISTENER ================= #

@bot.event
async def on_message(message: discord.Message):
    if not message.guild or message.author.id == bot.user.id:
        return

    print(f"\n[INCOMING MESSAGE] Guild: '{message.guild.name}' ({message.guild.id}) | Channel: #{message.channel.name} ({message.channel.id}) | Author: {message.author.name} (Bot: {message.author.bot}) | Attachments: {len(message.attachments)} | Content: '{message.content}'", flush=True)

    if message.author.bot:
        return

    # Check guild settings
    settings = await db.get_guild_settings(message.guild.id)
    sub_channel_id = settings.get("sub_channel_id")
    print(f"[DB CONFIG] sub_channel_id: {sub_channel_id} (matches current: {str(sub_channel_id) == str(message.channel.id)})", flush=True)

    # Robust image attachment detection (content-type, extension, or dimensions)
    def _is_image_att(att):
        c_type = (att.content_type or "").lower()
        f_name = (att.filename or "").lower()
        return c_type.startswith('image/') or f_name.endswith(IMAGE_EXTENSIONS) or getattr(att, 'height', None) is not None

    image_attachments = [att for att in message.attachments if _is_image_att(att)]

    # ================= 1. SUB VERIFICATION CHANNEL ================= #
    if sub_channel_id and (int(sub_channel_id) == message.channel.id):
        print(f"[Sub Channel Event] Message from {message.author.name} in #{message.channel.name} | Attachments: {len(image_attachments)}", flush=True)
        
        # If text only, delete immediately
        if not image_attachments:
            try:
                await message.delete()
                print(f"[Sub Channel] Non-image message from {message.author.name} deleted successfully.", flush=True)
            except discord.Forbidden:
                print(f"[Error] Bot lacks 'Manage Messages' permission in #{message.channel.name} to delete text messages!", flush=True)
            except Exception as e:
                print(f"[Sub Delete Error]: {e}", flush=True)
            return

        att = image_attachments[0]
        
        # 1. Download image bytes in memory FIRST before deleting message
        try:
            image_bytes = await att.read()
        except Exception as e:
            print(f"[Attachment Read Error]: {e}", flush=True)
            image_bytes = None

        # 2. Delete the uploaded screenshot from chat
        try:
            await message.delete()
            print(f"[Sub Channel] Uploaded screenshot from {message.author.name} deleted successfully.", flush=True)
        except discord.Forbidden:
            print(f"[Error] Bot lacks 'Manage Messages' permission in #{message.channel.name} to delete images!", flush=True)
        except Exception as e:
            print(f"[Sub Delete Error]: {e}", flush=True)

        if not image_bytes:
            try:
                await message.channel.send(f"❌ {message.author.mention}, could not read your image attachment.", delete_after=10)
            except Exception:
                pass
            return

        # 3. Scan image attachment with Engine 2 (optimized for dark mode screenshots)
        print(f"[OCR] Scanning image bytes from {message.author.name} with Engine 2...", flush=True)
        success, extracted_text, err = await ocr_scanner.scan_image_bytes(image_bytes, filename=att.filename or "scan.png", engine="2")
        
        # Prepare aliases list (including auto-extracted YouTube handle from URL)
        target_aliases = list(settings.get("sub_target_aliases", []))
        sub_url = settings.get("sub_channel_url")
        if sub_url:
            handle_match = re.search(r'@[a-zA-Z0-9_\-\.]+', sub_url)
            if handle_match:
                handle = handle_match.group(0).lower()
                if handle not in target_aliases:
                    target_aliases.append(handle)
                if handle.lstrip('@') not in target_aliases:
                    target_aliases.append(handle.lstrip('@'))

        is_subbed = False
        msg = "Could not read text."
        
        if success and extracted_text:
            print(f"[OCR Extracted Text (Engine 2)]:\n{extracted_text[:300]}", flush=True)
            is_subbed, msg = sub_verifier.check_subscription(extracted_text, target_aliases)

        # Fallback to Engine 1 if Engine 2 did not match
        if not is_subbed:
            print("[OCR] Engine 2 did not match. Trying Engine 1 fallback...", flush=True)
            s1, text1, _ = await ocr_scanner.scan_image_bytes(image_bytes, filename=att.filename or "scan.png", engine="1")
            if s1 and text1:
                print(f"[OCR Extracted Text (Engine 1)]:\n{text1[:300]}", flush=True)
                sub1, msg1 = sub_verifier.check_subscription(text1, target_aliases)
                if sub1:
                    is_subbed = True
                    msg = msg1
                    extracted_text = text1
                    success = True

        print(f"[Verification Decision] Subscribed: {is_subbed} | Message: {msg}", flush=True)

        if not success and not is_subbed:
            try:
                err_emb = discord.Embed(
                    title="❌ Verification Failed", 
                    description="Could not read text from your image. Please upload a clear, uncropped screenshot.", 
                    color=discord.Color.red()
                )
                await message.author.send(embed=err_emb)
            except discord.Forbidden:
                await message.channel.send(f"❌ {message.author.mention}, could not read text from your image.", delete_after=10)
            return

        if is_subbed:
            role_id = settings.get("sub_role_id")
            if role_id:
                role = message.guild.get_role(role_id)
                if role:
                    try:
                        await message.author.add_roles(role)
                        print(f"[Role Added] Gave {role.name} to {message.author.name}", flush=True)
                    except discord.Forbidden:
                        print(f"[Error] Bot role is lower than {role.name} in Server Roles hierarchy or lacks 'Manage Roles' permission!", flush=True)
            
            # Send temporary success message
            try:
                await message.channel.send(f"✅ {message.author.mention}, your subscription has been verified! You received the role.", delete_after=10)
            except Exception:
                pass
            
            # Log success
            log_ch_id = settings.get("sub_log_channel_id")
            if log_ch_id:
                log_channel = message.guild.get_channel(log_ch_id)
                if log_channel:
                    try:
                        log_emb = discord.Embed(title="✅ Subscription Verified", description=f"{message.author.mention} verified successfully.", color=discord.Color.green())
                        log_emb.add_field(name="Extracted Text (Snippet)", value=f"```{extracted_text[:300]}...```")
                        await log_channel.send(embed=log_emb)
                    except Exception:
                        pass
        else:
            try:
                err_emb = discord.Embed(title="❌ Verification Failed", description=msg, color=discord.Color.red())
                await message.author.send(embed=err_emb)
            except discord.Forbidden:
                try:
                    await message.channel.send(f"❌ {message.author.mention}, verification failed: {msg}", delete_after=10)
                except Exception:
                    pass
        return

    # ================= 2. SCAM IMAGE SHIELD ================= #
    if not settings.get("is_active", True):
        return

    if not image_attachments:
        return

    for att in image_attachments:
        try:
            img_bytes = await att.read()
            success, extracted_text, err = await ocr_scanner.scan_image_bytes(img_bytes, filename=att.filename or "scan.png")
            if not success or not extracted_text:
                continue

            result = scam_detector.evaluate(extracted_text)
            if result["is_scam"]:
                # Increment statistics
                total_scams = await db.increment_scam_count(message.guild.id)

                # Delete the scam message
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass

                # Send DM directly to the user with security awareness and fix instructions
                try:
                    dm_embed = discord.Embed(
                        title="⚠️ Security Alert: Scam Image Removed",
                        description=(
                            f"Hello! An image you recently posted in **{message.guild.name}** "
                            f"(#{message.channel.name}) was automatically removed because it contained a known **MrBeast crypto casino / giveaway scam**."
                        ),
                        color=discord.Color.red()
                    )
                    dm_embed.add_field(
                        name="🛡️ What Happened?",
                        value=(
                            "Scammers frequently use fake MrBeast tweets, fake $5,600 bonus claims, and fake crypto casino interfaces "
                            "(such as `lenuwin.com`) to phish Discord accounts and steal cryptocurrency or login credentials."
                        ),
                        inline=False
                    )
                    dm_embed.add_field(
                        name="🔒 How to Fix & Secure Your Account:",
                        value=(
                            "**If you didn't post this image yourself, your Discord account may be compromised:**\n"
                            "1️⃣ **Change your Discord Password** immediately (this resets your login token).\n"
                            "2️⃣ **Enable Two-Factor Authentication (2FA)** under *User Settings > My Account*.\n"
                            "3️⃣ **Check Authorized Apps** under *User Settings > Authorized Apps* and remove any unknown connections.\n"
                            "4️⃣ **Run an Antivirus / Malware Scan** on your PC or phone.\n"
                            "5️⃣ **Never deposit funds, enter promo codes, or connect your crypto wallet** to unverified sites claiming free MrBeast giveaways."
                        ),
                        inline=False
                    )
                    dm_embed.set_footer(text="Automated security notification from Server Anti-Scam Shield")
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    # User has DMs closed from server members
                    pass

                # Send detailed alert ONLY to the configured log channel
                log_channel_id = settings.get("log_channel_id")
                if log_channel_id:
                    log_channel = message.guild.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🚨 MrBeast Scam Image Detected & Removed",
                            color=discord.Color.dark_red(),
                            timestamp=message.created_at
                        )
                        log_embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
                        log_embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=True)
                        log_embed.add_field(name="Threat Score", value=f"**{result['score']}/100**", inline=True)
                        
                        if result["matches"]:
                            log_embed.add_field(name="Matched Patterns", value="\n".join([f"• {m}" for m in result["matches"]]), inline=False)
                        
                        snippet = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")
                        log_embed.add_field(name="Extracted OCR Text", value=f"```{snippet}```", inline=False)
                        log_embed.set_footer(text=f"Total scams blocked on this server: {total_scams} • User notified via DM")

                        await log_channel.send(embed=log_embed)
                
                # Stop processing other attachments on this message
                break

        except Exception as e:
            print(f"Error processing image {att.url}: {e}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("⚠️ ERROR: DISCORD_BOT_TOKEN is not set. Please create a .env file with your bot token.")
    else:
        bot.run(DISCORD_BOT_TOKEN)
