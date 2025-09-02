from pyrogram import filters
from pytgcalls.types import MediaStream
from pytgcalls.types import AudioQuality, VideoQuality

from .. import bot, call, cdz
from ..modules.helpers import AdminsOnlyWrapper


def seconds_to_hhmmss(seconds):
    """Convert seconds to HH:MM:SS format"""
    if seconds < 3600:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes:02}:{sec:02}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{hours:d}:{minutes:02}:{sec:02}"


def extract_argument(text, enforce_digit=False):
    """Extract argument from command text"""
    try:
        args = text.split(None, 1)[1] if len(text.split()) > 1 else None
        if enforce_digit and args:
            # Check if argument is a valid number
            int(args)
        return args
    except (IndexError, ValueError):
        return None


@bot.on_message(cdz("seek") & ~filters.private)
@AdminsOnlyWrapper
async def seek_vc_stream(client, message):
    """Seek to a specific position in the currently playing track."""
    chat_id = message.chat.id
    
    # Check if there's something playing
    queued = call.queue.get(chat_id)
    if not queued:
        return await message.reply_text("❌ **Nothing is currently playing.**")
    
    # Check if chat is in active chats
    if chat_id not in call.active_chats:
        return await message.reply_text("❌ **No active stream found.**")
    
    # Extract seek time from command
    args = extract_argument(message.text, enforce_digit=True)
    if not args:
        return await message.reply_text(
            "ℹ️ **Usage:** `/seek [seconds]`\n"
            "**Example:** `/seek 30` to jump 30 seconds forward"
        )
    
    try:
        seek_time = int(args)
    except ValueError:
        return await message.reply_text("⚠️ **Please enter a valid number of seconds.**")
    
    if seek_time < 0:
        return await message.reply_text("⚠️ **Please enter a positive number of seconds.**")
    
    if seek_time < 10:
        return await message.reply_text("⚠️ **Minimum seek time is 10 seconds.**")
    
    try:
        # Get current playing item
        current_item = queued[0] if queued else None
        if not current_item:
            return await message.reply_text("❌ **No track information found.**")
        
        # Get the current media stream info
        current_stream = current_item.get("media_stream")
        title = current_item.get("title", "Unknown")
        
        if not current_stream or not hasattr(current_stream, 'media_path'):
            return await message.reply_text("❌ **Cannot seek this type of stream.**")
        
        file_path = current_stream.media_path
        
        # Get current position and calculate new seek position
        current_pos = await call.get_current_position(chat_id)
        new_position = current_pos + seek_time
        
        try:
            # Check if it's video stream by looking at video_parameters
            is_video = hasattr(current_stream, 'video_parameters') and current_stream.video_parameters is not None
            
            # Create new media stream with seek offset
            if is_video:
                new_stream = MediaStream(
                    media_path=file_path,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                    ffmpeg_parameters=f"-ss {new_position}"  # Seek to new position
                )
            else:
                new_stream = MediaStream(
                    media_path=file_path,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_parameters=AudioQuality.STUDIO,
                    ffmpeg_parameters=f"-ss {new_position}"  # Seek to new position
                )
            
            # Update the current item with new stream
            current_item["media_stream"] = new_stream
            
            # Restart stream with new position
            await call.start_stream(chat_id, new_stream)
            
            # Update position tracking
            await call.update_position(chat_id, new_position)
            
            seek_time_formatted = seconds_to_hhmmss(new_position)
            mention = message.from_user.mention if message.from_user else "User"
            
            await message.reply_text(
                f"⏩ **Seeked {seek_time} seconds forward by {mention}**\n"
                f"🎵 **Track:** {title}\n"
                f"📍 **Current Position:** {seek_time_formatted}\n"
                f"🎬 **Stream Type:** {'Video' if is_video else 'Audio'}"
            )
            
        except Exception as e:
            return await message.reply_text(f"❌ **Failed to seek stream:** `{str(e)}`")
            
    except Exception as e:
        return await message.reply_text(f"❌ **Error occurred while seeking:** `{str(e)}`")


