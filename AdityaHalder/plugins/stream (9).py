import aiofiles, aiohttp, base64, json, os, random, re, requests, asyncio
import httpx

from .. import app, bot, call, cdz, console
from urllib.parse import urlparse
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ntgcalls import TelegramServerError
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import MediaStream
from pytgcalls.types import AudioQuality, VideoQuality
from youtubesearchpython.__future__ import VideosSearch


def parse_query(query: str) -> str:
    if bool(re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|shorts/|live/)?([A-Za-z0-9_-]{11})(?:[?&].*)?$', query)):
        match = re.search(r'(?:v=|\/(?:embed|v|shorts|live)\/|youtu\.be\/)([A-Za-z0-9_-]{11})', query)
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"
        
    return query


def parse_tg_link(link: str):
    parsed = urlparse(link)
    path = parsed.path.strip('/')
    parts = path.split('/')
    
    if len(parts) >= 2:
        return str(parts[0]), int(parts[1])
        
    return None, None


async def fetch_song(query: str, fmt: str = "video"):
    api_url = "https://bitflow.in/api/youtube"
    params = {
        "query": query,
        "format": fmt,
        "api_key": "1spiderkey2"
    }

    try:
        async with httpx.AsyncClient(timeout=150) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"📊 API Response: {data}")  # Debug log
            return data
    except Exception as e:
        print(f"❌ fetch_song error: {e}")
        return {}


async def download_direct_url(url: str, file_path: str):
    """Download file directly from URL"""
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        return True
    except Exception as e:
        print(f"❌ Direct download error: {e}")
        return False


def convert_to_seconds(duration: str) -> int:
    parts = list(map(int, duration.split(":")))
    total = 0
    multiplier = 1

    for value in reversed(parts):
        total += value * multiplier
        multiplier *= 60

    return total


def format_duration(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    sec = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if sec > 0 or not parts:
        parts.append(f"{sec}s")

    return " ".join(parts)


def seconds_to_hhmmss(seconds):
    if seconds < 3600:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes:02}:{sec:02}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{hours:d}:{minutes:02}:{sec:02}"


def random_color():
    return (random.randint(80, 255), random.randint(80, 255), random.randint(80, 255))


def trim_text(draw, text, font, max_width):
    """Ensure text fits inside max_width, otherwise trim and add '...'"""
    if not text:
        return ""
    original = text
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        text = text[:-1]
    if text != original:
        while True:
            bbox = draw.textbbox((0, 0), text + "...", font=font)
            if bbox[2] - bbox[0] <= max_width or len(text) == 0:
                break
            text = text[:-1]
        text = text + "..."
    return text


