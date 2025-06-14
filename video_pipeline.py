#!/usr/bin/env python3
import asyncio
import nest_asyncio
import random # For voice selection
import os # For path operations
import uuid # For unique filenames
import subprocess
import shutil # For shutil.move
from moviepy.editor import ImageClip, VideoFileClip, VideoClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips # VideoClip, AudioFileClip already imported
from moviepy.video.fx import all as vfx # For fadein
from moviepy.video.compositing.transitions import crossfadein # For potential future use, not in immediate plan
from moviepy.audio.fx import all as afx # For audio_loop and volumex
import numpy as np
from telegram import Bot
# from telegram import InputMediaPhoto # No longer needed
import traceback # For error printing in finalize_video
import json # For saving script data
# shutil and json are not immediately needed for these core functions but were in user's example

# Kokoro model and voices file paths
KOKORO_MODEL_FILE_PATH = "/home/ubuntu/crewgooglegemini/CAPTACITY/assets/kokoro_models/kokoro-v1.0.onnx"
KOKORO_VOICES_FILE_PATH = "/home/ubuntu/crewgooglegemini/CAPTACITY/assets/kokoro_models/voices-v1.0.bin"

# Curated list of major, high-quality Kokoro voices
KOKORO_VOICE_POOL = [
    # American English - Female
    {"voice": "af_bella",   "lang": "en-us", "speed": 0.92, "label": "US Female, natural, warm"},
    {"voice": "af_nicole",  "lang": "en-us", "speed": 0.95, "label": "US Female, clear, modern"},
    {"voice": "af_sarah",   "lang": "en-us", "speed": 0.93, "label": "US Female, expressive"},
    # American English - Male
    {"voice": "am_fenrir",  "lang": "en-us", "speed": 0.85, "label": "US Male, deep, calm"},
    {"voice": "am_michael", "lang": "en-us", "speed": 0.92, "label": "US Male, neutral, clear"},
    # British English - Female
    {"voice": "bf_emma",    "lang": "en-gb", "speed": 0.85, "label": "UK Female, natural, warm"},
    # British English - Male
    {"voice": "bm_george",  "lang": "en-gb", "speed": 0.90, "label": "UK Male, neutral, classic"},
    {"voice": "bm_fable",   "lang": "en-gb", "speed": 0.92, "label": "UK Male, modern, clear"},
]

KOKORO_OUTPUT_PATH = "./output/kokoro_voiceover" # Changed to relative path

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False
    print("WARNING: kokoro_onnx library not found. Kokoro TTS functionality will be disabled.")

import soundfile as sf

def generate_audio(
    text: str,
    output_filename: str,
    voice: str = None,
    speed: float = None,
    lang: str = None
):
    """
    Generate an audio file from text using Kokoro ONNX.
    Picks a random high-quality voice and settings for faceless/narration videos.
    """
    if not KOKORO_AVAILABLE:
        # Fallback: Create a dummy file if Kokoro is not available
        print("Kokoro TTS not available. Creating a dummy audio file.")
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(f"Dummy audio for: {text}")
        print(f"Dummy audio generated and saved to {output_filename}")
        return

    # Pick a random voice/settings from the curated pool if not specified
    if not voice or not speed or not lang:
        chosen = random.choice(KOKORO_VOICE_POOL)
        voice = chosen["voice"]
        speed = chosen["speed"]
        lang = chosen["lang"]
        print(f"[Kokoro] Using random voice: {voice} ({chosen['label']}), speed={speed}, lang={lang}")
    else:
        print(f"[Kokoro] Using specified voice: {voice}, speed={speed}, lang={lang}")

    # Initialize Kokoro with the specified model and voices files
    kokoro = Kokoro(KOKORO_MODEL_FILE_PATH, KOKORO_VOICES_FILE_PATH)

    # Synthesize audio
    samples, sample_rate = kokoro.create(
        text,
        voice=voice,
        speed=speed,
        lang=lang
    )

    # Save the audio file
    os.makedirs(os.path.dirname(output_filename), exist_ok=True) # Ensure directory exists
    sf.write(output_filename, samples, sample_rate)
    print(f"Audio generated and saved to {output_filename}")

def get_audio_duration(audio_path: str) -> float:
    """
    Calculates the duration of an audio file.
    Args:
        audio_path: Path to the audio file.
    Returns:
        Duration of the audio file in seconds, or 0.0 if an error occurs.
    """
    if not os.path.exists(audio_path):
        print(f"Audio file not found: {audio_path}")
        return 0.0
    try:
        clip = AudioFileClip(audio_path)
        duration = clip.duration
        clip.close() # Release resources
        return duration
    except Exception as e:
        print(f"Error getting duration for {audio_path}: {e}")
        return 0.0

def prepare_background_sound(bgsounds_dir: str, target_duration: float, volume_factor: float = 0.1) -> AudioFileClip | None:
    """
    Selects a random background sound, loops it to target_duration, and adjusts its volume.
    Args:
        bgsounds_dir: Directory containing background audio files.
        target_duration: The desired total duration for the background sound.
        volume_factor: Factor by which to multiply the audio's volume (e.g., 0.1 for 10%).
    Returns:
        An AudioFileClip object for the processed background sound, or None if an error occurs.
    """
    if not os.path.isdir(bgsounds_dir):
        print(f"Error: Background sounds directory not found: {bgsounds_dir}")
        return None

    audio_extensions = ('.mp3', '.wav', '.aac', '.ogg', '.flac')
    available_sounds = [f for f in os.listdir(bgsounds_dir) if os.path.isfile(os.path.join(bgsounds_dir, f)) and f.lower().endswith(audio_extensions)]

    if not available_sounds:
        print(f"No suitable audio files found in {bgsounds_dir}")
        return None

    selected_sound_file = os.path.join(bgsounds_dir, random.choice(available_sounds))
    print(f"Selected background sound: {selected_sound_file}")

    try:
        bg_clip = AudioFileClip(selected_sound_file)

        if bg_clip.duration == 0:
            print(f"Error: Background sound {selected_sound_file} has zero duration.")
            bg_clip.close()
            return None

        # Loop the background audio to fit the target_duration
        # Using afx.audio_loop for simplicity if bg_clip.duration < target_duration
        if bg_clip.duration < target_duration:
            # audio_loop function expects the clip and a duration argument
            # For versions of moviepy where audio_loop might take (clip, duration=D), ensure it works.
            # A more manual way if audio_loop is problematic or for older versions:
            # num_loops = int(np.ceil(target_duration / bg_clip.duration))
            # looped_clips = [bg_clip] * num_loops
            # final_bg_clip_unadjusted = concatenate_audioclips(looped_clips).subclip(0, target_duration)
            # For now, let's try the modern afx.audio_loop if available:
            try:
                # Check if afx.audio_loop is the new style that takes clip and duration
                # This is a bit of a guess at modern moviepy syntax for audio_loop
                looped_bg_clip = afx.audio_loop(bg_clip, duration=target_duration)
            except TypeError: # Fallback for older moviepy or different audio_loop signature
                print("afx.audio_loop with explicit duration failed, trying manual loop or older syntax if applicable.")
                # Fallback to manual looping if simple audio_loop fails.
                # This part might need adjustment based on MoviePy version.
                # Simplest approach that often works is creating a long enough clip and subcliping
                if bg_clip.duration > 0:
                    num_loops_needed = int(np.ceil(target_duration / bg_clip.duration))
                    clips_to_concat = [bg_clip] * num_loops_needed
                    concatenated_audio = CompositeAudioClip(clips_to_concat) # Or concatenate_audioclips
                    looped_bg_clip = concatenated_audio.subclip(0, target_duration)
                    # concatenated_audio.close() # Not directly, subclip is a view. Rely on GC for parts.
                else: # Should have been caught by bg_clip.duration == 0
                    bg_clip.close()
                    return None

        elif bg_clip.duration > target_duration:
            looped_bg_clip = bg_clip.subclip(0, target_duration)
        else: # bg_clip.duration == target_duration
            looped_bg_clip = bg_clip

        # Adjust volume
        final_bg_sound = looped_bg_clip.fx(afx.volumex, volume_factor)

        # Don't close bg_clip here if looped_bg_clip or final_bg_sound still references its resources.
        # Moviepy's resource management can be tricky. Rely on GC for intermediate clips unless specific close methods are documented.
        # If bg_clip was used directly (not looped/subclipped), final_bg_sound would be the one to return.
        # If looped_bg_clip is a new object, bg_clip might be closable if no longer needed.
        # For safety, let's assume final_bg_sound is the primary object to manage.

        print(f"Background sound prepared. Original duration: {bg_clip.duration:.2f}s, Target duration: {target_duration:.2f}s, Volume factor: {volume_factor}")
        return final_bg_sound

    except Exception as e:
        print(f"Error processing background sound {selected_sound_file}: {e}")
        if 'bg_clip' in locals() and hasattr(bg_clip, 'close'):
            bg_clip.close()
        return None

