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
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from unidecode import unidecode
import shutil
import requests
from IPython.display import Audio, display, FileLink
import uuid
import shutil
import urllib.request
import urllib.parse
import websocket
from termcolor import colored
from moviepy.editor import *
from tqdm.notebook import tqdm
import shutil
from moviepy.editor import ImageClip, vfx
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.video.fx.resize import resize  # Import resize for zooming
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, CompositeAudioClip
import subprocess
import tempfile
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
import time
import requests
import asyncio
import ast
import ssl
import re
import json
import random
from telegram import Bot
import torch
import cv2
import websocket
import uuid
import urllib.request
import urllib.parse
from PIL import Image
import io
import edge_tts
from termcolor import colored
import datetime
import os
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException
from jsonschema import validate, ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
from groq import Groq
import yt_dlp  # For downloading YouTube videos
import moviepy.editor as mp
from datetime import datetime
#from ultralytics import YOLO
from urllib.parse import urlparse, unquote
import numpy as np
from moviepy.video.fx.all import fadeout
from moviepy.audio.fx.all import audio_fadeout
from pexelsapi.pexels import Pexels
from pydantic import ValidationError
from jsonschema import validate
import wave
import glob
from IPython.display import clear_output
from pydub import AudioSegment
import time
import json

if 'FFMPEG_BIN' not in os.environ: # Check if already set by user's environment
    try:
        # Attempt to find ffmpeg using shutil.which, if not found, use common path
        # import shutil # shutil is already imported above
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            os.environ['FFMPEG_BIN'] = ffmpeg_path
            print(f"FFMPEG_BIN set to: {ffmpeg_path} (found in PATH)")
        else:
            # Fallback to common path if not found, user might need to adjust this
            default_ffmpeg_path = '/usr/bin/ffmpeg'
            if os.path.exists(default_ffmpeg_path):
                os.environ['FFMPEG_BIN'] = default_ffmpeg_path
                print(f"FFMPEG_BIN set to: {default_ffmpeg_path} (default path)")
            else:
                print(f"Warning: ffmpeg not found at {default_ffmpeg_path} or in PATH. Whisper may fail if it needs a specific ffmpeg binary.")
    except ImportError:
        # Fallback if shutil is not available for some reason (should not happen given earlier import)
        default_ffmpeg_path = '/usr/bin/ffmpeg'
        if os.path.exists(default_ffmpeg_path):
             os.environ['FFMPEG_BIN'] = default_ffmpeg_path
             print(f"FFMPEG_BIN set to: {default_ffmpeg_path} (default path, shutil not found)")
        else:
             print(f"Warning: ffmpeg not found at {default_ffmpeg_path}. Whisper may fail if it needs a specific ffmpeg binary.")

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    VideoClip, # Assuming VideoClip might be used directly or by other functions
    TextClip,
    ImageClip,
    VideoFileClip
)
# It's good practice to also import other moviepy classes if they are used,
# e.g. VideoFileClip, etc. but based on finalize_video, these are the direct ones.

# Global Caches
lines_cache = {}
shadow_cache = {}
text_cache = {}

# Class Definitions
class Character:
    def __init__(self, text, color=None):
        self.text = text
        self.color = color

    def set_color(self, color):
        self.color = color

class Word:
    def __init__(self, word, color=None):
        self.word = word
        self.color = color
        self.characters = []

        for char_text in word: # Iterate over characters in the word string
            self.characters.append(Character(char_text, color))

    def set_color(self, color):
        self.color = color
        for char_obj in self.characters: # Iterate over Character objects
            char_obj.set_color(color)

class TextClipEx(TextClip): # TextClip needs to be imported from moviepy.editor
    def __init__(self, **kwargs):
        # Ensure 'txt' is in kwargs before calling super, or handle its absence
        if 'txt' not in kwargs:
            # Provide a default or raise an error, depending on expected usage
            # For now, let's assume TextClip can handle it or it's always provided
            kwargs['txt'] = " " # Provide a default space to avoid issues with TextClip init
                                # if text is truly dynamic and set later.
                                # Or, raise ValueError("txt parameter is required for TextClipEx")

        # MoviePy's TextClip might not handle empty string well for size calculation initially.
        # If kwargs['txt'] is empty, some internal font processing might fail.
        # A single space is often safer if the text is meant to be set dynamically later.
        if not kwargs['txt']: # If txt is an empty string
            kwargs['txt'] = " "


        super().__init__(**kwargs)
        # self.text should be set by TextClip's __init__ if txt is passed.
        # If we want to ensure it, we can do:
        if hasattr(self, 'txt'):
             self.text = self.txt
        elif 'txt' in kwargs : # Should have been covered by super()
             self.text = kwargs["txt"]
        # else: self.text might not be set if 'txt' wasn't in kwargs and super() didn't set it as self.txt

# Helper Function Definitions
def moviepy_to_pillow(clip) -> Image.Image: # Added Image.Image type hint
    # Create a temporary file for the frame
    # Use delete=True and ensure image is loaded before context manager exits
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmpfile:
        temp_filename = tmpfile.name
        clip.save_frame(temp_filename, t=0) # Save first frame at t=0
        image = Image.open(temp_filename)
        image.load() # Ensure image data is loaded into memory before tempfile is deleted
        return image
    # No finally needed if delete=True is used and works correctly with image.load()

def get_font_path(font: str) -> str: # Using the version from user's initial caption code dump
    # Check if Font Exists Directly (e.g., an absolute path was provided):
    if os.path.exists(font) and (font.endswith(".ttf") or font.endswith(".otf")):
        return font

    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() and os.path.isabs(__file__) else os.path.abspath('.')

    # Search in Assets Folder relative to script:
    font_path_candidate = os.path.join(script_dir, "assets", "fonts", font)
    if os.path.exists(font_path_candidate):
        return font_path_candidate

    # Fallback to user-specified absolute path for fonts if relative not found
    # This path should ideally be configurable, not hardcoded.
    abs_font_path_base = "/home/ubuntu/crewgooglegemini/CAPTACITY/captacity/assets/fonts"
    font_path_candidate_abs = os.path.join(abs_font_path_base, font)
    if os.path.exists(font_path_candidate_abs):
        return font_path_candidate_abs

    # If still not found, try common system font paths (very basic example)
    # This part is highly OS-dependent and might not be reliable or desirable.
    # For example, on Linux:
    # system_font_paths = ["/usr/share/fonts/truetype/", "/usr/local/share/fonts/"]
    # for path_base in system_font_paths:
    #     if os.path.exists(os.path.join(path_base, font)):
    #         return os.path.join(path_base, font)

    # If truly not found after checks
    raise FileNotFoundError(f"Font '{font}' not found. Checked direct path, ./assets/fonts/, and {abs_font_path_base}. Please ensure the font is available.")

# Forward declaration for create_text_ex, as get_text_size_ex uses it.
# Actual definition will be provided further down.
_create_text_ex_placeholder = lambda *args, **kwargs: None # Placeholder returns None

def get_text_size(text, fontsize, font, stroke_width): # Assumes font is a name/relative path
    actual_font_path = get_font_path(font)
    # create_text internally calls TextClipEx, which uses the font path.
    text_clip = create_text(text, fontsize=fontsize, color="white", font=actual_font_path, stroke_width=stroke_width)
    if hasattr(text_clip, 'size'):
        return text_clip.size
    return (0,0) # Fallback if size isn't available

def get_text_size_ex(text, font, fontsize, stroke_width): # Assumes font is name/relative path
    actual_font_path = get_font_path(font)
    # This should call the actual create_text_ex that will be defined below.
    # The placeholder mechanism is used to define it before full definition.
    # Note: The placeholder returns None, so this might not be fully functional until create_text_ex is defined.
    # However, the subtask implies this structure.
    # For actual sizing, create_text_ex must return a clip with a .size attribute.
    text_clip = create_text_ex(text, fontsize=fontsize, color="white", font=actual_font_path, stroke_width=stroke_width)
    if hasattr(text_clip, 'size'):
        return text_clip.size
    return (0,0) # Fallback if size isn't available