async def create_music_thumbnail(cover_path, title, artist, duration_seconds=None, output_path="thumbnail.png"):
    # Handle title/artist
    if not title or title.strip() == "":
        title = "Unknown Title"
    if not artist or artist.strip() == "":
        artist = "Unknown Artist"

    # Handle time
    if (
        duration_seconds is None
        or duration_seconds == 0
        or duration_seconds == "live"
    ):
        total_time = "Live"
        tot_sec = None
    else:
        tot_sec = duration_seconds
        total_time = seconds_to_hhmmss(duration_seconds)

    if tot_sec:
        cur_sec = random.randint(0, tot_sec)
        current_time = seconds_to_hhmmss(cur_sec)
    else:
        cur_sec = random.randint(0, 7200)
        current_time = seconds_to_hhmmss(cur_sec)

    # Load cover and background
    cover = Image.open(cover_path).convert("RGBA").resize((500, 500))
    bg = cover.copy().resize((1280, 720))
    bg = bg.filter(ImageFilter.GaussianBlur(25))

    # --- Gradient overlay background ---
    grad_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad_overlay)
    c1, c2 = random_color(), random_color()
    for i in range(bg.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/bg.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/bg.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/bg.height))
        gdraw.line([(0, i), (bg.width, i)], fill=(r, g, b, 80))
    bg = Image.alpha_composite(bg, grad_overlay)

    # --- Glassmorphic Player Card ---
    card_w, card_h = 700, 380
    border_thickness = 5  

    # gradient for card border
    grad = Image.new("RGBA", (card_w + border_thickness*2, card_h + border_thickness*2), (0,0,0,0))
    gdraw = ImageDraw.Draw(grad)
    c1, c2 = random_color(), random_color()
    for i in range(grad.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/grad.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/grad.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/grad.height))
        gdraw.line([(0, i), (grad.width, i)], fill=(r, g, b))

    mask_outer = Image.new("L", grad.size, 0)
    mask_inner = Image.new("L", (card_w, card_h), 0)
    d_outer = ImageDraw.Draw(mask_outer)
    d_inner = ImageDraw.Draw(mask_inner)

    d_outer.rounded_rectangle([0, 0, grad.width, grad.height], 36, fill=255)
    d_inner.rounded_rectangle([0, 0, card_w, card_h], 30, fill=255)

    mask_inner_padded = Image.new("L", grad.size, 0)
    mask_inner_padded.paste(mask_inner, (border_thickness, border_thickness))
    mask_outer.paste(0, (0,0), mask_inner_padded)

    border = Image.composite(grad, Image.new("RGBA", grad.size, (0,0,0,0)), mask_outer)

    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 60))
    mask_card = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask_card).rounded_rectangle([0,0,card_w,card_h], 30, fill=255)

    card_with_border = border.copy()
    card_with_border.paste(card, (border_thickness, border_thickness), mask_card)

    # position card CENTER
    x = (bg.width - card_with_border.width) // 2
    y = (bg.height - card_with_border.height) // 2
    bg.paste(card_with_border, (x,y), card_with_border)

    # --- Album cover inside card with gradient border ---
    cover_size = 200
    border_size = 6  # thin border

    # Gradient border for cover
    grad_cover = Image.new("RGBA", (cover_size + border_size*2, cover_size + border_size*2), (0,0,0,0))
    gdraw = ImageDraw.Draw(grad_cover)
    c1, c2 = random_color(), random_color()
    for i in range(grad_cover.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/grad_cover.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/grad_cover.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/grad_cover.height))
        gdraw.line([(0, i), (grad_cover.width, i)], fill=(r, g, b))

    mask_outer = Image.new("L", grad_cover.size, 0)
    mask_inner = Image.new("L", (cover_size, cover_size), 0)
    d_outer = ImageDraw.Draw(mask_outer)
    d_inner = ImageDraw.Draw(mask_inner)

    d_outer.rounded_rectangle([0,0,grad_cover.width,grad_cover.height], 30, fill=255)
    d_inner.rounded_rectangle([0,0,cover_size,cover_size], 26, fill=255)

    mask_inner_padded = Image.new("L", grad_cover.size, 0)
    mask_inner_padded.paste(mask_inner, (border_size, border_size))
    mask_outer.paste(0, (0,0), mask_inner_padded)

    border_cover = Image.composite(grad_cover, Image.new("RGBA", grad_cover.size, (0,0,0,0)), mask_outer)

    cover_resized = cover.resize((cover_size, cover_size))
    mask_cover = Image.new("L", (cover_size, cover_size), 0)
    ImageDraw.Draw(mask_cover).rounded_rectangle([0,0,cover_size,cover_size], 26, fill=255)

    cover_with_border = border_cover.copy()
    cover_with_border.paste(cover_resized, (border_size, border_size), mask_cover)

    cover_x = x + border_thickness + 30
    cover_y = y + (card_h - cover_with_border.height)//2 + border_thickness
    bg.paste(cover_with_border, (cover_x, cover_y), cover_with_border)

    # --- Draw texts and progress bar ---
    draw = ImageDraw.Draw(bg)
    try:
        font_title = ImageFont.truetype("AdityaHalder/resource/font.ttf", 36)
        font_artist = ImageFont.truetype("AdityaHalder/resource/font.ttf", 28)
        font_time = ImageFont.truetype("AdityaHalder/resource/font.ttf", 24)
    except:
        # Fallback to default font if custom font not found
        font_title = ImageFont.load_default()
        font_artist = ImageFont.load_default()
        font_time = ImageFont.load_default()

    max_width = card_w - 300
    title = trim_text(draw, title, font_title, max_width)
    artist = trim_text(draw, artist, font_artist, max_width)

    text_x = cover_x + cover_with_border.width + 30
    draw.text((text_x, y + 86), title, font=font_title, fill="white")
    draw.text((text_x, y + 146), artist, font=font_artist, fill="white")

    # Progress bar
    progress_x, progress_y = text_x, y + 206
    bar_w, bar_h = 380, 8
    prog_fill = int((cur_sec / tot_sec) * bar_w) if tot_sec else bar_w

    draw.rounded_rectangle([progress_x, progress_y, progress_x + bar_w, progress_y + bar_h],
                           5, fill=(120, 120, 120, 160))

    c1, c2 = random_color(), random_color()
    for i in range(prog_fill):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/max(1, prog_fill)))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/max(1, prog_fill)))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/max(1, prog_fill)))
        draw.line([(progress_x + i, progress_y), (progress_x + i, progress_y + bar_h)], fill=(r,g,b))

    knob_x = progress_x + prog_fill
    knob_y = progress_y + bar_h // 2
    draw.ellipse([knob_x - 6, knob_y - 6, knob_x + 6, knob_y + 6], fill="white", outline="black", width=2)

    draw.text((progress_x, progress_y + 15), current_time, font=font_time, fill="white")
    total_bbox = draw.textbbox((0, 0), total_time, font=font_time)
    total_x = progress_x + bar_w - (total_bbox[2] - total_bbox[0])
    draw.text((total_x, progress_y + 15), total_time, font=font_time, fill="red" if total_time == "Live" else "white")

    # Controls (with repeat moved before back)
    controls_y = progress_y + 70
    num_icons = 7
    step = bar_w // (num_icons - 1)
    icon_positions = [progress_x + i*step for i in range(num_icons)]

    # shuffle
    shuffle_x = icon_positions[0]
    draw.line([(shuffle_x-12, controls_y-8), (shuffle_x+8, controls_y+12)], fill=(0,255,120), width=3)
    draw.polygon([(shuffle_x+8, controls_y+12), (shuffle_x+16, controls_y+6), (shuffle_x+2, controls_y+4)], fill=(0,255,120))
    draw.line([(shuffle_x-12, controls_y+8), (shuffle_x-2, controls_y-2)], fill=(0,255,120), width=3)

    # repeat (bright yellow)
    repeat_x = icon_positions[1]
    repeat_color = (255, 220, 50)
    draw.arc([repeat_x-14, controls_y-12, repeat_x+14, controls_y+12], start=30, end=300, fill=repeat_color, width=3)
    draw.polygon([(repeat_x+14, controls_y-2), (repeat_x+22, controls_y-6), (repeat_x+14, controls_y-10)], fill=repeat_color)

    # back
    sbx = icon_positions[2]
    draw.polygon([(sbx+10, controls_y-10), (sbx+10, controls_y+10), (sbx-12, controls_y)], fill="white")
    draw.rectangle([sbx+14, controls_y-10, sbx+18, controls_y+10], fill="white")

    # pause
    center_x = icon_positions[3]
    bar_wid, bar_height = 6, 26
    gap = 10
    draw.rectangle([center_x-gap-bar_wid, controls_y-bar_height//2, center_x-gap, controls_y+bar_height//2], fill="white")
    draw.rectangle([center_x+gap, controls_y-bar_height//2, center_x+gap+bar_wid, controls_y+bar_height//2], fill="white")

    # forward
    sfx = icon_positions[4]
    draw.polygon([(sfx-10, controls_y-10), (sfx-10, controls_y+10), (sfx+12, controls_y)], fill="white")
    draw.rectangle([sfx-18, controls_y-10, sfx-14, controls_y+10], fill="white")

    # heart
    fav_x = icon_positions[5]
    heart = [(fav_x, controls_y), (fav_x-10, controls_y-10), (fav_x-20, controls_y), (fav_x, controls_y+14),
             (fav_x+20, controls_y), (fav_x+10, controls_y-10)]
    draw.polygon(heart, fill="red")

    # earphone
    ear_x = icon_positions[6]
    draw.arc([ear_x-20, controls_y-20, ear_x+20, controls_y+20], start=200, end=-20, fill="white", width=3)
    draw.rectangle([ear_x-18, controls_y-4, ear_x-10, controls_y+12], fill="white")
    draw.rectangle([ear_x+10, controls_y-4, ear_x+18, controls_y+12], fill="white")

    bg.save(output_path)
    return output_path


async def generate_thumbnail(url: str) -> str:
    try:
        # Ensure cache directory exists
        os.makedirs("cache", exist_ok=True)
        
        filename = os.path.join("cache", f"thumbnail_{hash(url)}.jpg")
        parsed = urlparse(url)

        if parsed.scheme in ("http", "https"):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return "AdityaHalder/resource/thumbnail.png"
                    data = await resp.read()

                    with Image.open(BytesIO(data)) as img:
                        img = img.resize((1280, 720))
                        buf = BytesIO()
                        img.save(buf, format="JPEG", quality=90)
                        buf.seek(0)

                        async with aiofiles.open(filename, "wb") as f:
                            await f.write(buf.read())

        else:
            if not os.path.isfile(url):
                return "AdityaHalder/resource/thumbnail.png"

            with Image.open(url) as img:
                img = img.resize((1280, 720))
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=90)
                buf.seek(0)

                async with aiofiles.open(filename, "wb") as f:
                    await f.write(buf.read())

        return filename

    except Exception:
        return "AdityaHalder/resource/thumbnail.png"


async def make_thumbnail(image, title, channel, duration, output):
    return await create_music_thumbnail(image, title, channel, duration, output)


async def handle_telegram_media(client, message, telegram_media, video_stream=False):
    """Handle Telegram media files (audio, voice, video, documents)"""
    try:
        # Get media info
        media_title = getattr(telegram_media, 'title', None) or getattr(telegram_media, 'file_name', None) or "Telegram Audio"
        media_performer = getattr(telegram_media, 'performer', None) or "Unknown Artist"
        media_duration = getattr(telegram_media, 'duration', 0)
        
        # Create unique filename
        file_id = telegram_media.file_id
        file_extension = ".mp3"
        if hasattr(telegram_media, 'mime_type') and telegram_media.mime_type:
            if 'video' in telegram_media.mime_type:
                file_extension = ".mp4"
            elif 'audio' in telegram_media.mime_type:
                file_extension = ".mp3"
        
        # Ensure downloads directory exists
        os.makedirs("downloads", exist_ok=True)
        file_path = os.path.join("downloads", f"tg_{file_id}{file_extension}")
        
        # Download if not exists
        if not os.path.exists(file_path):
            try:
                await message.reply_to_message.download(file_name=file_path)
                
                # Wait for download completion
                max_wait = 60
                wait_count = 0
                while not os.path.exists(file_path) and wait_count < max_wait:
                    await asyncio.sleep(1)
                    wait_count += 1
                    
                if not os.path.exists(file_path):
                    return None, "❌ Download timeout."
                    
            except Exception as e:
                return None, f"❌ Failed to download media: {str(e)}"
        
        # Create media stream
        try:
            media_stream = (
                MediaStream(
                    media_path=file_path,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_parameters=AudioQuality.STUDIO,
                )
                if not video_stream
                else MediaStream(
                    media_path=file_path,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                )
            )
        except Exception as e:
            return None, f"❌ Failed to create media stream: {str(e)}"
        
        return {
            'media_stream': media_stream,
            'title': media_title,
            'artist': media_performer,
            'duration_sec': media_duration,
            'duration_formatted': format_duration(media_duration) if media_duration else "Unknown",
            'file_path': file_path,
            'thumbnail_url': "AdityaHalder/resource/thumbnail.png"  # Default thumbnail for Telegram media
        }, None
        
    except Exception as e:
        return None, f"❌ Error processing Telegram media: {str(e)}"

@bot.on_message(cdz(["play", "vplay"]) & ~filters.private)
async def start_stream_in_vc(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    chat_id = message.chat.id
    mention = (
        message.from_user.mention
        if message.from_user else
        f"[Anonymous User](https://t.me/{bot.username})"
    )

    # Check for replied Telegram media first
    replied = message.reply_to_message
    telegram_media = None
    
    if replied:
        if replied.audio:
            telegram_media = replied.audio
        elif replied.voice:
            telegram_media = replied.voice
        elif replied.video:
            telegram_media = replied.video
        elif replied.document and replied.document.mime_type:
            # Check if document is audio/video
            if replied.document.mime_type.startswith(('audio/', 'video/')):
                telegram_media = replied.document

    video_stream = True if message.command[0].startswith("v") else False

    # Handle Telegram media
    if telegram_media:
        try:
            aux = await message.reply_text("**🔄 Processing Telegram Media ✨...**")
        except Exception:
            aux = None
            
        try:
            media_info, error = await handle_telegram_media(client, message, telegram_media, video_stream)
            
            if error:
                if aux:
                    return await aux.edit(error)
                else:
                    return await message.reply_text(error)
            
            # Extract info
            media_stream = media_info['media_stream']
            title = media_info['title']
            artist = media_info['artist']
            duration_sec = media_info['duration_sec']
            duration_formatted = media_info['duration_formatted']
            file_path = media_info['file_path']
            thumbnail_url = media_info['thumbnail_url']
            
            # Try to stream
            if chat_id not in call.queue:
                try:
                    await call.start_stream(chat_id, media_stream)
                except NoActiveGroupCall:
                    if aux:
                        return await aux.edit("❌ No active voice chat found. Please join a voice chat first.")
                    else:
                        return await message.reply_text("❌ No active voice chat found. Please join a voice chat first.")
                except TelegramServerError:
                    if aux:
                        return await aux.edit("⚠️ **Telegram server error!**\nPlease try again shortly.")
                    else:
                        return await message.reply_text("⚠️ **Telegram server error!**\nPlease try again shortly.")
                except Exception as e:
                    if aux:
                        return await aux.edit(f"❌ **Failed to stream:** `{str(e)}`")
                    else:
                        return await message.reply_text(f"❌ **Failed to stream:** `{str(e)}`")

            # Generate thumbnail
            image_file = await generate_thumbnail(thumbnail_url)
            thumbnail = await make_thumbnail(
                image_file, title, artist, duration_sec, f"cache/{chat_id}_tg_{message.id}.png"
            )
                
            if aux:
                try:
                    await aux.delete()
                except:
                    pass
                
            pos = await call.add_to_queue(chat_id, media_stream, title, duration_formatted, thumbnail, mention)
            status = (
                "✅ **Started Streaming Telegram Media in VC.**"
                if pos == 0
                else f"✅ **Telegram Media Added To Queue At: #{pos}**"
            )
            
            caption = f"""{status}

**❍ Title:** {title}
**❍ Artist:** {artist}
**❍ Duration:** {duration_formatted}
**❍ Source:** Telegram Media
**❍ Requested By:** {mention}"""

            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="🗑️ Close",
                            callback_data="close",
                        ),
                    ]
                ]
            )
            
            try:
                await message.reply_photo(photo=thumbnail, caption=caption, has_spoiler=True, reply_markup=buttons)
            except Exception as e:
                await message.reply_text(f"{caption}\n\n❌ Failed to send thumbnail: {str(e)}")
            
            return
            
        except Exception as e:
            error_msg = f"❌ **Error processing Telegram media:** `{str(e)}`"
            if aux:
                try:
                    await aux.edit(error_msg)
                except:
                    await message.reply_text(error_msg)
            else:
                await message.reply_text(error_msg)
            return

    # If no Telegram media and no query provided, show help
    if len(message.command) < 2:
        return await message.reply_text(
            f"""**🥀 Give Me Some Query To Stream Audio Or Video❗...
ℹ️ Example:
≽ Audio: `/play yalgaar`
≽ Video: `/vplay yalgaar`
≽ Reply to audio/video: `/play` or `/vplay`**"""
        )

    # Handle YouTube/search queries
    query = parse_query(" ".join(message.command[1:]))
    
    try:
        aux = await message.reply_text("**🔄 Processing YouTube Query ✨...**")
    except Exception:
        aux = None

    try:
        search = VideosSearch(query, limit=1)
        result = (await search.next())["result"]

        if not result:
            if aux:
                return await aux.edit("❌ No results found.")
            else:
                return await message.reply_text("❌ No results found.")

        video = result[0]
        full_title = video["title"]
        title = full_title[:30]
        id = video["id"]
        duration = video["duration"]
        
        if not duration:
            if aux:
                return await aux.edit("❌ I can't stream live-stream right now.")
            else:
                return await message.reply_text("❌ I can't stream live-stream right now.")
                
        duration_sec = convert_to_seconds(duration)
        duration_mins = format_duration(duration_sec)
        views = video["viewCount"]["short"]
        image_path = video["thumbnails"][0]["url"].split("?")[0]
        channellink = video["channel"]["link"]
        channel = video["channel"]["name"]
        link = video["link"]
        
        # Ensure downloads directory exists
        os.makedirs("downloads", exist_ok=True)
        xyz = os.path.join("downloads", f"{id}.mp3")
        
        if not os.path.exists(xyz):
            song_data = await fetch_song(id)
            if not song_data:
                if aux:
                    return await aux.edit("❌ Failed to process query, please try again.")
                else:
                    return await message.reply_text("❌ Failed to process query, please try again.")
            
            # Check different possible fields for download URL
            song_url = None
            download_url = None
            
            # Check various possible response formats
            if "link" in song_data:
                song_url = song_data["link"]
            elif "download_url" in song_data:
                download_url = song_data["download_url"]
            elif "url" in song_data:
                download_url = song_data["url"]
            elif "audio_url" in song_data:
                download_url = song_data["audio_url"]
            elif "stream_url" in song_data:
                download_url = song_data["stream_url"]
            elif "direct_url" in song_data:
                download_url = song_data["direct_url"]
            elif isinstance(song_data, dict) and "data" in song_data:
                # If response has nested data
                data = song_data["data"]
                if isinstance(data, dict):
                    if "link" in data:
                        song_url = data["link"]
                    elif "download_url" in data:
                        download_url = data["download_url"]
                    elif "url" in data:
                        download_url = data["url"]
            
            # Handle Telegram link format
            if song_url:
                c_username, message_id = parse_tg_link(song_url)
                if not c_username or not message_id:
                    if aux:
                        return await aux.edit("❌ Invalid download link format.")
                    else:
                        return await message.reply_text("❌ Invalid download link format.")
                        
                try:
                    msg = await client.get_messages(c_username, message_id)
                    if aux:
                        await aux.edit("**⬇️ Downloading ✨...**")
                    await msg.download(file_name=xyz)
                except Exception as e:
                    if aux:
                        return await aux.edit(f"❌ Failed to download: {str(e)}")
                    else:
                        return await message.reply_text(f"❌ Failed to download: {str(e)}")
            
            # Handle direct URL download
            elif download_url:
                try:
                    if aux:
                        await aux.edit("**⬇️ Downloading ✨...**")
                    success = await download_direct_url(download_url, xyz)
                    if not success:
                        if aux:
                            return await aux.edit("❌ Failed to download from direct URL.")
                        else:
                            return await message.reply_text("❌ Failed to download from direct URL.")
                except Exception as e:
                    if aux:
                        return await aux.edit(f"❌ Failed to download: {str(e)}")
                    else:
                        return await message.reply_text(f"❌ Failed to download: {str(e)}")
            
            else:
                # No valid download URL found
                if aux:
                    return await aux.edit(f"❌ No download link found in API response. Available fields: {list(song_data.keys())}")
                else:
                    return await message.reply_text(f"❌ No download link found in API response. Available fields: {list(song_data.keys())}")
                
            # Wait for file to be completely downloaded
            max_wait = 60  # seconds
            wait_count = 0
            while not os.path.exists(xyz) and wait_count < max_wait:
                await asyncio.sleep(1)
                wait_count += 1
                
            if not os.path.exists(xyz):
                if aux:
                    return await aux.edit("❌ Download timeout.")
                else:
                    return await message.reply_text("❌ Download timeout.")

        file_path = xyz

        # Create media stream with proper error handling
        try:
            media_stream = (
                MediaStream(
                    media_path=file_path,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_parameters=AudioQuality.STUDIO,
                )
                if not video_stream
                else MediaStream(
                    media_path=file_path,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                )
            )
        except Exception as e:
            if aux:
                return await aux.edit(f"❌ **Failed to create media stream:** `{str(e)}`")
            else:
                return await message.reply_text(f"❌ **Failed to create media stream:** `{str(e)}`")
        
        # Check if chat_id is in queue, if not start streaming
        if chat_id not in call.queue:
            try:
                await call.start_stream(chat_id, media_stream)
            except NoActiveGroupCall:
                if aux:
                    return await aux.edit("❌ No active voice chat found. Please join a voice chat first.")
                else:
                    return await message.reply_text("❌ No active voice chat found. Please join a voice chat first.")
            except TelegramServerError:
                if aux:
                    return await aux.edit("⚠️ **Telegram server error!**\nPlease try again shortly.")
                else:
                    return await message.reply_text("⚠️ **Telegram server error!**\nPlease try again shortly.")
            except Exception as e:
                if aux:
                    return await aux.edit(f"❌ **Failed to stream:** `{str(e)}`")
                else:
                    return await message.reply_text(f"❌ **Failed to stream:** `{str(e)}`")

        # Generate thumbnail
        image_file = await generate_thumbnail(image_path)
        thumbnail = await make_thumbnail(
            image_file, full_title, channel, duration_sec, f"cache/{chat_id}_{id}_{message.id}.png"
        )
            
        if aux:
            try:
                await aux.delete()
            except:
                pass
            
        pos = await call.add_to_queue(chat_id, media_stream, title, duration_mins, thumbnail, mention)
        status = (
            "✅ **Started Streaming in VC.**"
            if pos == 0
            else f"✅ **Added To Queue At: #{pos}**"
        )
        
        caption = f"""{status}

**❍ Title:** [{title}...]({link})
**❍ Duration:** {duration_mins}
**❍ Requested By:** {mention}"""

        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="🗑️ Close",
                        callback_data="close",
                    ),
                ]
            ]
        )
        
        try:
            await message.reply_photo(photo=thumbnail, caption=caption, has_spoiler=True, reply_markup=buttons)
        except Exception as e:
            await message.reply_text(f"{caption}\n\n❌ Failed to send thumbnail: {str(e)}")

        # Logging
        if chat_id != console.LOG_GROUP_ID:
            try:
                chat_name = message.chat.title or "Unknown Chat"
                if message.chat.username:
                    chat_link = f"@{message.chat.username}"
                elif chat_id in console.chat_links:
                    clink = console.chat_links[chat_id]
                    chat_link = f"[Private Chat]({clink})"
                else:
                    try:
                        new_link = await client.export_chat_invite_link(chat_id)
                        console.chat_links[chat_id] = new_link
                        chat_link = f"[Private Chat]({new_link})"
                    except Exception:
                        chat_link = "N/A"
            
                if message.from_user:
                    if message.from_user.username:
                        req_user = f"@{message.from_user.username}"
                    else:
                        req_user = message.from_user.mention
                    user_id = message.from_user.id
                elif message.sender_chat:
                    if message.sender_chat.username:
                        req_user = f"@{message.sender_chat.username}"
                    else:
                        req_user = message.sender_chat.title
                    user_id = message.sender_chat.id
                else:
                    req_user = "Anonymous User"
                    user_id = "N/A"

                stream_type = "Audio" if not video_stream else "Video"

                log_message = f"""🎉 **{mention} Just Played A Song.**

📍 **Chat:** {chat_name}
💬 **Chat Link:** {chat_link}
♂️ **Chat ID:** {chat_id}
👤 **Requested By:** {req_user}
🆔 **User ID:** `{user_id}`
🔎 **Query:** {query}
🎶 **Title:** [{title}...]({link})
⏱️ **Duration:** {duration_mins}
📡 **Stream Type:** {stream_type}"""

                await bot.send_photo(console.LOG_GROUP_ID, photo=thumbnail, caption=log_message)
            except Exception:
                pass
                
    except Exception as e:
        error_msg = f"❌ **An error occurred:** `{str(e)}`"
        if aux:
            try:
                await aux.edit(error_msg)
            except:
                await message.reply_text(error_msg)
        else:
            await message.reply_text(error_msg)