def sanitize_filename(filename: str) -> str:
    """ Basic sanitization for filenames. Removes/replaces problematic characters. """
    # Remove characters not typically allowed or problematic in filenames
    # Keep alphanumeric, spaces, underscores, hyphens, periods.
    # Replace others with an underscore.
    sanitized = "".join(c if c.isalnum() or c in [' ', '_', '-', '.'] else '_' for c in filename)
    # Replace multiple spaces/underscores with a single one
    sanitized = "_".join(sanitized.split())
    return sanitized

def get_random_endscreen(endscreen_folder_path: str, target_resolution_str: str) -> str | None:
    """
    Picks a random endscreen .mp4 from the given folder that matches the target resolution string in its name.
    Args:
        endscreen_folder_path: Path to the folder containing endscreen videos.
        target_resolution_str: The resolution string to look for in filenames (e.g., "1280x720").
    Returns:
        Full path to a randomly selected matching endscreen video, or None if not found.
    """
    if not os.path.isdir(endscreen_folder_path):
        print(f"Warning: Endscreen folder not found: {endscreen_folder_path}")
        return None

    # Normalize the target_resolution_str for comparison (e.g. remove spaces, consistent casing if needed)
    # For now, assuming it's a simple substring match like "1280x720"

    mp4_files = []
    for f in os.listdir(endscreen_folder_path):
        if f.lower().endswith('.mp4') and target_resolution_str in f:
            mp4_files.append(f)

    if not mp4_files:
        print(f"Info: No .mp4 endscreen files found in {endscreen_folder_path} matching resolution '{target_resolution_str}'.")
        return None

    selected_file = random.choice(mp4_files)
    full_path = os.path.join(endscreen_folder_path, selected_file)
    print(f"Info: Randomly selected endscreen: {full_path}")
    return full_path

def append_endscreen_to_video(main_video_path, endscreen_video_path, final_output_path, target_width=1280, target_height=720):
    """
    Appends one endscreen video to the main video, re-encoding as needed to ensure compatibility.
    Both videos will be scaled and padded to target_width x target_height before concatenation.
    """
    if not os.path.exists(main_video_path):
        print(f"[ERROR] Main video not found: {main_video_path}")
        return False
    if not os.path.exists(endscreen_video_path):
        print(f"[ERROR] Endscreen video not found: {endscreen_video_path}")
        return False

    # Ensure target dimensions are integers for ffmpeg
    target_width = int(target_width)
    target_height = int(target_height)

    filter_complex = (
        f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"format=yuv420p[v0];"
        f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"format=yuv420p[v1];"
        f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a0];"
        f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]"
    )
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", main_video_path,
        "-i", endscreen_video_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264", "-crf", "23", "-preset", "medium", # Good default quality
        "-c:a", "aac", "-b:a", "192k", # Good default audio quality
        "-movflags", "+faststart", # Useful for web videos
        "-y", # Overwrite output file if it exists
        final_output_path
    ]
    print(f"[INFO] Running FFmpeg to append endscreen: {' '.join(ffmpeg_cmd)}")

    try:
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False) # check=False to inspect result
        if result.returncode == 0 and os.path.exists(final_output_path):
            print(f"[SUCCESS] Video with endscreen saved to: {final_output_path}")
            return True
        else:
            print(f"[ERROR] FFmpeg failed to append endscreen. Return code: {result.returncode}")
            print(f"FFmpeg stdout:\n{result.stdout}")
            print(f"FFmpeg stderr:\n{result.stderr}")
            return False
    except FileNotFoundError:
        print("[ERROR] FFmpeg command not found. Please ensure ffmpeg is installed and in your system's PATH.")
        return False
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred while running ffmpeg: {e}")
        import traceback
        traceback.print_exc()
        return False