def blur_text_clip(text_clip, blur_radius: int) -> VideoClip:
    pil_img = moviepy_to_pillow(text_clip)
    # Padding needs to be enough for the blur not to be clipped at edges
    # offset = int(blur_radius * 0.6) # This offset seems arbitrary, usually padding is just blur_radius
    padding = blur_radius * 2 # More generous padding

    pil_img_padded = Image.new("RGBA",
                               (pil_img.width + padding * 2, pil_img.height + padding * 2),
                               (0,0,0,0)) # Transparent background
    pil_img_padded.paste(pil_img, (padding, padding))

    pil_img_filtered = pil_img_padded.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    final_blurred_clip = ImageClip(np.array(pil_img_filtered))
    if hasattr(text_clip, 'duration') and text_clip.duration is not None:
        final_blurred_clip = final_blurred_clip.set_duration(text_clip.duration)
    # Ensure the position is maintained or reset if necessary.
    # By default, new ImageClip is at (0,0). If text_clip had a specific position, it's lost here.
    # This function is more about creating a blurred *version* of the content, not preserving layout.
    return final_blurred_clip


def create_text(
    text: str, fontsize: int, color: str, font: str, # font here is expected to be a resolved path by get_font_path
    bg_color: str = 'transparent', blur_radius: int = 0, opacity: float = 1.0,
    stroke_color: str | None = None, stroke_width: int = 1, kerning: float = 0.0,
) -> VideoClip:
    global text_cache
    # Font path is used in hash because different paths could point to same font name but be different files
    arg_hash = hash((text, fontsize, color, font, bg_color, blur_radius, opacity, stroke_color, stroke_width, kerning))
    if arg_hash in text_cache:
        cached_clip = text_cache[arg_hash]
        # MoviePy clips are stateful when used in compositions. Return a copy for safety.
        return cached_clip.copy() if hasattr(cached_clip, 'copy') else cached_clip


    text_clip = TextClipEx(txt=text, fontsize=fontsize, color=color, bg_color=bg_color, font=font,
                           stroke_color=stroke_color, stroke_width=stroke_width, kerning=kerning)

    if opacity < 1.0: # Apply opacity if not fully opaque
        text_clip = text_clip.set_opacity(opacity)

    if blur_radius > 0:
        text_clip = blur_text_clip(text_clip, blur_radius) # blur_text_clip returns a new clip

    text_cache[arg_hash] = text_clip # Store the potentially modified clip (e.g., blurred)
    return text_clip.copy() if hasattr(text_clip, 'copy') else text_clip


def create_text_chars(
    text: list[Word] | list[Character] | str, fontsize, color, font, # font is name/relative path
    bg_color = 'transparent', blur_radius: int = 0, opacity = 1,
    stroke_color = None, stroke_width = 1, add_space_between_words = True,
) -> list[VideoClip]: # list of VideoClip, not TextClip, as create_text can return blurred clips
    actual_font_path = get_font_path(font) # Resolve font path once
    clips = []
    processed_text_list = []

    if isinstance(text, str):
        words = text.split(' ') # Split by space to preserve multiple spaces if needed (though TextClip might collapse them)
        processed_text_list = [Word(word, color) for word in words]
    elif isinstance(text, list) and all(isinstance(item, str) for item in text): # List of strings
        processed_text_list = [Word(item, color) for item in text]
    elif isinstance(text, list) and all(isinstance(item, (Word, Character)) for item in text): # List of Word/Character objects
        processed_text_list = text
    else:
        print(f"Warning: Unexpected type or structure in create_text_chars input: {type(text)}. Returning empty list.")
        return []


    for i, item in enumerate(processed_text_list):
        if isinstance(item, Word):
            for char_obj in item.characters:
                char_color_to_use = char_obj.color if char_obj.color else color
                # Pass actual_font_path to create_text
                clip = create_text(char_obj.text, fontsize, char_color_to_use, actual_font_path, bg_color,
                                   blur_radius, opacity, stroke_color, stroke_width)
                clips.append(clip)
            if add_space_between_words and i < len(processed_text_list) - 1:
                # Create a space clip. Spaces also need the font path.
                space_clip = create_text(" ", fontsize, color, actual_font_path, bg_color, blur_radius,
                                         opacity, stroke_color, stroke_width)
                clips.append(space_clip)
        elif isinstance(item, Character):
            char_color_to_use = item.color if item.color else color
            clip = create_text(item.text, fontsize, char_color_to_use, actual_font_path, bg_color,
                               blur_radius, opacity, stroke_color, stroke_width)
            clips.append(clip)
    return clips

def create_composite_text(text_clips: list[VideoClip], font: str, font_size: int) -> CompositeVideoClip: # font is name/relative
    if not text_clips: # Handle empty list of clips
        # Return a minimal, empty, transparent clip
        return CompositeVideoClip([ImageClip(np.zeros((1,1,4), dtype=np.uint8)).set_duration(0.1)], size=(1,1))

    actual_font_path = get_font_path(font)
    try:
        pil_font = ImageFont.truetype(actual_font_path, font_size)
    except IOError:
        print(f"Error: Could not load font {actual_font_path} for metrics. Using default estimations.")
        # Fallback to a very basic estimation if font loading fails for metrics
        pil_font = ImageFont.load_default()


    positioned_clips = []
    current_x_offset = 0
    max_height = 0

    for clip_idx, clip_obj in enumerate(text_clips):
        # clip_obj is already a MoviePy clip (TextClip or ImageClip if blurred)
        clip_w, clip_h = clip_obj.size

        positioned_clips.append(clip_obj.set_position((current_x_offset, 0)))
        current_x_offset += clip_w

        if clip_h > max_height:
            max_height = clip_h

    final_size = (current_x_offset, max_height if max_height > 0 else 1) # Ensure height is at least 1
    return CompositeVideoClip(positioned_clips, size=final_size)


def str_to_charlist(text: str) -> list[Character]:
    return [Character(char) for char in text]

# Actual definition for create_text_ex, replacing the placeholder
def create_text_ex(
    text: list[Word] | list[Character] | str, fontsize: int, color: str, font: str, # font is name/relative
    bg_color='transparent', blur_radius: int = 0, opacity = 1,
    stroke_color = None, stroke_width = 1, kerning = 0, # kerning currently mostly unhandled beyond TextClip
) -> CompositeVideoClip:
    # actual_font_path is resolved inside create_text_chars and create_composite_text
    text_char_clips = create_text_chars(text, fontsize, color, font, bg_color, blur_radius,
                                        opacity, stroke_color, stroke_width)
    if not text_char_clips:
        # Return a dummy transparent clip of minimal size if no chars
        dummy_img = np.zeros((1, 1, 4), dtype=np.uint8) # RGBA, transparent
        return CompositeVideoClip([ImageClip(dummy_img).set_duration(0.1)], size=(1, 1))

    # Pass original font name (font) and fontsize to create_composite_text
    # create_composite_text will resolve font path again for its own metrics if needed.
    return create_composite_text(text_char_clips, font, fontsize)