@bot.on_message(cdz(["seekback", "backward"]) & ~filters.private)
@AdminsOnlyWrapper
async def seek_backward_vc_stream(client, message):
    """Seek backward in the currently playing track."""
    chat_id = message.chat.id
    
    # Check if there's something playing
    queued = call.queue.get(chat_id)
    if not queued:
        return await message.reply_text("❌ **Nothing is currently playing.**")
    
    # Check if chat is in active chats
    if chat_id not in call.active_chats:
        return await message.reply_text("❌ **No active stream found.**")
    
    # Extract seek time from command
    args = extract_argument(message.text, enforce_digit=True)
    if not args:
        return await message.reply_text(
            "ℹ️ **Usage:** `/seekback [seconds]`\n"
            "**Example:** `/seekback 30` to go 30 seconds backward"
        )
    
    try:
        seek_time = int(args)
    except ValueError:
        return await message.reply_text("⚠️ **Please enter a valid number of seconds.**")
    
    if seek_time < 0:
        return await message.reply_text("⚠️ **Please enter a positive number of seconds.**")
    
    if seek_time < 10:
        return await message.reply_text("⚠️ **Minimum seek time is 10 seconds.**")
    
    try:
        # Get current playing item
        current_item = queued[0] if queued else None
        if not current_item:
            return await message.reply_text("❌ **No track information found.**")
        
        # Get the current media stream info
        current_stream = current_item.get("media_stream")
        title = current_item.get("title", "Unknown")
        
        if not current_stream or not hasattr(current_stream, 'media_path'):
            return await message.reply_text("❌ **Cannot seek this type of stream.**")
        
        file_path = current_stream.media_path
        
        # Get current position and calculate new seek position
        current_pos = await call.get_current_position(chat_id)
        new_position = max(0, current_pos - seek_time)  # Don't go below 0
        
        try:
            # Check if it's video stream
            is_video = hasattr(current_stream, 'video_parameters') and current_stream.video_parameters is not None
            
            # Create new media stream with backward seek offset
            if is_video:
                new_stream = MediaStream(
                    media_path=file_path,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                    ffmpeg_parameters=f"-ss {new_position}" if new_position > 0 else ""
                )
            else:
                new_stream = MediaStream(
                    media_path=file_path,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_parameters=AudioQuality.STUDIO,
                    ffmpeg_parameters=f"-ss {new_position}" if new_position > 0 else ""
                )
            
            # Update the current item with new stream
            current_item["media_stream"] = new_stream
            
            # Restart stream with new position
            await call.start_stream(chat_id, new_stream)
            
            # Update position tracking
            await call.update_position(chat_id, new_position)
            
            seek_time_formatted = seconds_to_hhmmss(new_position)
            mention = message.from_user.mention if message.from_user else "User"
            
            if new_position == 0:
                await message.reply_text(
                    f"⏪ **Restarted track by {mention}**\n"
                    f"🎵 **Track:** {title}\n"
                    f"📍 **Position:** 00:00\n"
                    f"🎬 **Stream Type:** {'Video' if is_video else 'Audio'}"
                )
            else:
                await message.reply_text(
                    f"⏪ **Seeked {seek_time} seconds backward by {mention}**\n"
                    f"🎵 **Track:** {title}\n"
                    f"📍 **Current Position:** {seek_time_formatted}\n"
                    f"🎬 **Stream Type:** {'Video' if is_video else 'Audio'}"
                )
            
        except Exception as e:
            return await message.reply_text(f"❌ **Failed to seek backward:** `{str(e)}`")
            
    except Exception as e:
        return await message.reply_text(f"❌ **Error occurred while seeking:** `{str(e)}`")


