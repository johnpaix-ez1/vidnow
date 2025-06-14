# This is the beginning of the video pipeline script.
# More content will be added in subsequent steps.

import os
import shutil
import traceback
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    VideoClip # Assuming VideoClip might be used directly or by other functions
)
# It's good practice to also import other moviepy classes if they are used,
# e.g. ImageClip, VideoFileClip, etc. but based on finalize_video, these are the direct ones.

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
        print(f"Main content video saved temporarily to {temp_main_content_path}")

        # Endscreen logic
        endscreen_folder_path = "/home/ubuntu/crewgooglegemini/manVidspro/endscreens" # User should confirm this path
        selected_endscreen_path = get_random_endscreen(endscreen_folder_path, target_resolution_str)

        if selected_endscreen_path and os.path.exists(selected_endscreen_path):
            print(f"Attempting to append endscreen: {selected_endscreen_path}")
            target_w, target_h = parse_resolution(target_resolution_str)

            success_appending = append_endscreen_to_video(
                main_video_path=temp_main_content_path,
                endscreen_video_path=selected_endscreen_path,
                final_output_path=output_path,
                target_width=target_w,
                target_height=target_h
            )
            if success_appending:
                print(f"Endscreen appended. Final video at: {output_path}")
                final_success = True
            else:
                print(f"Failed to append endscreen. Moving main content (no endscreen) to final path.")
                shutil.move(temp_main_content_path, output_path) # Ensure file is moved
                print(f"Moved main content (no endscreen) to final path: {output_path}")
                final_success = True # Success in providing main content
        else:
            if selected_endscreen_path: # It was selected but did not exist
                 print(f"Selected endscreen path {selected_endscreen_path} does not exist. Saving main content without endscreen.")
            else: # No endscreen was found/selected by get_random_endscreen
                 print("No suitable endscreen found or endscreen folder missing. Saving main content video without endscreen.")
            shutil.move(temp_main_content_path, output_path) # Ensure file is moved
            print(f"Main content video (no endscreen) saved to: {output_path}")
            final_success = True

        return final_success

    except Exception as e:
        print(f"Error during video finalization: {e}")
        import traceback
        traceback.print_exc()
        return False # Explicitly return False on exception
    finally:
        # Clean up moviepy clips from local variables in this function's scope
        if 'final_video_track' in locals() and hasattr(final_video_track, 'close'): final_video_track.close()
        if 'voiceover_audio' in locals() and hasattr(voiceover_audio, 'close'): voiceover_audio.close()
        # background_audio_clip is passed in, so it should be closed by the caller or managed carefully if modified (e.g. subclip)
        # However, if subclip creates a new instance, the local reference 'background_audio_clip' might point to this new instance.
        # For safety, if it was potentially modified (e.g. by subclip), it might be better to close it here too.
        # Let's assume background_audio_clip passed in is not closed here, but any derived clips are.
        # The prompt's version had: if background_audio_clip and hasattr(background_audio_clip, 'close'): background_audio_clip.close()
        # This is fine if the passed clip is not expected to be used after this function.
        if background_audio_clip is not None and hasattr(background_audio_clip, 'close'):
             # If background_audio_clip.subclip created a new object and reassigned background_audio_clip, this closes the new one.
             # If it modified in place, it closes the modified original.
             # If it was not modified, it closes the original.
             # This implies the caller should not expect to reuse background_audio_clip if it's passed to this function.
             background_audio_clip.close()

        if 'final_audio_track' in locals() and hasattr(final_audio_track, 'close'): final_audio_track.close()
        if 'final_video_with_audio' in locals() and hasattr(final_video_with_audio, 'close'): final_video_with_audio.close()

        # visual_clips are passed in. The caller should manage their lifecycle.
        # However, the prompt's version includes closing them. This is safer if they are not used afterwards.
        for clip_obj in visual_clips:
            if hasattr(clip_obj, 'close'):
                clip_obj.close()

        # Clean up temporary main content file
        # This logic needs to be robust:
        # - If final_success is True, the temp file should have been moved or appended from, so it might not exist or should be deleted if append_endscreen_to_video didn't clean it up.
        # - If final_success is False, an error occurred, and the temp file might still exist.
        if os.path.exists(temp_main_content_path):
            try:
                if final_success:
                    # If success, and temp file is still here, it means it was the source for an append operation
                    # that should ideally consume or make it irrelevant, or it was moved.
                    # If append_endscreen_to_video used it as input and created output_path, then temp_main_content_path can be removed.
                    # If shutil.move occurred, it's already gone.
                    # This condition implies it was NOT moved (e.g. append happened)
                    print(f"Cleaning up temporary file {temp_main_content_path} after successful operation.")
                else:
                    print(f"Cleaning up temporary file {temp_main_content_path} due to error or incomplete finalization.")
                os.remove(temp_main_content_path)
            except OSError as e_remove_final:
                print(f"Warning: Could not remove temp file {temp_main_content_path} in final cleanup: {e_remove_final}")

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