def calculate_lines(text, font, font_size, stroke_width, frame_width): # font is name/relative
    global lines_cache
    arg_hash = hash((text, font, font_size, stroke_width, frame_width))
    if arg_hash in lines_cache:
        return lines_cache[arg_hash]

    lines = []
    line_to_draw_info = None # Stores {"text": ..., "height": ...} for the line being built
    current_line_text_str = "" # The actual string content of the line being built
    words = text.split(' ') # Split by space
    word_index = 0
    total_calculated_height = 0

    actual_font_path = get_font_path(font) # Resolve font path once for measurements

    while word_index < len(words):
        word = words[word_index]

        # Handle empty words that might result from multiple spaces, e.g. "hello  world" -> "hello", "", "world"
        if not word and word_index < len(words) -1: # if it's an empty word and not the last one
            if current_line_text_str: # if there's text on the line, add a space
                 current_line_text_str += " "
            word_index += 1
            continue # process next word (which would be the actual word after multiple spaces)

        # Test line with the new word
        test_line_str = current_line_text_str + word if not current_line_text_str else current_line_text_str + " " + word

        # Use get_text_size which uses create_text (and thus TextClipEx) for measuring
        text_w, line_h = get_text_size(test_line_str.strip(), font_size, actual_font_path, stroke_width)

        if text_w <= frame_width: # Word fits or starts a new line that fits
            current_line_text_str = test_line_str
            line_to_draw_info = {"text": current_line_text_str.strip(), "height": line_h if line_h > 0 else font_size} # Use font_size as min height
            word_index += 1
        else: # Word makes the current line too long
            if line_to_draw_info: # If there was already text on the line (current_line_text_str was not empty)
                lines.append(line_to_draw_info)
                total_calculated_height += line_to_draw_info["height"]
                current_line_text_str = "" # Reset for the new line (that starts with the current word)
                line_to_draw_info = None
                # The current word that didn't fit will be processed in the next iteration, starting a new line.
            else: # Single word is too long for the frame_width
                print(f"NOTICE: Word '{word}' (length {text_w}) is too long for the frame width {frame_width} at font size {font_size}.")
                # Add the long word as its own line.
                # Re-measure just the word itself.
                single_w, single_h = get_text_size(word, font_size, actual_font_path, stroke_width)
                lines.append({"text": word, "height": single_h if single_h > 0 else font_size})
                total_calculated_height += (single_h if single_h > 0 else font_size)
                current_line_text_str = ""
                line_to_draw_info = None
                word_index += 1 # Move to the next word

    if line_to_draw_info: # Append any remaining line
        lines.append(line_to_draw_info)
        total_calculated_height += line_to_draw_info["height"]

    data = {"lines": lines, "height": total_calculated_height}
    lines_cache[arg_hash] = data
    return data

def fits_frame(line_count, font, font_size, stroke_width, frame_width): # font is name/relative
    def fit_function(text_to_check: str) -> bool:
        # Ensure text_to_check is not empty or just whitespace, as that might lead to 0 lines.
        if not text_to_check.strip():
            return True # Empty text technically "fits" as it takes no lines.

        calculated_line_data = calculate_lines(text_to_check, font, font_size, stroke_width, frame_width)
        return len(calculated_line_data["lines"]) <= line_count
    return fit_function

def make_safe_filename(name: str) -> str:
    # Replace any character that is not alphanumeric, a hyphen, or underscore with an underscore
    # Also remove leading/trailing underscores/hyphens that might result
    # And collapse multiple underscores/hyphens
    name = re.sub(r'[^A-Za-z0-9-_.]', '_', name) # Allow period for extension
    name = re.sub(r'__+', '_', name) # Collapse multiple underscores
    name = re.sub(r'--+', '-', name) # Collapse multiple hyphens
    name = name.strip('-_') # Remove leading/trailing junk
    if not name: # Handle case where name becomes empty
        return "untitled"
    return name