def finalize_video(
    visual_clips: list,
    voiceover_audio_path: str,
    background_audio_clip: AudioFileClip | None,
    output_path: str, # This is the *final* desired output path
    target_resolution_str: str, # New parameter e.g., "1280x720"
    video_codec: str = 'libx264',
    # ... (other parameters remain the same)
    crf: int = 23,
    preset: str = 'medium',
    threads: int = 4
):
    """
    Concatenates visual clips, adds voiceover and optional background audio, and exports the final video.
    Args:
        visual_clips: A list of moviepy.VideoClip objects.
        voiceover_audio_path: Path to the main voiceover audio file.
        background_audio_clip: A processed moviepy.AudioFileClip for background sound (or None).
        output_path: The full path to save the final exported video.
        target_resolution_str: The target resolution string (e.g., "1280x720").
        video_codec: Codec for video encoding.
        audio_codec: Codec for audio encoding.
        crf: Constant Rate Factor for x264/x265.
        preset: Encoding preset for x264/x265.
        threads: Number of threads for ffmpeg.
    """
    if not visual_clips:
        print("Error: No visual clips provided to finalize_video.")
        return False

    print(f"Finalizing video. Output path: {output_path}")
    # Ensure output directory for final video exists (used by append_endscreen and fallback moves)
    final_output_dir = os.path.dirname(output_path)
    if not os.path.exists(final_output_dir):
        try:
            os.makedirs(final_output_dir, exist_ok=True)
            print(f"Created final output directory: {final_output_dir}")
        except OSError as e:
            print(f"Error creating final output directory {final_output_dir}: {e}")
            return False


    # Define a temporary path for the main content video
    temp_main_content_path = os.path.join(final_output_dir, "temp_main_content_" + os.path.basename(output_path))

    try:
        # Concatenate visual clips
        final_video_track = concatenate_videoclips(visual_clips, method="compose") # 'compose' is often more robust
        print(f"Visual clips concatenated. Total visual duration: {final_video_track.duration:.2f}s")

        # Load voiceover audio
        voiceover_audio = AudioFileClip(voiceover_audio_path)
        print(f"Voiceover audio loaded. Duration: {voiceover_audio.duration:.2f}s")

        # Prepare final audio track
        final_audio_track = None
        if background_audio_clip:
            print("Mixing voiceover with background sound.")
            if background_audio_clip.duration > voiceover_audio.duration:
                 background_audio_clip = background_audio_clip.subclip(0, voiceover_audio.duration)
            final_audio_track = CompositeAudioClip([voiceover_audio, background_audio_clip])
        else:
            print("Using only voiceover audio.")
            final_audio_track = voiceover_audio

        if abs(final_video_track.duration - final_audio_track.duration) > 0.1:
            print(f"Warning: Mismatch between video duration ({final_video_track.duration:.2f}s) and audio duration ({final_audio_track.duration:.2f}s). Adjusting audio to video duration.")
            final_audio_track = final_audio_track.set_duration(final_video_track.duration)

        final_video_with_audio = final_video_track.set_audio(final_audio_track)
        print("Audio track set for the main content video.")

        # Write the main content video to the temporary path
        print(f"Writing main content video to temporary path {temp_main_content_path} with CRF {crf} and preset {preset}...")
        final_video_with_audio.write_videofile(
            temp_main_content_path, # Write to temp path
            codec=video_codec,
            audiocodec=audio_codec,
            temp_audiofile_path=os.path.dirname(temp_main_content_path), # Temp audio in same dir
            remove_temp=True,
            threads=threads,
            fps=24,
            preset=preset,
            ffmpeg_params=['-crf', str(crf)]
        )
        print(f"Main content video saved temporarily to {temp_main_content_path}")

        # Attempt to append endscreen
        endscreen_folder_path = "/home/ubuntu/crewgooglegemini/manVidspro/endscreens" # User should confirm this path
        selected_endscreen_path = get_random_endscreen(endscreen_folder_path, target_resolution_str)

        if selected_endscreen_path and os.path.exists(selected_endscreen_path):
            print(f"Attempting to append endscreen: {selected_endscreen_path}")
            target_w, target_h = parse_resolution(target_resolution_str)

            success_appending = append_endscreen_to_video(
                main_video_path=temp_main_content_path,
                endscreen_video_path=selected_endscreen_path,
                final_output_path=output_path, # Actual final path
                target_width=target_w,
                target_height=target_h
            )
            if success_appending:
                print(f"Endscreen appended. Final video at: {output_path}")
                try:
                    os.remove(temp_main_content_path)
                    print(f"Removed temporary file: {temp_main_content_path}")
                except OSError as e:
                    print(f"Warning: Could not remove temporary file {temp_main_content_path}: {e}")
                return True # Overall success
            else:
                print(f"Failed to append endscreen. The main content (without endscreen) is at {temp_main_content_path}. Moving it to final path.")
                try:
                    shutil.move(temp_main_content_path, output_path)
                    print(f"Moved main content (no endscreen) to final path: {output_path}")
                    return True # Success, but without endscreen
                except Exception as e_move:
                    print(f"Error moving temp file {temp_main_content_path} to {output_path}: {e_move}")
                    return False # Failed to even provide the main content
        else:
            print("No suitable endscreen found or endscreen folder missing. Saving main content video without endscreen.")
            try:
                shutil.move(temp_main_content_path, output_path)
                print(f"Main content video (no endscreen) saved to: {output_path}")
                return True # Overall success
            except Exception as e_move:
                print(f"Error moving temp file {temp_main_content_path} to {output_path}: {e_move}")
                return False # Failed to provide the main content

    except Exception as e:
        print(f"Error during video finalization (before endscreen stage or in fallback): {e}")
        traceback.print_exc() # traceback already imported
        return False
    finally:
        # Clean up moviepy clips to release resources
        if 'final_video_track' in locals() and hasattr(final_video_track, 'close'): final_video_track.close()
        if 'voiceover_audio' in locals() and hasattr(voiceover_audio, 'close'): voiceover_audio.close()
        if background_audio_clip and hasattr(background_audio_clip, 'close'): background_audio_clip.close() # passed in, close if exists
        if 'final_audio_track' in locals() and hasattr(final_audio_track, 'close'): final_audio_track.close()
        if 'final_video_with_audio' in locals() and hasattr(final_video_with_audio, 'close'): final_video_with_audio.close()

        for clip_obj in visual_clips: # visual_clips is the original list
            if hasattr(clip_obj, 'close'):
                clip_obj.close()

        # Ensure temp_main_content_path is deleted if it exists and wasn't successfully moved/deleted
        # This is a bit tricky because if endscreen append fails, we might want to keep it if move also fails.
        # However, if an exception occurs *before* it's moved or deleted, it might be left over.
        # The current logic attempts to move it if appending fails. If that move fails, the temp file remains.
        # If an exception occurs in the main try block *before* the endscreen logic, it also remains.
        # This might be acceptable for debugging, or could be made more aggressive.
        # For now, let's leave it as is, as aggressive deletion might remove useful intermediate files on error.

async def send_telegram_message(bot_token: str, chat_id: str, video_path: str, video_title: str, script_text: str):
    """
    Sends a video and a script message to a Telegram chat.
    Args:
        bot_token: The Telegram Bot Token.
        chat_id: The ID of the target chat.
        video_path: Path to the video file to send.
        video_title: Title of the video (used in captions/messages).
        script_text: The script content to send as a message.
    """
    try:
        bot = Bot(token=bot_token)

        # Prepare script message
        # The user's original step_5f_send_to_telegram had "Title: {video_title}
        #
        # Transcript:
        # {transcript_text}"
        # We'll use script_text directly, which is the Kokoro input script.
        # For clarity, let's prepend the title to the script message.
        full_script_message = f"Title: {video_title}\n\nScript:\n{script_text}"


        # Send the video
        print(f"Sending video to Telegram: {video_path}")
        with open(video_path, 'rb') as video_file_handle:
            await bot.send_video(chat_id=chat_id, video=video_file_handle, caption=f"Video: {video_title}")
        print("Video sent to Telegram.")

        # Send the script as a text message
        print(f"Sending script to Telegram for title: {video_title}")
        # Telegram messages have a length limit (typically 4096 chars).
        # Split if too long.
        max_len = 4000 # Keep some buffer
        if len(full_script_message) > max_len:
            print(f"Script message is long ({len(full_script_message)} chars), sending in parts.")
            for i in range(0, len(full_script_message), max_len):
                await bot.send_message(chat_id=chat_id, text=full_script_message[i:i+max_len])
        else:
            await bot.send_message(chat_id=chat_id, text=full_script_message)
        print("Script message sent to Telegram.")

        print("Video and script sent successfully to Telegram.")

    except FileNotFoundError:
        print(f"Error sending to Telegram: Video file not found at {video_path}")
    except Exception as e:
        print(f"An error occurred while sending to Telegram: {e}")
        import traceback
        traceback.print_exc()

async def step_5f_send_to_telegram(video_path: str, video_title: str, script_text: str):
    """
    Prepares data and triggers sending video and script to Telegram.
    Args:
        video_path: Full path to the video file.
        video_title: Title of the video.
        script_text: The script content (Kokoro input).
    """
    # Telegram Bot Configuration (hardcoded as per user's original snippet)
    BOT_TOKEN = '6157935666:AAESXcHywVwdHZqurjz0kCcVTjzCv50gjlQ' # User provided
    CHAT_ID = '5034393732' # User provided

    print(f"Preparing to send to Telegram: Video '{video_title}'")

    if not os.path.exists(video_path):
        print(f"Error for Telegram: Video file not found at {video_path}")
        return

    # Call the async helper function
    await send_telegram_message(
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        video_path=video_path,
        video_title=video_title,
        script_text=script_text
    )