@bot.on_message(cdz(["seekto", "goto"]) & ~filters.private)
@AdminsOnlyWrapper
async def seek_to_position(client, message):
    """Seek to a specific position in the track (absolute positioning)."""
    chat_id = message.chat.id
    
    # Check if there's something playing
    queued = call.queue.get(chat_id)
    if not queued:
        return await message.reply_text("❌ **Nothing is currently playing.**")
    
    # Check if chat is in active chats
    if chat_id not in call.active_chats:
        return await message.reply_text("❌ **No active stream found.**")
    
    # Extract time from command (supports MM:SS or seconds)
    args = extract_argument(message.text)
    if not args:
        return await message.reply_text(
            "ℹ️ **Usage:** `/seekto [time]`\n"
            "**Examples:**\n"
            "• `/seekto 120` (2 minutes)\n"
            "• `/seekto 2:30` (2 minutes 30 seconds)"
        )
    
    try:
        # Parse time format
        if ":" in args:
            # MM:SS format
            time_parts = args.split(":")
            if len(time_parts) == 2:
                minutes, seconds = map(int, time_parts)
                seek_position = minutes * 60 + seconds
            elif len(time_parts) == 3:
                # HH:MM:SS format
                hours, minutes, seconds = map(int, time_parts)
                seek_position = hours * 3600 + minutes * 60 + seconds
            else:
                raise ValueError("Invalid time format")
        else:
            # Seconds format
            seek_position = int(args)
    except ValueError:
        return await message.reply_text("⚠️ **Please enter a valid time format (seconds or MM:SS).**")
    
    if seek_position < 0:
        return await message.reply_text("⚠️ **Please enter a positive time value.**")
    
    try:
        # Get current playing item
        current_item = queued[0] if queued else None
        if not current_item:
            return await message.reply_text("❌ **No track information found.**")
        
        # Get the current media stream info
        current_stream = current_item.get("media_stream")
        title = current_item.get("title", "Unknown")
        
        if not current_stream or not hasattr(current_stream, 'media_path'):
            return await message.reply_text("❌ **Cannot seek this type of stream.**")
        
        file_path = current_stream.media_path
        
        try:
            # Check if it's video stream
            is_video = hasattr(current_stream, 'video_parameters') and current_stream.video_parameters is not None
            
            # Create new media stream with absolute seek position
            if is_video:
                new_stream = MediaStream(
                    media_path=file_path,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                    ffmpeg_parameters=f"-ss {seek_position}"
                )
            else:
                new_stream = MediaStream(
                    media_path=file_path,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_parameters=AudioQuality.STUDIO,
                    ffmpeg_parameters=f"-ss {seek_position}"
                )
            
            # Update the current item with new stream
            current_item["media_stream"] = new_stream
            
            # Restart stream with new position
            await call.start_stream(chat_id, new_stream)
            
            # Update position tracking
            await call.update_position(chat_id, seek_position)
            
            seek_time_formatted = seconds_to_hhmmss(seek_position)
            mention = message.from_user.mention if message.from_user else "User"
            
            await message.reply_text(
                f"🎯 **Jumped to position by {mention}**\n"
                f"🎵 **Track:** {title}\n"
                f"📍 **Position:** {seek_time_formatted}\n"
                f"🎬 **Stream Type:** {'Video' if is_video else 'Audio'}"
            )
            
        except Exception as e:
            return await message.reply_text(f"❌ **Failed to seek to position:** `{str(e)}`")
            
    except Exception as e:
        return await message.reply_text(f"❌ **Error occurred while seeking:** `{str(e)}`")


@bot.on_message(cdz(["position", "pos", "time"]) & ~filters.private)
async def get_current_position(client, message):
    """Get current playback position of the track."""
    chat_id = message.chat.id
    
    # Check if there's something playing
    queued = call.queue.get(chat_id)
    if not queued:
        return await message.reply_text("❌ **Nothing is currently playing.**")
    
    # Check if chat is in active chats
    if chat_id not in call.active_chats:
        return await message.reply_text("❌ **No active stream found.**")
    
    try:
        # Get current playing item
        current_item = queued[0] if queued else None
        if not current_item:
            return await message.reply_text("❌ **No track information found.**")
        
        title = current_item.get("title", "Unknown")
        duration = current_item.get("duration", "Unknown")
        current_stream = current_item.get("media_stream")
        
        # Get current position
        current_pos = await call.get_current_position(chat_id)
        current_pos_formatted = seconds_to_hhmmss(current_pos)
        
        # Check if it's video stream
        is_video = (hasattr(current_stream, 'video_parameters') and 
                   current_stream.video_parameters is not None) if current_stream else False
        
        await message.reply_text(
            f"🎵 **Currently Playing:**\n"
            f"**Title:** {title}\n"
            f"**Duration:** {duration}\n"
            f"**Current Position:** {current_pos_formatted}\n"
            f"**Stream Type:** {'Video' if is_video else 'Audio'}"
        )
        
    except Exception as e:
        return await message.reply_text(f"❌ **Error getting position:** `{str(e)}`")
