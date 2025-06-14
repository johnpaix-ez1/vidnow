# This is the beginning of the video pipeline script.
# More content will be added in subsequent steps.

import os
import shutil
import traceback
import whisper
import torch
from typing import Callable # For type hinting parse_transcription_segments
# import openai # Seems unused by transcribe_locally
# from openai._types import FileTypes # Seems unused

# Set FFmpeg path (should be very early, e.g., after imports)
# Ensure 'os' is imported for os.environ
import numpy as np
from PIL import Image, ImageFilter, ImageFont
import tempfile
import re
import ast
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

    # --- End of New Transcription and Captioning Stage ---

    # --- Modified Endscreen Logic ---
        endscreen_folder_path = "/home/ubuntu/crewgooglegemini/manVidspro/endscreens"
        selected_endscreen_path = get_random_endscreen(endscreen_folder_path, target_resolution_str)

        final_content_to_use_path = video_for_endscreen

        success_appending = False # Initialize success_appending for cleanup logic
        if selected_endscreen_path and os.path.exists(selected_endscreen_path):
            print(f"Attempting to append endscreen: {selected_endscreen_path} to {final_content_to_use_path}")
            target_w, target_h = parse_resolution(target_resolution_str)

            success_appending = append_endscreen_to_video(
                main_video_path=final_content_to_use_path,
                endscreen_video_path=selected_endscreen_path,
                final_output_path=output_path,
                target_width=target_w,
                target_height=target_h
            )
            if success_appending:
                print(f"Endscreen appended. Final video at: {output_path}")
                final_success = True
            else:
                print(f"Failed to append endscreen. Moving content (from {final_content_to_use_path}) to final path.")
                if os.path.exists(final_content_to_use_path): shutil.move(final_content_to_use_path, output_path)
                final_success = True
        else:
            if selected_endscreen_path:
                 print(f"Selected endscreen path {selected_endscreen_path} does not exist.")
            print(f"No suitable endscreen found or selected. Moving content (from {final_content_to_use_path}) to final path: {output_path}")
            if os.path.exists(final_content_to_use_path): shutil.move(final_content_to_use_path, output_path)
            final_success = True

        # Cleanup the source file for endscreen stage if it was a temporary captioned file and different from original temp
        if final_content_to_use_path != temp_main_content_path and os.path.exists(final_content_to_use_path):
            if success_appending :
                 try:
                     os.remove(final_content_to_use_path)
                     print(f"Removed intermediate captioned file after successful append: {final_content_to_use_path}")
                 except OSError as e_rem_captioned:
                     print(f"Warning: Could not remove intermediate captioned file {final_content_to_use_path} after append: {e_rem_captioned}")
            # If it was moved (either success_appending=False, or no endscreen), shutil.move already handled it.

        # Ensure original temp_main_content_path (if it wasn't the one moved/used by endscreen) is cleaned up
        if os.path.exists(temp_main_content_path) and final_content_to_use_path != temp_main_content_path :
            # This means captioning produced video_for_endscreen, and temp_main_content_path is the pre-caption version
            try:
                os.remove(temp_main_content_path)
                print(f"Removed initial temp file (pre-captioning): {temp_main_content_path}")
            except OSError as e_rem_init_temp:
                print(f"Warning: Could not remove initial temp file {temp_main_content_path}: {e_rem_init_temp}")
        elif os.path.exists(temp_main_content_path) and final_content_to_use_path == temp_main_content_path and success_appending:
            # This means no captioning happened (or failed), and temp_main_content_path was used for successful append. So, delete it.
            try:
                os.remove(temp_main_content_path)
                print(f"Removed temp_main_content_path after successful append (no captions): {temp_main_content_path}")
            except OSError as e_rem_init_temp:
                 print(f"Warning: Could not remove temp_main_content_path {temp_main_content_path}: {e_rem_init_temp}")

        return final_success

    except Exception as e:
        print(f"Error during video finalization: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'final_video_track' in locals() and hasattr(final_video_track, 'close'): final_video_track.close()
        if 'voiceover_audio' in locals() and hasattr(voiceover_audio, 'close'): voiceover_audio.close()
        if background_audio_clip is not None and hasattr(background_audio_clip, 'close'):
             background_audio_clip.close()
        if 'final_audio_track' in locals() and hasattr(final_audio_track, 'close'): final_audio_track.close()
        if 'final_video_with_audio' in locals() and hasattr(final_video_with_audio, 'close'): final_video_with_audio.close()
        for clip_obj in visual_clips:
            if hasattr(clip_obj, 'close'):
                clip_obj.close()

        # Specific cleanup of temp_main_content_path is now handled within the try block's endscreen logic.
        # The following general cleanup for temp_main_content_path is removed to avoid conflict.
        # if os.path.exists(temp_main_content_path) and not final_success :
        #      try:
        #          print(f"Cleaning up temp file {temp_main_content_path} due to incomplete finalization or error.")
        #          os.remove(temp_main_content_path)
        #      except OSError as e_remove_final:
        #          print(f"Warning: Could not remove temp file {temp_main_content_path} in final cleanup: {e_remove_final}")
        # elif os.path.exists(temp_main_content_path) and final_success and selected_endscreen_path :
        #      try:
        #          os.remove(temp_main_content_path)
        #          print(f"Ensured removal of temporary file: {temp_main_content_path} after successful append.")
        #      except OSError as e_remove_final_success:
        #          print(f"Warning: Could not remove temp file {temp_main_content_path} even after successful append: {e_remove_final_success}")


# Placeholder for async def main() - to indicate where finalize_video sits relative to it
async def main():
    print("Placeholder: main function called. Pipeline would run here.")
    # Example of how finalize_video might be called (requires actual clips and paths)
    # dummy_visual_clips = [] # Populate with actual MoviePy VideoClip objects
    # dummy_voiceover_path = "path/to/voiceover.mp3"
    # dummy_bg_audio = None # Or an AudioFileClip
    # dummy_output = "output/final_video.mp4"
    # dummy_resolution = "1280x720"
    #
    # if os.path.exists(dummy_voiceover_path) and dummy_visual_clips:
    #    finalize_video(dummy_visual_clips, dummy_voiceover_path, dummy_bg_audio, dummy_output, dummy_resolution)
    # else:
    #    print("Dummy assets for finalize_video not found, skipping call in placeholder main.")
    pass

if __name__ == '__main__':
    # Example of how to run main (if it were synchronous, or for asyncio setup)
    # For asyncio:
    # import asyncio
    # asyncio.run(main())
    print("video_pipeline.py script finished (placeholder execution)")