def step_5g_upload_to_google_drive(video_path: str, video_title_original: str, script_text: str):
    """
    Uploads the video and its script (as a .txt file) to Google Drive using rclone.
    Args:
        video_path: Full path to the final .mp4 video file.
        video_title_original: The original user-provided video title (for the .txt content).
        script_text: The script content (Kokoro input).
    """
    print(f"Preparing to upload to Google Drive: Video '{video_title_original}' from {video_path}")

    if not os.path.exists(video_path):
        print(f"Error for Google Drive: Video file not found at {video_path}")
        return

    # Derive base filename from video_path for the script text file
    video_file_basename = os.path.splitext(os.path.basename(video_path))[0]
    script_txt_filename = f"{video_file_basename}_script.txt"
    # Save the .txt script in the same directory as the video
    script_txt_path = os.path.join(os.path.dirname(video_path), script_txt_filename)

    print(f"Creating script text file: {script_txt_path}")
    transcript_content_for_file = (
        f"Title: {video_title_original}\n\n"
        f"Script:\n{script_text}"
    )
    try:
        with open(script_txt_path, 'w', encoding='utf-8') as tf:
            tf.write(transcript_content_for_file)
        print(f"Script text file saved: {script_txt_path}")
    except Exception as e:
        print(f"Error saving script TXT file at {script_txt_path}: {e}")
        # Decide if we should proceed with video upload only or return
        print("Proceeding with video upload only, if possible.")
        script_txt_path = None # Indicate script TXT is not available for upload

    # Upload video to Google Drive
    # Assuming rclone is configured with a remote named 'mygdrive'
    gdrive_remote_path = "mygdrive:YouTubevids/" # User provided path, ensured no leading / for remote

    print(f"Uploading video to Google Drive: {video_path} -> {gdrive_remote_path}")
    video_upload_command = [
        'rclone', 'copy', video_path, gdrive_remote_path, '--progress'
    ]
    try:
        subprocess.run(video_upload_command, check=True) # check=True will raise CalledProcessError on failure
        print(f"Uploaded video: {os.path.basename(video_path)}")
    except FileNotFoundError:
        print("[ERROR] rclone command not found. Please ensure rclone is installed and in your system's PATH.")
        return # Cannot proceed
    except subprocess.CalledProcessError as e:
        print(f"Error during rclone video upload: {e}")
        # Continue to attempt script upload if it exists
    except Exception as e:
        print(f"An unexpected error occurred during rclone video upload: {e}")

    # Upload transcript .txt file to Google Drive if it was created
    if script_txt_path and os.path.exists(script_txt_path):
        print(f"Uploading script TXT to Google Drive: {script_txt_path} -> {gdrive_remote_path}")
        transcript_upload_command = [
            'rclone', 'copy', script_txt_path, gdrive_remote_path, '--progress'
        ]
        try:
            subprocess.run(transcript_upload_command, check=True)
            print(f"Uploaded script TXT: {os.path.basename(script_txt_path)}")
        except FileNotFoundError:
            print("[ERROR] rclone command not found (should have been caught earlier).")
        except subprocess.CalledProcessError as e:
            print(f"Error during rclone script TXT upload: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during rclone script TXT upload: {e}")
    elif script_txt_path: # Path was set, but file doesn't exist (e.g. save failed)
        print(f"Script TXT file {script_txt_path} not found for upload. Skipping.")
    else: # script_txt_path was None from the start
        print("Script TXT file was not created due to an earlier error. Skipping its upload.")


    # Thumbnail logic has been removed.
    print("Google Drive upload process for video and script TXT attempted.")

def make_fullscreen_imageclip(image_path, output_size):
    #print(f"Making fullscreen: {image_path} for {output_size}")
    img_clip = ImageClip(image_path)
    w, h = output_size

    # Resize to fit height first, then width, then crop.
    # This handles images that are wider or taller than the target aspect ratio.
    if img_clip.w / img_clip.h > w / h: # Image is wider than target AR
        resized_clip = img_clip.resize(height=h)
    else: # Image is taller or same AR as target
        resized_clip = img_clip.resize(width=w)

    return resized_clip.crop(x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=w, height=h)


def fadein_effect(image_clip, duration):
    #print(f"  [EFFECT] fadein ({duration}s)")
    return image_clip.fx(vfx.fadein, duration) # .set_duration(duration) is usually not needed here as fadein returns a clip of that duration

def color_shift_effect(image_clip, duration):
    #print(f"  [EFFECT] color_shift ({duration}s)")
    def brighten(get_frame, t):
        frame = get_frame(t).astype(float)
        # Reduced intensity: smaller factor range for sin wave
        factor = 1 + 0.2 * np.sin(2 * np.pi * t / duration) # Was 0.5
        frame = np.clip(frame * factor, 0, 255)
        return frame.astype(np.uint8)
    return image_clip.fl(brighten, apply_to=['mask'] if image_clip.mask is not None else True).set_duration(duration)

def ken_burns_effect(image_clip, duration, zoom_start_factor=1.0, zoom_end_factor=1.1, pan_direction='center-in', image_size=(1280, 720)):
    #print(f"  [EFFECT] ken_burns {pan_direction} zoom {zoom_start_factor}->{zoom_end_factor} ({duration}s)")
    pan_options = {
        'top_left-to-bottom_right': ((0, 0), (1, 1)), 'bottom_right-to-top_left': ((1, 1), (0, 0)),
        'left-to-right': ((0, 0.5), (1, 0.5)), 'top-to-bottom': ((0.5, 0), (0.5, 1)),
        'center-in': ((0.5, 0.5), (0.5, 0.5)), 'right-to-left': ((1, 0.5), (0, 0.5)),
        'bottom-to-top': ((0.5, 1), (0.5, 0)), 'top_right-to-bottom_left': ((1, 0), (0, 1)),
        'bottom_left-to-top_right': ((0, 1), (1, 0)),
    }
    start_rel, end_rel = pan_options.get(pan_direction, ((0.5, 0.5), (0.5, 0.5)))
    w, h = image_size

    # Ensure image_clip is already at image_size before applying Ken Burns
    # This simplifies calculations. The source clip should be pre-resized.
    if image_clip.size[0] != w or image_clip.size[1] != h:
        # This case should ideally be handled before calling ken_burns,
        # make_fullscreen_imageclip should ensure this.
        # For safety, let's resize, though it might indicate an issue upstream.
        # print(f"Warning: Ken Burns received clip of size {image_clip.size}, expected {image_size}. Resizing.")
        image_clip = image_clip.resize((w,h))


    def crop_func(get_frame, t):
        frame_img = ImageClip(get_frame(t), ismask=image_clip.ismask) # Convert frame to ImageClip for resize

        progress = t / duration
        current_zoom = zoom_start_factor + (zoom_end_factor - zoom_start_factor) * progress

        crop_w = w / current_zoom
        crop_h = h / current_zoom

        # Ensure crop dimensions are not larger than the frame itself if zoom_factor < 1
        crop_w = min(crop_w, w)
        crop_h = min(crop_h, h)

        x_rel = start_rel[0] + (end_rel[0] - start_rel[0]) * progress
        y_rel = start_rel[1] + (end_rel[1] - start_rel[1]) * progress

        # Center of the crop area, relative to the original frame dimensions (w,h)
        x_center_crop_area = w * x_rel
        y_center_crop_area = h * y_rel

        # Calculate top-left corner of the crop area
        x1 = x_center_crop_area - crop_w / 2
        y1 = y_center_crop_area - crop_h / 2

        # Clip coordinates to be within frame boundaries
        x1 = np.clip(x1, 0, w - crop_w)
        y1 = np.clip(y1, 0, h - crop_h)

        cropped_frame = frame_img.crop(x1=x1, y1=y1, width=crop_w, height=crop_h)

        # Resize cropped area back to the target frame size (w,h)
        final_frame = cropped_frame.resize((w,h))
        return final_frame.get_frame(0) # Return as numpy array

    return VideoClip(crop_func, duration=duration, ismask=image_clip.ismask)