def load_video_segments(transcript_filename: str) -> list: # transcript_filename is the path to _transcription.txt
    """
    Loads transcription segments from a file generated by the transcription step.
    The file is expected to have lines in the format: start_time end_time text words_json_array
    """
    if not os.path.exists(transcript_filename):
        print(f"[ERROR] Transcript file for segments not found: {transcript_filename}")
        return []

    segments = []
    print(f"Loading segments from: {transcript_filename}")
    try:
        with open(transcript_filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue # Skip empty lines

                # Regex to capture start, end, text, and the JSON words array
                # This regex is more robust to varied spacing and text content.
                match = re.match(r'(\d+\.\d+)\s+(\d+\.\d+)\s+(.*?)\s+(\[.*\])$', line)

                if match:
                    start_time_str, end_time_str, text_str, words_json_str = match.groups()
                    try:
                        words_list = ast.literal_eval(words_json_str)
                        if not isinstance(words_list, list):
                            print(f"[WARN] Line {line_num+1}: Parsed 'words' is not a list in {transcript_filename}. Segment: '{text_str}'. Got: {type(words_list)}")
                            words_list = [] # Fallback

                        segments.append({
                            'start': float(start_time_str),
                            'end': float(end_time_str),
                            'text': text_str.strip(), # Ensure text is stripped
                            'words': words_list,
                        })
                    except (ValueError, SyntaxError) as e_eval:
                        print(f"[WARN] Line {line_num+1}: Error parsing words JSON or float times in {transcript_filename}. Segment: '{text_str}'. Error: {e_eval}")
                    except Exception as e_seg:
                         print(f"[WARN] Line {line_num+1}: Unexpected error processing segment in {transcript_filename}. Segment: '{text_str}'. Error: {e_seg}")
                else:
                    print(f"[WARN] Line {line_num+1}: Could not parse segment from line in {transcript_filename}: '{line[:100]}...'")
    except Exception as e_file:
        print(f"[ERROR] Failed to read or process transcript segment file {transcript_filename}: {e_file}")
        return [] # Return empty if file processing fails fundamentally

    print(f"Loaded {len(segments)} segments from {transcript_filename}.")
    return segments

def create_shadow(text: str, font_size: int, font: str, # font is name/relative path
                  blur_radius: float, opacity: float=1.0) -> VideoClip: # Added return type hint
    global shadow_cache # Ensure shadow_cache is initialized globally: shadow_cache = {}

    # Resolve font path
    actual_font_path = get_font_path(font)

    arg_hash = hash((text, font_size, actual_font_path, blur_radius, opacity)) # Use resolved font path in hash

    if arg_hash in shadow_cache:
        return shadow_cache[arg_hash].copy()

    # Create the text clip that will be the shadow (typically black)
    # create_text_ex is suitable here as it handles complex text if needed, though for shadow, simple text is often enough.
    # Using create_text for simplicity for shadow, as it doesn't need word-level objects usually.
    # If create_text_ex is preferred, ensure 'text' is compatible (e.g. simple string for shadow)

    # Option 1: Using create_text (simpler for a solid shadow)
    # shadow_base = create_text(text, font_size, "black", actual_font_path, opacity=opacity)

    # Option 2: Using create_text_ex (if complex text objects are ever passed for shadowing, though unlikely for simple text)
    # For a simple string 'text', create_text_ex will internally wrap it.
    shadow_base = create_text_ex(text, font_size, "black", actual_font_path, opacity=opacity)


    # Apply blur
    # Ensure blur_radius for blur_text_clip is an int and positive if > 0
    blur_amount = 0
    if blur_radius > 0:
        blur_amount = int(font_size * blur_radius) # As per user's original add_captions
        if blur_amount <= 0: # Ensure blur is at least 1 if blur_radius > 0 and font_size is small
            blur_amount = 1

    if blur_amount > 0 :
        blurred_shadow = blur_text_clip(shadow_base, blur_amount)
    else:
        blurred_shadow = shadow_base # No blur if radius is zero or calculated amount is zero

    shadow_cache[arg_hash] = blurred_shadow.copy()
    return blurred_shadow

def add_captions(
    video_file, # Path to the input video
    output_file = "with_captions.mp4", # Output path for video with captions

    font = "Bangers-Regular.ttf", # Font name or path
    font_size = 100,
    font_color = "yellow",

    stroke_width = 3,
    stroke_color = "black",

    highlight_current_word = True,
    word_highlight_color = "red",

    line_count = 2, # Max lines for captions
    fit_function = None, # Custom fit function, if None, uses default fits_frame

    padding = 30, # Padding around text box within video frame
    position = ("center", "bottom"), # ('center', 'center') was in user code, changed to bottom as common for captions
                                 # This 'position' is for the text block, not individual lines.

    shadow_strength = 1.0, # Opacity of shadow
    shadow_blur = 0.1, # Blur radius factor for shadow

    print_info = False, # Verbose logging

    initial_prompt = None, # Passed to segment_parser if it uses it. Not used by our current segment_parser.
    segments = None, # Expects list of segments from Whisper (e.g. from transcribe_locally)
):
    _start_time = time.time()

    try:
        actual_font_path = get_font_path(font)
        if print_info: print(f"Using font: {actual_font_path}")
    except FileNotFoundError as e:
        print(f"[ERROR] Font '{font}' not found: {e}. Cannot add captions.")
        return None

    if print_info:
        print("Generating video elements for captions...")

    if not os.path.exists(video_file):
        print(f"[ERROR] Input video for captions not found: {video_file}")
        return None

    try:
        video = VideoFileClip(video_file)
    except Exception as e:
        print(f"[ERROR] Could not open video file {video_file} with MoviePy: {e}")
        return None

    text_bbox_width = video.w - padding * 2
    clips = [video]

    if fit_function is None:
        # actual_font_path is used here for fits_frame, which calls calculate_lines, which calls get_text_size,
        # which calls create_text, which needs a resolved font path.
        fit_function = fits_frame(line_count, actual_font_path, font_size, stroke_width, text_bbox_width)

    # Segments passed to add_captions are assumed to be raw Whisper segments
    if segments is None:
        print("[WARN] No segments provided to add_captions. Output will have no captions.")
        parsed_captions = []
    else:
        parsed_captions = parse_transcription_segments(
            segments=segments,
            fit_function=fit_function,
            allow_partial_sentences=True # Allow partial sentences for more granular word highlighting
        )

    if not parsed_captions and print_info:
        print("[INFO] No caption segments to render after parsing.")

    # Main loop for creating caption clips for each segment
    for caption_segment_data in parsed_captions:
        # caption_segment_data is a dict: {'start': float, 'end': float, 'text': str, 'words': list[dict]}

        # Determine the text to display for the entire duration of this caption_segment_data
        full_segment_text = caption_segment_data["text"]

        # Calculate how this full_segment_text breaks into lines
        line_layout_info = calculate_lines(full_segment_text, actual_font_path, font_size, stroke_width, text_bbox_width)

        # Vertical positioning for the block of lines
        base_y_position = video.h - padding # Start from bottom of video minus padding
        current_block_height = line_layout_info["height"]

        # Adjust y_offset to make 'bottom' refer to the bottom of the text block
        # Position such that the bottom of the text block is at base_y_position
        text_y_start_offset = base_y_position - current_block_height
        # User had an additional offset (font_size // 2), let's test without first, then re-add if needed.
        # text_y_start_offset -= (font_size // 4) # Small additional lift from bottom

        current_line_y = text_y_start_offset

        for line_idx, line_info in enumerate(line_layout_info["lines"]):
            # line_info is {'text': str, 'height': float}
            line_text_to_render = line_info["text"]

            # If NOT highlighting words, or if no words in segment, create one clip for the whole line_text_to_render
            if not highlight_current_word or not caption_segment_data.get("words"):
                # Shadow for the whole line
                if shadow_strength > 0:
                    shadow_cl = create_shadow(line_text_to_render, font_size, actual_font_path, shadow_blur, shadow_strength)
                    shadow_cl = shadow_cl.set_start(caption_segment_data["start"]).set_duration(caption_segment_data["end"] - caption_segment_data["start"])
                    shadow_cl = shadow_cl.set_position((position[0], current_line_y))
                    clips.append(shadow_cl)

                # Main text for the whole line
                text_cl = create_text(line_text_to_render, font_size, font_color, actual_font_path,
                                      stroke_color=stroke_color, stroke_width=stroke_width)
                text_cl = text_cl.set_start(caption_segment_data["start"]).set_duration(caption_segment_data["end"] - caption_segment_data["start"])
                text_cl = text_cl.set_position((position[0], current_line_y))
                clips.append(text_cl)
            else:
                # Word highlighting IS enabled and there are words in this segment
                # We need to create sub-clips for each word's duration within this line

                # Find which words from caption_segment_data['words'] are on this current line_text_to_render
                # This is complex because words from Whisper are flat, lines are calculated.
                # We need to reconstruct Word objects for this line, then color them.

                # Simplification: create one text_ex clip for the line, then for each word in that line,
                # create an additional highlighted version of that word that appears on top.
                # This is easier than splicing the line by word times.

                # Base text for the line (not highlighted)
                if shadow_strength > 0:
                    shadow_cl_base = create_shadow(line_text_to_render, font_size, actual_font_path, shadow_blur, shadow_strength)
                    shadow_cl_base = shadow_cl_base.set_start(caption_segment_data["start"]).set_duration(caption_segment_data["end"] - caption_segment_data["start"])
                    shadow_cl_base = shadow_cl_base.set_position((position[0], current_line_y))
                    clips.append(shadow_cl_base)

                base_text_cl = create_text(line_text_to_render, font_size, font_color, actual_font_path,
                                           stroke_color=stroke_color, stroke_width=stroke_width)
                base_text_cl = base_text_cl.set_start(caption_segment_data["start"]).set_duration(caption_segment_data["end"] - caption_segment_data["start"])
                base_text_cl = base_text_cl.set_position((position[0], current_line_y))
                clips.append(base_text_cl)

                # Now, overlay highlighted words
                # This requires knowing the (x,y) position of each word in the line.
                # create_text_ex gives a CompositeVideoClip. We need to position this composite,
                # then figure out relative positions of words *within* it if we want to overlay.

                # Alternative for word highlight: iterate through words of the *original parsed segment*
                # (caption_segment_data['words']) that fall onto the current line_text_to_render.

                # Let's try the Word object coloring approach with create_text_ex for the line
                # This means the *entire line* will flash highlight based on the first word of the line's timing
                # This is not ideal. The user's original code implied word-by-word highlighting.

                # Correct approach for word-by-word highlight:
                # The loop should be over individual words from caption_segment_data['words'].
                # For each word, determine which line it falls on. Then create the full line text,
                # but highlight *only that word* using Word objects, for the duration of that word.

                # This is already handled by the prior structure:
                # captions_to_draw_for_segment was created by looping through words if highlight_current_word.
                # So, current_caption_data here is effectively a "per-word" display instruction.
                # The issue is that 'text' in current_caption_data is the *full original text* of the segment,
                # not just the line. And 'highlight_word_text' is the word.
                # This means calculate_lines is called with full segment text repeatedly.

                # Re-evaluating the loop structure based on user's original snippet logic:
                # The outer loop is `for caption_segment in parsed_captions`.
                # Inner loop `for current_caption_data in captions_to_draw_for_segment`
                #   where captions_to_draw_for_segment is made from segment words if highlighting.
                #   'current_caption_data' has 'text' (full line from segment) and 'highlight_word_text'.
                #   'start' and 'end' in current_caption_data are for the *word*.

                # So, for each word's duration, we re-draw all lines of the caption segment,
                # but with that specific word highlighted.

                # The current line_info['text'] is a line from the full caption_segment_data['text'].
                # We need to construct Word objects for this line_info['text'],
                # highlighting if a word in it matches current_caption_data['highlight_word_text'].

                word_objs_for_line = []
                words_in_line = line_info["text"].split(' ')

                # Match current_caption_data["highlight_word_text"] against words_in_line
                # This is tricky due to potential mismatches (punctuation, case) if not careful.
                # Assuming highlight_word_text is clean.

                temp_highlight_word = current_caption_data.get("highlight_word_text") if highlight_current_word else None

                for w_str in words_in_line:
                    wo = Word(w_str)
                    # A simple string match for highlighting.
                    # More robust: use word start/end times if available and align with Whisper's word objects.
                    if temp_highlight_word and w_str.strip().startswith(temp_highlight_word.strip()) and len(w_str.strip()) >= len(temp_highlight_word.strip()) -1 : # Allow for minor diffs like trailing punctuation
                        wo.set_color(word_highlight_color)
                    else:
                        wo.set_color(font_color) # Default color
                    word_objs_for_line.append(wo)

                # Create shadow for this line, for this word's duration
                if shadow_strength > 0:
                    # Shadow uses create_text_ex for consistency if Word objects are complex (they are not here)
                    # Or, create_shadow could take Word objects. For now, it takes string.
                    shadow_hl_cl = create_shadow(line_info["text"], font_size, actual_font_path, shadow_blur, shadow_strength)
                    shadow_hl_cl = shadow_hl_cl.set_start(current_caption_data["start"]).set_duration(current_caption_data["end"] - current_caption_data["start"])
                    shadow_hl_cl = shadow_hl_cl.set_position((position[0], current_line_y))
                    clips.append(shadow_hl_cl)

                # Create main text with highlighted word for this line, for this word's duration
                text_hl_cl = create_text_ex(word_objs_for_line, font_size, font_color, # font_color is base, Word obj color overrides
                                           actual_font_path, # Pass resolved path
                                           stroke_color=stroke_color, stroke_width=stroke_width)
                text_hl_cl = text_hl_cl.set_start(current_caption_data["start"]).set_duration(current_caption_data["end"] - current_caption_data["start"])
                text_hl_cl = text_hl_cl.set_position((position[0], current_line_y))
                clips.append(text_hl_cl)

            current_line_y += line_info["height"] # Advance Y for next line in the block

        generation_end_time = time.time()
        generation_time = generation_end_time - _start_time
        if print_info:
            print(f"Caption elements for segment generated in {generation_time*1000:.0f} ms. Total clips: {len(clips)-1}")
            _start_time = time.time() # Reset for next segment's generation timing or for render timing

    # Final rendering after all caption clips are generated
    if print_info:
        print(f"Rendering video with all captions: {output_file}")

    render_start_time = time.time()
    try:
        video_with_captions = CompositeVideoClip(clips, size=video.size)
        video_with_captions.write_videofile(
            filename=output_file,
            codec="libx264",
            fps=video.fps if video.fps and video.fps > 0 else 24,
            threads=os.cpu_count() or 4, # Use more threads if available
            # logger="bar" if print_info else None, # Progress bar can be noisy
            logger=None,
            preset="medium", # faster than slow, good quality
            ffmpeg_params=[
                "-crf", "23", # Good quality/size balance
                "-pix_fmt", "yuv420p" # Common pixel format for compatibility
            ]
        )
        render_end_time = time.time()
        render_time = render_end_time - render_start_time
        total_process_time = render_end_time - (_start_time if not print_info else generation_end_time) # Fix _start_time reference
        if print_info:
            print(f"Video with captions rendered in {render_time//60:02.0f}m{render_time%60:02.0f}s")
            print(f"Total caption processing time: {total_process_time//60:02.0f}m{total_process_time%60:02.0f}s")

        return output_file
    except Exception as e:
        print(f"[ERROR] Failed to write video with captions: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if 'video' in locals() and hasattr(video, 'close'): video.close()
        # It's good practice to close all generated clips if they are not automatically closed by CompositeVideoClip
        for c in clips[1:]: # clips[0] is the original video
             if hasattr(c, 'close'):
                 try:
                     c.close()
                 except Exception as e_close:
                     if print_info: print(f"Warning: could not close a clip: {e_close}")


def transcribe_locally(
    audio_file: str,
    prompt: str | None = None
):
    """
    Transcribe an audio file using the local Whisper package.
    Returns the 'segments' part of the transcription.
    """
    print(f"[INFO] Starting local transcription for: {audio_file}")
    # Check if CUDA is available and set device accordingly
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Whisper using device: {device}")
    if device == "cuda":
        # Check for FP16 support. torch.cuda.is_bf16_supported() is for bfloat16
        # For float16, typically it's available if CUDA is, but some older GPUs might not fully support it well.
        # whisper.transcribe has an fp16 parameter.
        # A more direct check could be related to the compute capability of the GPU.
        # For now, let's assume if CUDA is available, fp16 can be attempted by Whisper.
        # The model itself will be loaded, and transcribe will handle fp16 option.
        # Let's refine the check for fp16 support.
        # One way is to check compute capability, e.g., >= 7.0 for good FP16 performance.
        # However, Whisper might handle this internally.
        # For simplicity, we assume Whisper's fp16=True will work if device is CUDA.
        # Update: The provided snippet has a more specific check:
        if not torch.cuda.is_fp16_supported():
            print("[WARNING] CUDA device does not support FP16. Transcription might be slower or use more memory.")
            use_fp16 = False
        else:
            use_fp16 = True
    else:
        use_fp16 = False


    # Load the Whisper model on the specified device
    # Model size: "tiny", "base", "small", "medium", "large"
    # Using "base" as per user snippet. Can be parameterized later if needed.
    model_name = "base"
    try:
        # Ensure the model is moved to the correct device upon loading
        model = whisper.load_model(model_name, device=device)
        print(f"[INFO] Whisper model '{model_name}' loaded onto {device}.")
    except Exception as e:
        print(f"[ERROR] Failed to load Whisper model '{model_name}': {e}")
        print("Please ensure Whisper is installed correctly and model files are accessible.")
        return None # Indicate failure

    try:
        transcription_result = model.transcribe(
            audio=audio_file,
            word_timestamps=True,
            fp16=use_fp16, # Let Whisper handle this based on device and model.
            initial_prompt=prompt,
        )
        print(f"[INFO] Transcription completed for: {audio_file}")
        return transcription_result["segments"]
    except Exception as e:
        print(f"[ERROR] Error during Whisper transcription: {e}")
        return None # Indicate failure

def has_partial_sentence(text): # Helper for parse_transcription_segments
    words = text.split()
    if len(words) >= 2:
        prev_word = text.split()[-2].strip()
        # Check if the second to last word ends with a sentence-ending punctuation
        if prev_word and prev_word[-1] in ['.', '!', '?']: # Added more terminators
            return True
    # Additionally, consider if the text itself ends with a punctuation, implying it's a full sentence part.
    if text.strip() and text.strip()[-1] in ['.', '!', '?']:
        return True # Treat as complete if it ends with punctuation
    return False

def parse_transcription_segments(
    segments: list[dict],
    fit_function: Callable, # Example: Callable[[str], bool]
    allow_partial_sentences: bool = False,
):
    """
    Parses Whisper segments into captions that fit based on fit_function.
    """
    if segments is None: # Handle case where transcription failed
        print("[WARN] Segments input to parse_transcription_segments is None. Returning empty list.")
        return []

    captions = []
    current_caption = { # Renamed from 'caption' to avoid conflict if this func is nested later
        "start": None,
        "end": 0,
        "words": [],
        "text": "",
    }

    # Pre-process segments: Merge words that are not separated by spaces (from user code)
    for s_idx, segment in enumerate(segments):
        if "words" not in segment or not isinstance(segment["words"], list):
            print(f"[WARN] Segment {s_idx} missing 'words' or 'words' is not a list. Skipping segment.")
            continue # Skip malformed segment

        new_words = []
        if not segment["words"]: # if words list is empty
            # print(f"[INFO] Segment {s_idx} has an empty 'words' list.")
            continue

        # Ensure current_word_obj is initialized with a copy of the first word's dictionary
        # and that the first word itself is valid.
        if not isinstance(segment["words"][0], dict) or "word" not in segment["words"][0] or "start" not in segment["words"][0] or "end" not in segment["words"][0]:
            print(f"[WARN] Segment {s_idx}, first word is malformed. Skipping word processing for this segment.")
            continue
        current_word_obj = dict(segment["words"][0])


        for w_idx in range(1, len(segment["words"])):
            next_word_obj_original = segment["words"][w_idx]

            # Validate next_word_obj_original structure
            if not isinstance(next_word_obj_original, dict) or "word" not in next_word_obj_original or "start" not in next_word_obj_original or "end" not in next_word_obj_original :
                print(f"[WARN] Malformed word object at segment {s_idx}, word index {w_idx}. Skipping this word.")
                # Add the current_word_obj before skipping the malformed next_word_obj
                if current_word_obj and "word" in current_word_obj: # ensure current_word_obj is valid before appending
                    new_words.append(current_word_obj)
                current_word_obj = None # Mark as consumed or invalid for next iteration
                continue # Move to the next word in the original list

            if current_word_obj is None: # If previous word was problematic, try to start fresh
                current_word_obj = dict(next_word_obj_original)
                continue

            next_word_obj = dict(next_word_obj_original) # Work with a copy


            # Ensure 'word' key exists and is a string for current_word_obj
            if "word" not in current_word_obj or not isinstance(current_word_obj["word"], str):
                 print(f"[WARN] current_word_obj malformed at segment {s_idx}. Attempting to recover.")
                 current_word_obj = next_word_obj # Try to recover with next word
                 continue


            if next_word_obj["word"].startswith(" "): # If next word starts with space, it's separate
                new_words.append(current_word_obj)
                current_word_obj = next_word_obj
            else: # Merge if no leading space
                current_word_obj["word"] += next_word_obj["word"]
                current_word_obj["end"] = next_word_obj["end"]

        if current_word_obj and "word" in current_word_obj: # Add the last processed word for the segment
             new_words.append(current_word_obj)
        segments[s_idx]["words"] = new_words


    # Parse segments into captions
    for segment in segments:
        if "words" not in segment or not segment["words"]: # Ensure words exist and list is not empty
            continue
        for word in segment["words"]:
            # Ensure word is a dictionary and has the required keys
            if not isinstance(word, dict) or "word" not in word or "start" not in word or "end" not in word:
                print(f"[WARN] Skipping malformed word object in segment: {word}")
                continue

            if current_caption["start"] is None: # Initialize start for the very first word
                current_caption["start"] = word["start"]

            word_text = word.get("word", "") # .get() provides default if "word" is missing
            if not isinstance(word_text, str):
                word_text = "" # Safety for malformed data
                print(f"[WARN] Word text is not a string, using empty string: {word}")


            text_to_test = current_caption["text"] + word_text

            # Check criteria
            # has_partial_sentence should ideally handle empty or space-only text_to_test.strip()
            is_partial_check_relevant = not allow_partial_sentences
            current_text_is_partial = has_partial_sentence(text_to_test.strip()) if is_partial_check_relevant else False

            # caption_fits_criteria: True if we allow partials, OR if the text is NOT partial.
            caption_fits_criteria = allow_partial_sentences or not current_text_is_partial

            # fit_function should also handle empty or space-only strings gracefully.
            caption_fits_frame = fit_function(text_to_test.strip())


            if caption_fits_criteria and caption_fits_frame:
                current_caption["words"].append(word)
                current_caption["end"] = word["end"]
                current_caption["text"] = text_to_test
            else:
                # Only append if current_caption has actual text.
                # This prevents empty captions if the very first word itself doesn't meet criteria.
                if current_caption["text"].strip():
                    captions.append(current_caption)

                # Start new caption with the current word
                current_caption = {
                    "start": word["start"],
                    "end": word["end"],
                    "words": [word],
                    "text": word_text.strip(), # Start new caption with current word's text (stripped)
                }
                # If this single word itself doesn't fit (e.g. it's too long for fit_function),
                # it will be added as a caption on its own in the next iteration's "else" block if it's the last word,
                # or if the next word starts a new caption.
                # This case (single word not fitting) might lead to it being pushed to captions immediately
                # if the next word also causes a break.
                # Consider if a single word caption that doesn't fit should be handled differently (e.g. forced split, though not done here)
                # If the current word (now forming a new caption) itself does not fit the criteria,
                # and it's the *only* word, it will be added when the loop ends or when the next word forces a break.
                # This is generally okay as fit_function is the primary constraint.

        # Append any remaining caption after all words in all segments are processed.
        if current_caption["text"].strip():
            captions.append(current_caption)

    return captions

# Placeholder for sanitize_filename (assumed to be defined elsewhere)
def sanitize_filename(filename: str) -> str:
    """Sanitizes a filename by removing or replacing invalid characters."""
    # Basic implementation, can be expanded
    return "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in filename)

# Placeholder for parse_resolution (assumed to be defined elsewhere)
def parse_resolution(resolution_str: str) -> tuple[int, int]:
    """Parses a 'WIDTHxHEIGHT' string into a tuple (width, height)."""
    try:
        width, height = map(int, resolution_str.lower().split('x'))
        return width, height
    except ValueError:
        print(f"Error: Invalid resolution string format: {resolution_str}. Using default 1280x720.")
        return 1280, 720 # Default or raise error

# Placeholder for get_random_endscreen (assumed to be defined elsewhere)
def get_random_endscreen(endscreen_folder_path: str, target_resolution_str: str) -> str | None:
    """Selects a random endscreen video path matching the target resolution."""
    print(f"Placeholder: get_random_endscreen called with {endscreen_folder_path}, {target_resolution_str}")
    # In a real implementation, this would scan the folder, filter by resolution, and pick one.
    # For now, let's assume it might return None or a dummy path if the folder exists.
    if os.path.exists(endscreen_folder_path):
        # Dummy logic: just an example, not functional for finding actual files
        print(f"Endscreen folder exists: {endscreen_folder_path}. No actual selection logic in placeholder.")
        return None
    return None

# Placeholder for append_endscreen_to_video (assumed to be defined elsewhere)
def append_endscreen_to_video(
    main_video_path: str,
    endscreen_video_path: str,
    final_output_path: str,
    target_width: int,
    target_height: int
) -> bool:
    """Appends an endscreen video to the main video using ffmpeg."""
    print(f"Placeholder: append_endscreen_to_video called for {main_video_path} and {endscreen_video_path}")
    # In a real implementation, this would use subprocess to call ffmpeg.
    # For now, let's simulate success if the main video exists.
    if os.path.exists(main_video_path):
        # Simulate moving main video to final path if no actual append logic
        # shutil.move(main_video_path, final_output_path)
        print(f"Placeholder: append_endscreen_to_video would try to create {final_output_path}")
        # Simulate success for placeholder purposes
        return True
    return False

def finalize_video(
    visual_clips: list, # List of moviepy.VideoClip objects
    voiceover_audio_path: str,
    background_audio_clip: AudioFileClip | None, # moviepy.AudioFileClip or None
    output_path: str, # This is the *final* desired output path
    target_resolution_str: str, # New parameter e.g., "1280x720"
    video_codec: str = 'libx264', # Good quality and widely compatible
    audio_codec: str = 'aac',     # Good quality and widely compatible # CORRECTED PARAMETER NAME HERE
    crf: int = 23,                # Constant Rate Factor (lower is better quality, 18-28 is common range)
    preset: str = 'medium',       # Encoding speed vs. compression (ultrafast, superfast, fast, medium, slow, slower, veryslow)
    threads: int = 4              # Number of threads for encoding
):
    """
    Concatenates visual clips, adds voiceover and optional background audio,
    appends an endscreen, and exports the final video.
    """
    if not visual_clips:
        print("Error: No visual clips provided to finalize_video.")
        return False

    print(f"Finalizing video. Eventual output path: {output_path}")

    # Define temporary path for main content before endscreen
    # Ensure output_dir for the final output_path exists, as temp file is placed relative to it or in it.
    output_dir = os.path.dirname(output_path)
    if not output_dir: # Handle cases where output_path is just a filename (current dir)
        output_dir = "."

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")

    temp_main_content_path = os.path.join(output_dir, "temp_main_content_" + sanitize_filename(os.path.basename(output_path)) + ".mp4")

    # Variable to track overall success
    final_success = False

    try:
        # Concatenate visual clips
        final_video_track = concatenate_videoclips(visual_clips, method="compose")
        print(f"Visual clips concatenated. Total visual duration: {final_video_track.duration:.2f}s")

        # Load voiceover audio
        voiceover_audio = AudioFileClip(voiceover_audio_path)
        print(f"Voiceover audio loaded. Duration: {voiceover_audio.duration:.2f}s")

        # Prepare final audio track
        final_audio_track = None
        if background_audio_clip:
            print("Mixing voiceover with background sound.")
            # Ensure background audio does not exceed voiceover duration if they are meant to sync that way
            if background_audio_clip.duration > voiceover_audio.duration:
                 background_audio_clip = background_audio_clip.subclip(0, voiceover_audio.duration)
            final_audio_track = CompositeAudioClip([voiceover_audio, background_audio_clip])
        else:
            print("Using only voiceover audio.")
            final_audio_track = voiceover_audio

        # Ensure audio and video durations match, adjusting audio if necessary
        # This is crucial as write_videofile can fail or produce unexpected results if they don't.
        if abs(final_video_track.duration - final_audio_track.duration) > 0.1: # 100ms tolerance
            print(f"Warning: Mismatch between video duration ({final_video_track.duration:.2f}s) and audio duration ({final_audio_track.duration:.2f}s). Adjusting audio to video duration.")
            # We adjust audio to video length. If audio is shorter, it might result in silence at the end.
            # If audio is longer, it will be cut.
            final_audio_track = final_audio_track.set_duration(final_video_track.duration)

        final_video_with_audio = final_video_track.set_audio(final_audio_track)
        print("Audio track set for the main video content.")

        print(f"Writing main content video to temporary path {temp_main_content_path} with CRF {crf} and preset {preset}...")
        # Ensure temp_audiofile_path is a directory
        temp_audio_dir = os.path.dirname(temp_main_content_path)
        if not temp_audio_dir: temp_audio_dir = "." # Default to current if path is just a filename

        final_video_with_audio.write_videofile(
            temp_main_content_path,
            codec=video_codec,
            audio_codec=audio_codec, # <<<< THE FIX IS HERE <<<<
            temp_audiofile_path=temp_audio_dir, # Moviepy recommends a directory here
            remove_temp=True,
            threads=threads,
            fps=24,
            preset=preset,
            ffmpeg_params=['-crf', str(crf)]
        )
        print(f"Main content video (visuals + audio mix) saved temporarily to {temp_main_content_path}")

    # --- New Transcription and Captioning Stage ---
        video_for_endscreen = temp_main_content_path # Default to this if captioning fails or is skipped

        print("\n--- Starting Transcription Stage ---")
        # voiceover_audio_path is the original clean voiceover (e.g., tts_output_path)
        transcription_segments = transcribe_locally(voiceover_audio_path)

        if transcription_segments:
            # Save transcription to a text file
            # output_dir is already defined: os.path.dirname(output_path)
            base_name_for_files = os.path.splitext(sanitize_filename(os.path.basename(output_path)))[0]
            transcript_txt_filepath = os.path.join(output_dir, f"{base_name_for_files}_transcription.txt")

            try:
                print(f"Saving transcription to: {transcript_txt_filepath}")
                with open(transcript_txt_filepath, "w", encoding="utf-8") as f_transcript:
                    for segment in transcription_segments:
                        words_json_serializable = []
                        if "words" in segment and segment["words"] is not None:
                            for word_info in segment["words"]:
                                serializable_word_info = {k: (float(v) if isinstance(v, np.floating) else v) for k, v in word_info.items()}
                                words_json_serializable.append(serializable_word_info)

                        start_time = segment.get("start", 0.0)
                        end_time = segment.get("end", 0.0)
                        text_content = segment.get("text", "").replace("\n", " ")

                        f_transcript.write(f"{start_time:.3f}\t{end_time:.3f}\t{text_content}\t{json.dumps(words_json_serializable)}\n")
                print(f"Transcription saved successfully to {transcript_txt_filepath}")

                print("\n--- Starting Captioning Stage ---")
                temp_video_with_captions_path = os.path.join(output_dir, "temp_main_with_captions_" + sanitize_filename(os.path.basename(output_path)) + ".mp4")

                captioned_video_path = add_captions(
                    video_file=temp_main_content_path,
                    output_file=temp_video_with_captions_path,
                    segments=transcription_segments,
                    print_info=True
                )

                if captioned_video_path and os.path.exists(captioned_video_path):
                    print(f"Video with captions generated: {captioned_video_path}")
                    try:
                        if os.path.exists(temp_main_content_path): # Check existence before removal
                            os.remove(temp_main_content_path)
                            print(f"Removed temporary file (no captions): {temp_main_content_path}")
                    except OSError as e_rem:
                        print(f"Warning: Could not remove temp file {temp_main_content_path}: {e_rem}")
                    video_for_endscreen = captioned_video_path
                else:
                    print("[WARNING] Captioning failed or produced no output. Proceeding with video without captions.")

            except Exception as e_transcript_save:
                 print(f"[ERROR] Failed during transcription saving or captioning setup: {e_transcript_save}")
                 # video_for_endscreen remains temp_main_content_path

        else:
            print("[INFO] Transcription failed or produced no segments. Skipping captioning.")
            # video_for_endscreen remains temp_main_content_path
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

KOKORO_OUTPUT_PATH = "/home/ubuntu/crewgooglegemini/manVidspro/kokoroVoiceover" # Changed to relative path

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
    output_path: str,
    target_resolution_str: str,
    video_codec: str = 'libx264',
    audio_codec: str = 'aac',  # <-- ADD THIS LINE
    crf: int = 19,
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
            temp_main_content_path,
            codec=video_codec,
            audio_codec=audio_codec,  # now defined
            temp_audiofile=temp_main_content_path + ".temp_audio.m4a",
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
    pan_options = {
        'top_left-to-bottom_right': ((0, 0), (1, 1)), 'bottom_right-to-top_left': ((1, 1), (0, 0)),
        'left-to-right': ((0, 0.5), (1, 0.5)), 'top-to-bottom': ((0.5, 0), (0.5, 1)),
        'center-in': ((0.5, 0.5), (0.5, 0.5)), 'right-to-left': ((1, 0.5), (0, 0.5)),
        'bottom-to-top': ((0.5, 1), (0.5, 0)), 'top_right-to-bottom_left': ((1, 0), (0, 1)),
        'bottom_left-to-top_right': ((0, 1), (1, 0)),
    }
    start_rel, end_rel = pan_options.get(pan_direction, ((0.5, 0.5), (0.5, 0.5)))
    w, h = image_size

    if image_clip.size[0] != w or image_clip.size[1] != h:
        image_clip = image_clip.resize((w, h))

    def crop_func(t):  # <-- Only one argument
        frame_img = ImageClip(image_clip.get_frame(t), ismask=image_clip.ismask)
        progress = t / duration
        current_zoom = zoom_start_factor + (zoom_end_factor - zoom_start_factor) * progress
        crop_w = w / current_zoom
        crop_h = h / current_zoom
        crop_w = min(crop_w, w)
        crop_h = min(crop_h, h)
        x_rel = start_rel[0] + (end_rel[0] - start_rel[0]) * progress
        y_rel = start_rel[1] + (end_rel[1] - start_rel[1]) * progress
        x_center_crop_area = w * x_rel
        y_center_crop_area = h * y_rel
        x1 = np.clip(x_center_crop_area - crop_w / 2, 0, w - crop_w)
        y1 = np.clip(y_center_crop_area - crop_h / 2, 0, h - crop_h)
        cropped_frame = frame_img.crop(x1=x1, y1=y1, width=crop_w, height=crop_h)
        final_frame = cropped_frame.resize((w, h))
        return final_frame.get_frame(0)

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

    # 2. Pre-flight Check for videoscript.json
    print("Checking for script in videoscript.json...")
    # script_json_path is defined globally/earlier in 'main' in the actual full script,
    # but for this subtask, ensure it's defined if running standalone or add it.
    # For the purpose of this subtask, let's assume script_json_path is defined earlier in main
    # like: script_json_path = "/home/ubuntu/crewgooglegemini/manVidspro/videoscript.json"
    # (If it's not, the subtask should add its definition here based on the plan)
    # Let's ensure it's defined for robustness of this subtask instruction:
    script_json_path = "/home/ubuntu/crewgooglegemini/manVidspro/videoscript.json"

    title_from_json = None # Initialize
    script_from_json = None # Initialize

    if not os.path.exists(script_json_path):
        print(f"Error: Script JSON file not found at {script_json_path}.")
        print("Please create this file, ensure it contains a 'script' field (and optionally 'title'), and then re-run.")
        return # Stop execution

    try:
        with open(script_json_path, 'r', encoding='utf-8') as f_json:
            data = json.load(f_json)

        if not isinstance(data, dict):
            print(f"Error: Content of {script_json_path} is not a valid JSON object (dictionary). It should be like {{'title': 'T', 'script': 'S'}}.")
            return # Stop execution

        script_from_json = data.get("script")
        # title_from_json = data.get("title") # Title from JSON will not be used as per latest user feedback (title always prompted)
                                            # but it's good to load it if it exists for potential future use or logging.
        if data.get("title"):
            title_from_json = data.get("title") # Store it if present

        if not script_from_json or not isinstance(script_from_json, str) or not script_from_json.strip():
            print(f"Error: The 'script' field in {script_json_path} is missing, empty, or not a string.")
            print("Please ensure videoscript.json contains a valid, non-empty 'script'.")
            # script_from_json = None # Not needed, as we return
            return # Stop execution

        print(f"Successfully loaded script from {script_json_path} (length: {len(script_from_json)}).")
        if title_from_json:
            print(f"  (Note: Title found in JSON: '{title_from_json}'. User will still be prompted for title to confirm/override.)")
        else:
            print(f"  (Note: No 'title' field found in JSON. User will be prompted for title.)")


    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {script_json_path}. Please ensure it's valid JSON (e.g., {{'title': 'T', 'script': 'S'}}).")
        return # Stop execution
    except Exception as e:
        print(f"An unexpected error occurred while reading {script_json_path}: {e}")
        return # Stop execution

    # At this point, script_from_json holds the valid script from the JSON file.
    # The main 'script' variable for the pipeline will be assigned this value later.
    # 'title_from_json' is also available but user will be prompted for title.

    # --- Get Video Title (Always prompt as per user feedback) ---
    print("\n--- Video Title ---")
    # video_title variable should be initialized to None earlier in main, e.g. where script_from_json is.
    # For this subtask, let's ensure it's handled here.
    # If title_from_json was loaded, we can inform the user but still prompt.

    # Re-initialize video_title here to ensure it's from the prompt for this run.
    # The 'video_title' variable used throughout the rest of the script will be this one.
    video_title = None

    if title_from_json: # title_from_json was loaded in the previous step
        print(f"A title ('{title_from_json}') was found in videoscript.json.")
        print("You will now be prompted to confirm or provide the title for this run.")

    video_title_input_prompt = "Enter the video title for this run: "
    video_title = input(video_title_input_prompt).strip()
    while not video_title: # Ensure a title is provided
        print("Video title cannot be empty.")
        video_title = input(video_title_input_prompt).strip()

    print(f"Video title for this run set to: '{video_title}'")

    # Now, 'video_title' holds the user-confirmed title for this session.
    # 'script_from_json' holds the script from the JSON file.
    # 'script' variable for the pipeline will be set using script_from_json later.

    # 'title_from_json' is also available but user will be prompted for title.

    # --- Get Video Title (Always prompt as per user feedback) ---
    # This block was inserted by subtask 23.
    # The 'video_title' variable used throughout the rest of the script will be this one.
    # 'script_from_json' holds the script from the JSON file (from pre-flight check #2).
    # 'title_from_json' is also available from pre-flight check #2.

    # The script for the current run is now definitively script_from_json
    script = script_from_json

    # --- Initialize (or re-initialize) tts_output_path and use_existing_voiceover ---
    # These were potentially set by a previous "Existing Voiceover Check" logic,
    # but that old logic is being replaced/restructured by this current subtask.
    # The new "Existing Voiceover Check" (Step 3 of the plan) comes *after* title and script are determined.
    tts_output_path = None
    use_existing_voiceover = False


    # --- (New Step 3 from plan) Existing Voiceover Check ---
    # This check now happens *after* title is prompted and script is loaded from JSON.
    # It decides if we can use an old audio file OR if we must generate a new one.
    # The key here is that `video_title` (from prompt) and `script` (from JSON) are now fixed for this run.

    kokoro_voiceover_dir = "/home/ubuntu/crewgooglegemini/manVidspro/kokoroVoiceover" # User specified
    print(f"\nChecking for existing voiceover in: {kokoro_voiceover_dir}...")

    potential_voiceovers = []
    if os.path.exists(kokoro_voiceover_dir) and os.path.isdir(kokoro_voiceover_dir):
        audio_extensions = ('.wav', '.mp3', '.aac', '.ogg', '.flac')
        for item in os.listdir(kokoro_voiceover_dir):
            item_path = os.path.join(kokoro_voiceover_dir, item)
            if os.path.isfile(item_path) and item.lower().endswith(audio_extensions):
                # Simple heuristic: if a voiceover filename (without extension) contains
                # a sanitized version of the current video_title, it's a candidate.
                # This is imperfect but better than just picking the newest unrelated file.
                # User might need to manage this folder carefully or use a more robust matching system.
                # For now, we just check if any audio exists and pick newest if user confirms.
                potential_voiceovers.append(item_path)

    if potential_voiceovers:
        print(f"Found {len(potential_voiceovers)} audio file(s) in the voiceover directory.")
        # Sort by modification time (newest first) to present the most recent ones first
        potential_voiceovers.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        print("Available files (newest first):")
        for i, vo_path in enumerate(potential_voiceovers):
            # Using datetime for more readable timestamp - ensure datetime is imported if this line is kept long-term
            # from datetime import datetime # Would be needed at top of file
            # For now, just path:
            print(f"  {i+1}: {os.path.basename(vo_path)} (modified: {os.path.getmtime(vo_path)})")

        # Ask user if they want to use one of these or generate a new one
        while True:
            user_choice = input(f"Use an existing voiceover (enter number 1-{len(potential_voiceovers)}), or 'N' to generate new? (N): ").strip().lower()
            if not user_choice or user_choice == 'n':
                use_existing_voiceover = False
                tts_output_path = None # Ensure it's reset
                print("Proceeding to generate a new voiceover.")
                break
            try:
                choice_idx = int(user_choice) - 1
                if 0 <= choice_idx < len(potential_voiceovers):
                    tts_output_path = potential_voiceovers[choice_idx]
                    use_existing_voiceover = True
                    print(f"Selected existing voiceover: {tts_output_path}")
                    # If using existing, the script from videoscript.json is still the master script.
                    # The title is what the user just entered.
                    print(f"This voiceover will be used for video titled '{video_title}' with script from videoscript.json.")
                    break
                else:
                    print(f"Invalid number. Please choose from 1 to {len(potential_voiceovers)} or 'N'.")
            except ValueError:
                print("Invalid input. Please enter a number or 'N'.")
    else:
        print(f"No existing voiceover files found in {kokoro_voiceover_dir}.")
        use_existing_voiceover = False
        print(f"A new voiceover will be generated using the script from videoscript.json for title '{video_title}'.")

    # --- Get Video Resolution (moved here, happens for both paths) ---
    print("\n--- Video Configuration ---")
    while True:
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

    # --- Conditional TTS Generation (if not using existing) ---
    # 'script' variable is already set to script_from_json.
    # 'video_title' is set from user prompt.
    # 'tts_output_path' is set if use_existing_voiceover is True, otherwise it's None here.
    if not use_existing_voiceover:
        # Script is already loaded from script_from_json.
        # Title is already set from user prompt.
        if not script: # Should have been caught by pre-flight, but as a safeguard
            print("Error: Script (from videoscript.json) is empty. Cannot generate new voiceover. Please check videoscript.json.")
            return

        print(f"Using script from videoscript.json (length: {len(script)}) for TTS.")
        # print(script) # Optionally print script for verification

        # Process script with Kokoro TTS
        print("\nProcessing script with Kokoro TTS...")
        tts_output_path_or_error = await process_with_kokoro_tts(script) # script is script_from_json

        if isinstance(tts_output_path_or_error, str) and os.path.exists(tts_output_path_or_error):
            tts_output_path = tts_output_path_or_error # Assign to the main tts_output_path
            print(f"Kokoro TTS processing complete. Output: {tts_output_path}")
        else:
            print(f"Kokoro TTS processing failed or returned an invalid path: '{tts_output_path_or_error}'")
            print("Cannot proceed without a valid voiceover file.")
            return

    # --- Ensure tts_output_path is valid before proceeding (either existing or newly generated) ---
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