def shake_effect(image_clip, duration, intensity=2): # Reduced default intensity
    #print(f"  [EFFECT] shake (intensity={intensity}, {duration}s)")
    w, h = image_clip.size

    # Store original frames to avoid repeated get_frame(t) calls for the same t if possible
    # However, for shake, we need get_frame(t) as base might change if other effects are applied before shake

    def make_frame_shake(t):
        dx = random.randint(-intensity, intensity)
        dy = random.randint(-intensity, intensity)

        # Get the frame from the input clip at current time t
        base_frame = image_clip.get_frame(t)

        # Create a padded version of the base_frame
        # Pad with edge pixels to avoid black borders during shake
        padded_frame = np.pad(base_frame, ((intensity, intensity), (intensity, intensity), (0, 0)), mode='edge')

        # Calculate new top-left corner for cropping from the padded frame
        y1_padded = intensity + dy
        x1_padded = intensity + dx

        # Crop to original dimensions (w,h) from the shifted position in padded frame
        shaken_frame = padded_frame[y1_padded:y1_padded + h, x1_padded:x1_padded + w]

        return shaken_frame

    return VideoClip(make_frame_shake, duration=duration)


# Define ken_burns_variants globally or pass it to animate_photo
# Using reduced zoom for news style as per plan
NEWS_STYLE_KEN_BURNS_VARIANTS = [
    (1.0, 1.1, 'top_left-to-bottom_right'), (1.1, 1.0, 'bottom_right-to-top_left'),
    (1.0, 1.12, 'left-to-right'), (1.12, 1.0, 'top-to-bottom'),
    (1.0, 1.08, 'center-in'), (1.08, 1.0, 'right-to-left'),
    (1.0, 1.1, 'bottom_left-to_top_right'), (1.1, 1.0, 'top_right-to-bottom_left'),
]

def animate_photo(image_path, image_size, duration, ken_burns_variants=None):
    #print(f"[ANIMATION] {os.path.basename(image_path)} for {duration}s")
    if ken_burns_variants is None:
        ken_burns_variants = NEWS_STYLE_KEN_BURNS_VARIANTS

    base_clip = make_fullscreen_imageclip(image_path, image_size)

    # Apply a short fade-in to the total duration
    # Fade-in should be short, e.g., 0.5s or 1s, ensure it's not longer than total duration
    fade_in_duration = min(0.5, duration / 2)
    clip_with_fadein = fadein_effect(base_clip, fade_in_duration)

    # The rest of the effects should apply over the main part of the duration
    # If fadein is applied, the effective duration for other effects might seem shorter
    # or they might overlap. Simpler: apply fadein to the *result* of other effects.

    # Ken Burns should operate on the original base_clip's content, scaled.
    # And it dictates the main visual movement over the *entire* duration.
    kb_params = random.choice(ken_burns_variants) # (zoom_start, zoom_end, pan_direction)
    # Ken burns effect applied for the full duration on the base clip (already fullscreen)
    animated_clip = ken_burns_effect(base_clip, duration, kb_params[0], kb_params[1], kb_params[2], image_size)

    if random.random() < 0.3: # Reduced probability for news style
        animated_clip = color_shift_effect(animated_clip, duration) # Apply to the already Ken Burns'd clip

    if random.random() < 0.2: # Reduced probability
        animated_clip = shake_effect(animated_clip, duration, intensity=random.randint(1,2)) # Apply to the result so far

    # Apply fade-in to the fully animated clip
    final_clip_with_fade = fadein_effect(animated_clip, fade_in_duration)

    return final_clip_with_fade.set_duration(duration)

def discover_and_prepare_media(media_dir: str, target_resolution_str: str):
    """
    Discovers image and video files in a directory and prepares a list of them.
    Args:
        media_dir: Path to the directory containing media files.
        target_resolution_str: The target resolution string (e.g., "1280x720"), currently unused in this function
                               but planned for future use or context.
    Returns:
        A list of dictionaries, each representing a media file.
        Each dict contains: 'path', 'type' ('image' or 'video'),
        and 'duration' (for videos, in seconds).
    """
    print(f"Discovering media in: {media_dir}")
    media_list = []
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp') # Added webp
    video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm') # Added mkv, flv, webm

    if not os.path.isdir(media_dir):
        print(f"Error: Media directory not found: {media_dir}")
        return media_list

    for item in os.listdir(media_dir):
        item_path = os.path.join(media_dir, item)
        if os.path.isfile(item_path):
            ext = os.path.splitext(item)[1].lower()
            if ext in image_extensions:
                media_list.append({'path': item_path, 'type': 'image', 'duration': 0}) # duration 0 for images
                # print(f"Found image: {item_path}")
            elif ext in video_extensions:
                try:
                    # This block might fail if moviepy cannot be imported in the environment
                    clip = VideoFileClip(item_path)
                    duration = clip.duration
                    clip.close()
                    media_list.append({'path': item_path, 'type': 'video', 'duration': duration})
                    # print(f"Found video: {item_path}, Duration: {duration:.2f}s")
                except Exception as e:
                    # If moviepy fails (e.g. ModuleNotFoundError or error reading file),
                    # still add the video but with unknown duration (or skip it).
                    # For now, let's add it with duration -1 to indicate it's a video but duration is unknown.
                    print(f"Could not get duration for video {item_path} (may be corrupted or unsupported): {e}")
                    media_list.append({'path': item_path, 'type': 'video', 'duration': -1.0})


    if not media_list:
        print(f"No media files found in {media_dir}")
    else:
        print(f"Discovered {len(media_list)} media items.")
    return media_list

def parse_resolution(resolution_str: str) -> tuple[int, int]:
    """ Parses a 'WxH' string into (width, height) tuple. """
    try:
        w, h = map(int, resolution_str.split('x'))
        return w, h
    except ValueError:
        print(f"Error parsing resolution string: {resolution_str}. Using default 1280x720.")
        return 1280, 720 # Default fallback

def create_visual_sequence(media_list: list, target_resolution_str: str, total_target_duration: float) -> list:
    """
    Creates a sequence of video clips (animated images or processed videos)
    to match the total_target_duration.
    """
    print(f"Creating visual sequence for target duration: {total_target_duration:.2f}s, resolution: {target_resolution_str}")
    if not media_list:
        print("Error: No media items provided to create_visual_sequence.")
        return []
    if total_target_duration <= 0:
        print("Error: Total target duration must be positive.")
        return []

    output_clips = []
    current_duration = 0.0
    target_size = parse_resolution(target_resolution_str) # e.g., (1280, 720)
    target_w, target_h = target_size

    media_pool = list(media_list) # Create a mutable copy for random selection

    while current_duration < total_target_duration:
        if not media_pool:
            print("Warning: Media pool exhausted before reaching target duration. Repeating last clip if available.")
            if not output_clips:
                print("Error: Media pool exhausted and no clips generated. Cannot meet target duration.")
                return [] # Cannot proceed

            # Simple strategy: repeat the last clip to fill remaining duration
            last_clip_to_repeat = output_clips[-1]
            if last_clip_to_repeat.duration > 0.1: # Ensure last clip has meaningful duration
                remaining_needed = total_target_duration - current_duration
                num_repeats = int(np.ceil(remaining_needed / last_clip_to_repeat.duration))
                for i in range(num_repeats):
                    # If it's the very last iteration of repeat and it would overshoot, subclip it
                    if i == num_repeats -1 and current_duration + last_clip_to_repeat.duration > total_target_duration:
                        needed_duration = total_target_duration - current_duration
                        if needed_duration > 0.1 : # only add if significant
                             output_clips.append(last_clip_to_repeat.subclip(0,needed_duration))
                             current_duration += needed_duration
                        break
                    output_clips.append(last_clip_to_repeat)
                    current_duration += last_clip_to_repeat.duration
                    if current_duration >= total_target_duration:
                        break
            else: # Last clip too short or invalid, cannot fill
                print("Warning: Last available clip is too short to repeat for filling duration.")
            break # Exit the main while loop, as we cannot pick new media

        selected_media_item = random.choice(media_pool) # Pick a random item
        media_path = selected_media_item['path']
        media_type = selected_media_item['type']

        print(f"Selected media: {os.path.basename(media_path)} (type: {media_type})")

        clip_to_add = None
        actual_clip_duration = 0

        if media_type == 'image':
            img_duration = random.uniform(4.0, 8.0)
            # Adjust duration if it would overshoot significantly when this is the last clip
            if current_duration + img_duration > total_target_duration + 2.0: # Allow slight overshoot for last image
                img_duration = max(0.5, total_target_duration - current_duration) # Ensure at least 0.5s

            if img_duration < 0.5 : # If remaining time too short
                 print(f"Remaining duration {img_duration:.2f}s too short for new image, stopping.")
                 break

            print(f"  Animating image {os.path.basename(media_path)} for {img_duration:.2f}s")
            try:
                clip_to_add = animate_photo(media_path, target_size, img_duration)
                actual_clip_duration = clip_to_add.duration # Should be img_duration
            except Exception as e:
                print(f"Error animating image {media_path}: {e}")
                # Remove problematic media from the pool to avoid re-selection in this run
                media_pool = [item for item in media_pool if item['path'] != media_path]
                continue

        elif media_type == 'video':
            original_video_duration = selected_media_item.get('duration', 0)
            if original_video_duration < 0.1: # Video with unknown, zero, or too short duration
                print(f"Skipping video {media_path} due to invalid or too short duration: {original_video_duration:.2f}s")
                media_pool = [item for item in media_pool if item['path'] != media_path]
                continue

            print(f"  Processing video {os.path.basename(media_path)}, original duration: {original_video_duration:.2f}s")
            try:
                video_clip_obj = VideoFileClip(media_path, audio=False)
                orig_w, orig_h = video_clip_obj.size

                processed_video_clip = None
                if (orig_w, orig_h) == target_size:
                    print(f"    Video {os.path.basename(media_path)} is already target size.")
                    processed_video_clip = video_clip_obj
                elif target_w > target_h and orig_w < orig_h : # Target is landscape, video is portrait
                     print(f"    Video {os.path.basename(media_path)} is portrait {orig_w}x{orig_h} for target {target_w}x{target_h}. Scaling to fit height and padding.")
                     # Scale to fit height
                     scaled_clip = video_clip_obj.resize(height=target_h)
                     # Pad to target width, centering
                     processed_video_clip = CompositeVideoClip([scaled_clip.set_position('center')],
                                                               size=target_size,
                                                               bg_color=(0,0,0)).set_duration(scaled_clip.duration)
                else: # General case: scale and pad
                    print(f"    Resizing video {os.path.basename(media_path)} from {orig_w}x{orig_h} to {target_w}x{target_h} (scale & pad).")
                    # Scale to fit within target_size (decrease)
                    scaled_clip = video_clip_obj.resize(lambda t_ignored: min(target_w/orig_w, target_h/orig_h))
                    processed_video_clip = CompositeVideoClip([scaled_clip.set_position('center')],
                                                              size=target_size,
                                                              bg_color=(0,0,0)).set_duration(scaled_clip.duration)

                clip_to_add = processed_video_clip
                actual_clip_duration = clip_to_add.duration
                # video_clip_obj.close() # Close original clip resource - important! moviepy docs suggest this happens when the object is garbage collected, but explicit can be safer.
                                        # However, some operations might need it open. Let's rely on GC for now unless issues arise.

            except Exception as e:
                print(f"Error processing video {media_path}: {e}")
                media_pool = [item for item in media_pool if item['path'] != media_path]
                continue

        if clip_to_add and actual_clip_duration > 0.1:
            output_clips.append(clip_to_add)
            current_duration += actual_clip_duration
            print(f"    Added {os.path.basename(media_path)}. Current total duration: {current_duration:.2f}s")
        elif clip_to_add : # actual_clip_duration <= 0.1
             print(f"    Generated clip for {os.path.basename(media_path)} was too short ({actual_clip_duration:.2f}s). Discarding.")

    # Final trim if current_duration slightly overshoots total_target_duration
    if current_duration > total_target_duration and output_clips:
        overshoot = current_duration - total_target_duration
        last_clip = output_clips[-1]
        if last_clip.duration - overshoot > 0.1: # Only trim if it leaves a meaningful clip
            print(f"Final trim: Trimming last clip from {last_clip.duration:.2f}s by {overshoot:.2f}s.")
            output_clips[-1] = last_clip.subclip(0, last_clip.duration - overshoot)
        # else: last clip is too short to trim meaningfully, or would become zero. Consider popping it if strict duration is needed.
        # For now, a slight overshoot is accepted if trimming makes last clip too small.

    final_actual_duration = sum(c.duration for c in output_clips)
    print(f"Visual sequence generation complete. {len(output_clips)} clips. Final actual duration: {final_actual_duration:.2f}s")
    return output_clips

async def process_with_kokoro_tts(script: str):
    print("\n--- Preparing for Kokoro TTS ---")

    # Ensure the base output directory exists
    os.makedirs(KOKORO_OUTPUT_PATH, exist_ok=True)

    # Generate a unique filename for the audio output
    # Using only the first 100 chars of script for filename, and replacing non-alphanum
    sane_script_prefix = "".join(c if c.isalnum() else "_" for c in script[:100])
    unique_id = str(uuid.uuid4().hex[:8])
    output_filename = os.path.join(KOKORO_OUTPUT_PATH, f"voiceover_{sane_script_prefix}_{unique_id}.wav") # .wav is common for sf

    print(f"Target audio file: {output_filename}")

    # Run the synchronous generate_audio function in a thread pool executor
    # to avoid blocking the asyncio event loop.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,  # Uses the default ThreadPoolExecutor
        generate_audio, # The synchronous function to call
        script,         # Arguments for generate_audio
        output_filename
    )

    if not KOKORO_AVAILABLE:
        print(f"Kokoro TTS is not available. A dummy file was created at: {output_filename}")
    else:
        print(f"--- Kokoro TTS processing complete. Audio saved to: {output_filename} ---")

    return output_filename

async def main():
    # --- Pre-flight Checks ---
    print("Performing pre-flight checks...")

    # 1. Check allMedia directory
    all_media_dir = "/home/ubuntu/crewgooglegemini/manVidspro/allMedia" # User specified path
    if not os.path.exists(all_media_dir):
        print(f"Error: The media directory {all_media_dir} does not exist.")
        print("Please create this directory and add your image/video files to it.")
        return # Stop execution

    if not os.listdir(all_media_dir): # Check if the directory is empty
        print(f"Error: The media directory {all_media_dir} is empty.")
        print("Please add image/video files to this directory to proceed.")
        return # Stop execution

    print(f"Media directory {all_media_dir} check passed. Found content.")

    # --- Initialize variables for voiceover/script/title handling ---
    tts_output_path = None
    video_title = None # Will be populated either from voiceover filename/JSON or user prompt
    script = ""        # Will be populated either from JSON or user prompt
    use_existing_voiceover = False

    # 2. Check for existing voiceover
    kokoro_voiceover_dir = "/home/ubuntu/crewgooglegemini/manVidspro/kokoroVoiceover" # User specified
    script_json_path = "/home/ubuntu/crewgooglegemini/manVidspro/videoscript.json" # User specified

    print(f"Checking for existing voiceover in: {kokoro_voiceover_dir}")
    potential_voiceovers = []
    if os.path.exists(kokoro_voiceover_dir) and os.path.isdir(kokoro_voiceover_dir):
        audio_extensions = ('.wav', '.mp3', '.aac', '.ogg', '.flac') # Common audio types
        for item in os.listdir(kokoro_voiceover_dir):
            item_path = os.path.join(kokoro_voiceover_dir, item)
            if os.path.isfile(item_path) and item.lower().endswith(audio_extensions):
                potential_voiceovers.append(item_path)

    if potential_voiceovers:
        if len(potential_voiceovers) > 1:
            print(f"Multiple voiceover files found. Selecting the most recent.")
            # Sort by modification time (newest first)
            potential_voiceovers.sort(key=lambda f: os.path.getmtime(f), reverse=True)

        tts_output_path = potential_voiceovers[0] # Most recent or the only one
        use_existing_voiceover = True
        print(f"Using existing voiceover: {tts_output_path}")

        # Attempt to parse video_title from filename (e.g., "My Title_voiceover.wav" or "My Title.wav")
        base_vo_filename = os.path.splitext(os.path.basename(tts_output_path))[0]
        if base_vo_filename.lower().endswith("_voiceover"):
            video_title_from_vo = base_vo_filename[:-10].strip() # Remove "_voiceover"
        else:
            video_title_from_vo = base_vo_filename.strip()

        if video_title_from_vo:
            print(f"Attempting to use title from voiceover filename: '{video_title_from_vo}'")
            # Further check: Load script_json_path to see if this title exists
            if os.path.exists(script_json_path):
                try:
                    with open(script_json_path, 'r', encoding='utf-8') as f_json:
                        all_scripts_data = json.load(f_json) # Assuming it's a dict of dicts or list of dicts

                    # Assuming structure is {"title1": {"script": "..."}} or a list [{"title":"..", "script":"..."}]
                    # For simplicity, let's assume it's a dictionary where keys are titles.
                    # If it's a list, this logic needs adjustment.
                    # User mentioned "video title and script in one block" for videoscript.json
                    # Let's assume it's a single JSON object: {"title": "the_title", "script": "the_script"}
                    # This was from step 1 of this plan. So, the JSON path contains ONE title/script.
                    # This means we should check if video_title_from_vo matches the title in that JSON.

                    # Re-evaluating: script_json_path as per step 1 was:
                    # script_data_to_save = {"title": video_title, "script": script}
                    # This implies script_json_path stores info for ONE video, the *last* one.
                    # This is not a database of all scripts.
                    # So, if an old voiceover is found, its title might not be in this specific JSON file
                    # unless it was the very last video processed.

                    # New refined logic:
                    # The JSON file /home/ubuntu/crewgooglegemini/manVidspro/videoscript.json
                    # is expected to contain {"title": "actual_title", "script": "actual_script"}
                    # that corresponds to the LATEST run that saved this file.
                    # If an old voiceover is picked, its title might not match the one in this JSON.

                    # Simpler approach for now: If title is parsed from voiceover, use it.
                    # If script for this title can be found (e.g. from a text file named video_title_from_vo_script.txt
                    # in the voiceover dir, or if videoscript.json was a DICTIONARY of scripts keyed by title),
                    # then use it. Otherwise, script will be empty or prompted.
                    # For now, let's assume script_json_path might contain the relevant script if titles match.

                    script_data = None # Initialize script_data
                    if os.path.exists(script_json_path): # Check if script_json_path exists before opening
                        with open(script_json_path, 'r', encoding='utf-8') as f_json:
                            try:
                                script_data_from_file = json.load(f_json)
                                # Check if the title from file matches the parsed title
                                if isinstance(script_data_from_file, dict) and script_data_from_file.get('title') == video_title_from_vo:
                                    script = script_data_from_file.get('script', "")
                                    video_title = video_title_from_vo # Confirm title
                                    print(f"Found matching script for title '{video_title}' in {script_json_path}")
                                else:
                                    print(f"Title '{video_title_from_vo}' from voiceover filename does not match title in {script_json_path}. Script not loaded from JSON.")
                                    video_title = video_title_from_vo # Still use title from filename
                                    # Script remains empty, will be prompted or handled later
                            except json.JSONDecodeError:
                                print(f"Warning: Could not decode JSON from {script_json_path}. Script not loaded.")
                    else: # script_json_path does not exist
                        print(f"Warning: Script JSON file {script_json_path} not found. Script not loaded.")
                        video_title = video_title_from_vo # Still use title from filename

                except Exception as e_json:
                    print(f"Error reading script JSON {script_json_path}: {e_json}")
                    video_title = video_title_from_vo # Fallback to title from filename
                    # Script remains empty
            else: # video_title_from_vo was empty
                print("Could not parse a valid title from the voiceover filename.")
                # video_title will be prompted later
                # script will be prompted later (if new VO) or remain empty (if existing VO and no script found)
        else: # No voiceover files found
            print("No existing voiceover files found.")
            use_existing_voiceover = False
            # video_title and script will be prompted as per normal flow for new video
    else: # kokoro_voiceover_dir does not exist or is not a directory
        print(f"Voiceover directory {kokoro_voiceover_dir} not found or is not a directory.")
        use_existing_voiceover = False
        # video_title and script will be prompted as per normal flow for new video

    # --- Get Video Resolution (this part can remain largely unchanged, happens for both paths) ---
    print("\n--- Video Configuration ---")
    while True:
        # This print statement was removed in a previous subtask run. Let's ensure it's here or similar.
        # print("Starting the video production pipeline...") # This was an old print, let's use a more contextual one.
        print("\nChoose video resolution:")
        print("1: 720x1280 (Portrait)")
        print("2: 1280x720 (Landscape)")
        resolution_choice = input("Enter your choice (1 or 2): ")
        if resolution_choice == '1':
            resolution = "720x1280"
            break
        elif resolution_choice == '2':
            resolution = "1280x720"
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    print(f"Selected resolution: {resolution}")


    # --- Conditional Handling for Title, Script, and TTS ---
    if use_existing_voiceover:
        print(f"Proceeding with existing voiceover: {tts_output_path}")

        if not video_title: # If title wasn't parsed from filename or is empty
            print("Could not determine video title from existing voiceover filename or JSON.")
            video_title = input("Please enter the video title: ").strip()
            while not video_title: # Ensure a title is provided
                print("Video title cannot be empty.")
                video_title = input("Please enter the video title: ").strip()
            print(f"Video title set to: {video_title}")
        else:
            print(f"Using video title: '{video_title}' (from voiceover filename/JSON).")


        if not script: # If script wasn't loaded from JSON or is empty for the given title
            print(f"No script was found or loaded for title '{video_title}' from {script_json_path}.")
            # Option: Prompt for a script/description, or use a placeholder.
            # Using a placeholder as decided.
            script = f"Script for video titled '{video_title}' (associated with existing voiceover: {os.path.basename(tts_output_path)})."
            print(f"Using placeholder script: '{script[:100]}...'")
        else:
            print(f"Using script found for title '{video_title}'.")

    else: # No existing voiceover to use - normal new video flow
        print("No existing usable voiceover found. Proceeding with new script input.")

        # Get video title (original placement for new video flow)
        # video_title should be None or empty here if use_existing_voiceover is False
        if video_title:
             print(f"Warning: video_title ('{video_title}') was unexpectedly pre-set in new video flow. Will re-prompt.")

        print("\nWhat is the title for this video?")
        video_title = input("Enter video title: ").strip()
        while not video_title: # Ensure a title is provided
            print("Video title cannot be empty.")
            video_title = input("Enter video title: ").strip()
        print(f"Video title set to: {video_title}")

        # Get video script
        print("\nPaste your video script below. Press Ctrl+D (or Ctrl+Z on Windows) when done.")
        script_lines = []
        while True:
            try:
                line = input()
                script_lines.append(line)
            except EOFError:
                break
        script = "\n".join(script_lines)

        if not script.strip():
            print("Script input was empty. Exiting.")
            return

        print(f"\n--- Video Script Received (length: {len(script)}) ---")
        # print(script) # Optionally print full script for verification
        print("--- End of Script ---")

        # Process script with Kokoro TTS
        print("\nProcessing script with Kokoro TTS...")
        # tts_output_path variable will be (re)assigned here
        tts_output_path_or_error = await process_with_kokoro_tts(script)
        if isinstance(tts_output_path_or_error, str) and os.path.exists(tts_output_path_or_error):
            tts_output_path = tts_output_path_or_error # Assign to the main tts_output_path
            print(f"Kokoro TTS processing complete. Output: {tts_output_path}")
        else:
            print(f"Kokoro TTS processing failed or returned an invalid path: '{tts_output_path_or_error}'")
            print("Cannot proceed without a valid voiceover file.")
            return

    # --- Ensure tts_output_path is valid before proceeding ---
    if not tts_output_path or not os.path.exists(tts_output_path):
        print(f"Error: Voiceover path '{tts_output_path}' is not valid or file does not exist. Cannot proceed.")
        return

    # --- Save/Update script and title to JSON (happens for both new and existing voiceover cases) ---
    # script_json_path should be defined from a previous step (Startup Check: Existing Voiceover Processing)
    script_data_to_save = {"title": video_title, "script": script}
    try:
        # Ensure directory for json exists (it was already created in step 1 of this plan, but good to have exist_ok=True)
        os.makedirs(os.path.dirname(script_json_path), exist_ok=True)
        with open(script_json_path, 'w', encoding='utf-8') as f_json:
            json.dump(script_data_to_save, f_json, indent=4)
        print(f"Saved/Updated script and title to JSON: {script_json_path}")
    except Exception as e:
        print(f"Error saving/updating script to JSON at {script_json_path}: {e}")

    # --- The rest of the pipeline follows ---
    # (e.g., get_audio_duration(tts_output_path), discover_and_prepare_media, etc.)
    voiceover_duration = get_audio_duration(tts_output_path)
    if voiceover_duration <= 0:
            print("Error: Could not determine voiceover duration or voiceover is empty. Cannot proceed with video generation.")
            return # Or handle error appropriately

        print(f"Voiceover duration: {voiceover_duration:.2f} seconds")

        media_dir = "/home/ubuntu/crewgooglegemini/manVidspro/allMedia" # As specified by user

        # Discover and prepare media
        # The 'resolution' variable should be available from the user's earlier choice.
        available_media = discover_and_prepare_media(media_dir, resolution)

        if not available_media:
            print(f"No media found in {media_dir}. Cannot create video sequence.")
            return

        # Create the visual sequence of clips
        print(f"Starting to create visual sequence for resolution: {resolution} and duration: {voiceover_duration:.2f}s")
        visual_clips = create_visual_sequence(available_media, resolution, voiceover_duration)

        if not visual_clips:
            print("Failed to create the visual sequence of clips.")
            return

        actual_visual_duration = sum(c.duration for c in visual_clips)
        print(f"\n--- Visual Sequence Generation Complete ---")
        print(f"Number of clips generated: {len(visual_clips)}")
        print(f"Total duration of visual clips: {actual_visual_duration:.2f}s")
        print(f"Target voiceover duration was: {voiceover_duration:.2f}s")

        # --- Final Video Assembly ---
        bgsounds_dir = "/home/ubuntu/crewgooglegemini/manVidspro/bgsounds" # User specified path
        final_video_dir = "/home/ubuntu/crewgooglegemini/manVidspro/Finalvideo" # User specified path

        # Ensure output directory for final video exists
        try:
            os.makedirs(final_video_dir, exist_ok=True)
        except OSError as e:
            print(f"Error creating output directory {final_video_dir}: {e}")
            # Depending on severity, might want to return or raise
            return

        # Prepare background sound
        # voiceover_duration should be available from earlier in main()
        background_audio = None # Initialize to None
        if os.path.exists(bgsounds_dir) and os.listdir(bgsounds_dir): # Check if dir exists and is not empty
            background_audio = prepare_background_sound(bgsounds_dir, voiceover_duration, volume_factor=0.08) # e.g., 8% volume
        else:
            print(f"Background sounds directory {bgsounds_dir} not found or is empty. Proceeding without background sound.")

        # Sanitize video title for filename
        # video_title variable should be available from earlier in main()
        safe_video_filename = sanitize_filename(video_title) + ".mp4"
        output_video_path = os.path.join(final_video_dir, safe_video_filename)

        print(f"\nStarting final video assembly...")
        print(f"Voiceover audio: {tts_output_path}")
        if background_audio:
            print(f"Background audio will be used.")
        else:
            print(f"No background audio will be used.")
        print(f"Output video will be saved to: {output_video_path}")

        success = finalize_video(
            visual_clips=visual_clips,
            voiceover_audio_path=tts_output_path,
            background_audio_clip=background_audio,
            output_path=output_video_path,
            target_resolution_str=resolution # Pass the user's chosen resolution string
            # Using default quality settings in finalize_video, can customize here if needed
        )

        if success:
            print(f"\n--- Video Generation Successful ---")
            print(f"Final video saved to: {output_video_path}")

            # Save the Kokoro input script as a .txt file in the same directory as the video
            # output_video_path should be defined and hold the full path to the .mp4 video
            # video_title should hold the original user-provided title

            # We need a sanitized version of video_title for the TXT filename,
            # but the JSON and Google Drive upload might use the original or a differently sanitized one.
            # Let's use the same sanitized name as the video for consistency for the TXT file.
            # The output_video_path already uses a sanitized name from sanitize_filename(video_title) + ".mp4"

            base_filename = os.path.splitext(os.path.basename(output_video_path))[0] # Extracts filename without .mp4
            script_txt_filename = f"{base_filename}_script.txt"
            script_txt_path = os.path.join(os.path.dirname(output_video_path), script_txt_filename)

            try:
                with open(script_txt_path, 'w', encoding='utf-8') as f_txt:
                    f_txt.write(f"Title: {video_title}\n\nScript:\n{script}")
                print(f"Saved Kokoro input script to TXT: {script_txt_path}")
            except Exception as e:
                print(f"Error saving script to TXT at {script_txt_path}: {e}")

            # Now, proceed with uploads
            print(f"\n--- Starting Upload Processes ---")

            # Ensure 'script' (Kokoro input) and 'video_title' (original) are available here.
            # 'output_video_path' is the full path to the generated .mp4 file.

            # Call Telegram upload function (async)
            # It's important that step_5f_send_to_telegram is defined as an async function
            try:
                print("\nAttempting to send to Telegram...")
                await step_5f_send_to_telegram(
                    video_path=output_video_path,
                    video_title=video_title, # Original title for display
                    script_text=script      # Kokoro input script
                )
                print("Telegram sending process completed.")
            except Exception as e_telegram:
                print(f"An error occurred during Telegram sending: {e_telegram}")

            # Call Google Drive upload function (synchronous)
            try:
                print("\nAttempting to upload to Google Drive...")
                step_5g_upload_to_google_drive(
                    video_path=output_video_path,
                    video_title_original=video_title, # Original title for .txt content
                    script_text=script               # Kokoro input script
                )
                print("Google Drive upload process completed.")
            except Exception as e_gdrive:
                print(f"An error occurred during Google Drive upload: {e_gdrive}")

            print(f"\n--- All Processes Attempted ---")

        else:
            print(f"\n--- Video Generation Failed ---")
            print("Uploads will be skipped. Please check the logs for errors during finalization.")

        # Cleanup for visual_clips is now handled within finalize_video's finally block.
        # Cleanup for tts_output_path (if it's a temp file) or background_audio could be done here if needed,
        # but background_audio (AudioFileClip) is also closed in finalize_video.
        # If tts_output_path is a dummy file from Kokoro fallback, it might need cleanup.
        # For now, assuming tts_output_path is managed elsewhere or persists.

    # Placeholder for future function calls using the resolution and script
    print("\nNext steps will process the video based on the provided script and resolution.")

if __name__ == "__main__":
    nest_asyncio.apply()  # Allow nested event loops
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"Error: {e}")
