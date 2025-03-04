#!/usr/bin/env python3
import os
import json
import argparse
import pretty_midi
import shlex
import logging
import subprocess
import tempfile
import platform
from colorama import Fore, Style, init
from typing import List, Dict, Optional, Union, Any
import sys
import re
from enum import Enum

# Configure logging to reduce sf2utils warnings
logging.basicConfig(level=logging.ERROR)  # Only show errors, not warnings

# Import system modules
from soundfont_utils import (
    SoundfontMetadata,
    MappedNotes,
    extract_sf2_metadata,
    analyze_timbre,
    generate_tag_suggestions,
    suggest_genres,
    suggest_quality,
    create_test_midi
)
from soundfont_manager import SoundfontManager

# Initialize Colorama
init(autoreset=True)

class AnalysisMode(Enum):
    """Available analysis modes."""
    BASIC = "basic"       # Basic metadata extraction
    FULL = "full"         # Full analysis (including timbre analysis)
    INTERACTIVE = "interactive"  # Interactive mode (user questions)

def setup_argparse() -> argparse.ArgumentParser:
    """
    Configure command line argument parser.
    
    Returns:
        Configured ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="Advanced Soundfont Annotator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "-d", "--directory",
        help="Soundfont directory",
        default="."
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file",
        default="soundfonts.json"
    )
    
    parser.add_argument(
        "-m", "--mode",
        help="Analysis mode",
        choices=[mode.value for mode in AnalysisMode],
        default=AnalysisMode.FULL.value
    )
    
    parser.add_argument(
        "-r", "--recursive",
        help="Recursively search for soundfonts",
        action="store_true"
    )
    
    parser.add_argument(
        "-f", "--force",
        help="Force reanalysis even for already annotated soundfonts",
        action="store_true"
    )
    
    parser.add_argument(
        "-p", "--play",
        help="Play a test sound with the soundfont during analysis",
        action="store_true"
    )
    
    parser.add_argument(
        "--audio-driver",
        help="FluidSynth audio driver (alsa, pulseaudio, coreaudio, dsound, etc.)",
        default=None  # Will be auto-detected
    )
    
    parser.add_argument(
        "--scan",
        help="Scan directory and automatically add new soundfonts",
        action="store_true"
    )
    
    parser.add_argument(
        "--insert-data",
        help="Enable interactive data insertion for each soundfont",
        action="store_true"
    )
    
    parser.add_argument(
        "--debug",
        help="Enable debug mode with more verbose output",
        action="store_true"
    )
    
    parser.add_argument(
        "--batch-size",
        help="Number of soundfonts to process before saving (for large collections)",
        type=int,
        default=10
    )
    
    parser.add_argument(
        "--no-timbre-analysis",
        help="Skip timbre analysis (faster processing)",
        action="store_true"
    )
    
    parser.add_argument(
        "--quality-threshold",
        help="Manually set threshold for quality classification (0-1)",
        type=float,
        default=None
    )
    
    return parser

def escape_path(path: str) -> str:
    """
    Escape a file path for safe use in shell commands.
    
    Args:
        path: File path
        
    Returns:
        Escaped path
    """
    return shlex.quote(path)

def detect_audio_driver():
    """
    Detect the appropriate audio driver for FluidSynth based on the operating system.
    
    Returns:
        Name of the audio driver to use
    """
    system = platform.system().lower()
    
    if system == 'linux':
        # Check if pulseaudio is running
        try:
            result = subprocess.run(
                ['pulseaudio', '--check'], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return 'pulseaudio'
        except:
            pass
        
        # Default to alsa on Linux
        return 'alsa'
    elif system == 'darwin':
        return 'coreaudio'
    elif system == 'windows':
        return 'dsound'
    else:
        # Safe default
        return 'alsa'

def check_fluidsynth_available():
    """
    Check if FluidSynth is available in the system path.
    
    Returns:
        True if FluidSynth is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['fluidsynth', '--version'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except:
        return False

def play_soundfont_test(soundfont_path: str, audio_driver: Optional[str] = None, debug: bool = False) -> bool:
    """
    Play a test arpeggio using FluidSynth.
    
    Args:
        soundfont_path: Path to the .sf2 file
        audio_driver: Audio driver for FluidSynth to use
        debug: If True, print more detailed output
        
    Returns:
        True if playback was successful, False otherwise
    """
    # Check if FluidSynth is available
    if not check_fluidsynth_available():
        print(Fore.RED + "Error: FluidSynth is not available in your system path." + Style.RESET_ALL)
        print(Fore.YELLOW + "Please install FluidSynth and make sure it's in your PATH." + Style.RESET_ALL)
        return False
    
    # Create a temporary MIDI file
    try:
        midi_file = create_test_midi()
        if not midi_file or not os.path.exists(midi_file):
            print(Fore.RED + "Error: Failed to create test MIDI file." + Style.RESET_ALL)
            return False
    except Exception as e:
        print(Fore.RED + f"Error creating test MIDI: {e}" + Style.RESET_ALL)
        return False
    
    # Detect the appropriate audio driver if not specified
    if audio_driver is None:
        audio_driver = detect_audio_driver()
    
    try:
        # Escape paths for shell
        escaped_sf2_path = escape_path(soundfont_path)
        escaped_midi_file = escape_path(midi_file)
        
        # Build the FluidSynth command
        cmd = [
            'fluidsynth',
            '-a', audio_driver,  # Audio driver
            '-g', '1.0',         # Gain
            '-r', '44100',       # Sample rate
            '-l',                # Don't print banner
            escaped_sf2_path,    # Soundfont file
            escaped_midi_file    # MIDI file
        ]
        
        # Print the command if in debug mode
        if debug:
            print(Fore.CYAN + f"Running: {' '.join(cmd)}" + Style.RESET_ALL)
        
        # Play the MIDI file using FluidSynth
        print(Fore.YELLOW + "\nPlaying test arpeggio..." + Style.RESET_ALL)
        print(Fore.YELLOW + "Press Ctrl+C to stop playback." + Style.RESET_ALL)
        
        # Run FluidSynth as a subprocess
        result = subprocess.run(
            ' '.join(cmd), 
            shell=True, 
            stderr=subprocess.PIPE if not debug else None,
            stdout=subprocess.PIPE if not debug else None
        )
        
        if result.returncode != 0 and debug:
            print(Fore.RED + "FluidSynth returned an error:" + Style.RESET_ALL)
            if result.stderr:
                print(result.stderr.decode('utf-8', errors='replace'))
            return False
            
        return result.returncode == 0
    
    except Exception as e:
        print(Fore.RED + f"Error playing test: {e}" + Style.RESET_ALL)
        return False
    
    finally:
        # Remove the temporary MIDI file
        if midi_file and os.path.exists(midi_file):
            try:
                os.remove(midi_file)
            except:
                pass

def list_soundfonts(directory: str, recursive: bool = False) -> List[str]:
    """
    List all .sf2 files in the specified directory.
    
    Args:
        directory: Directory to scan
        recursive: If True, search in subdirectories
        
    Returns:
        List of paths to .sf2 files
    """
    sf2_files = []
    
    try:
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.sf2'):
                        sf2_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory):
                if file.lower().endswith('.sf2'):
                    sf2_files.append(os.path.join(directory, file))
    except Exception as e:
        print(Fore.RED + f"Error scanning directory: {e}" + Style.RESET_ALL)
    
    return sorted(sf2_files)

def validate_and_get_input(prompt: str, options: Optional[List[str]] = None, default: Optional[str] = None) -> str:
    """
    Request user input with validation.
    
    Args:
        prompt: Prompt text
        options: List of valid options (optional)
        default: Default value (optional)
        
    Returns:
        Validated user input
    """
    # Add information about default value and options to the prompt
    display_prompt = prompt
    if options:
        display_prompt += f" [{'/'.join(options)}]"
    if default is not None:
        display_prompt += f" (default: {default})"
    display_prompt += ": "
    
    while True:
        user_input = input(Fore.CYAN + display_prompt + Style.RESET_ALL)
        
        # If input is empty and there's a default, use the default
        if not user_input and default is not None:
            return default
        
        # If there are options, validate the input
        if options and user_input and user_input not in options:
            print(Fore.RED + f"Invalid input. Choose from: {', '.join(options)}" + Style.RESET_ALL)
            continue
        
        return user_input

def get_manual_metadata(existing_metadata: Dict) -> Dict:
    """
    Collect metadata manually from the user.
    
    Args:
        existing_metadata: Existing metadata to use as default values
        
    Returns:
        Dictionary with collected metadata
    """
    print(Fore.YELLOW + "\n=== Collecting Metadata Manually ===" + Style.RESET_ALL)
    
    metadata = {}
    
    # Descriptive information with default values from existing metadata
    metadata['name'] = input(Fore.CYAN + f"Soundfont Name (default: {existing_metadata.get('name', '')}): " + Style.RESET_ALL) or existing_metadata.get('name', '')
    
    # For timbre, we need to consider if it's a string or a dictionary
    default_timbre = ""
    if isinstance(existing_metadata.get('timbre'), str):
        default_timbre = existing_metadata.get('timbre', '')
    elif isinstance(existing_metadata.get('timbre'), dict):
        timbre_info = existing_metadata.get('timbre', {})
        default_timbre = f"{timbre_info.get('brightness', '')} {timbre_info.get('richness', '')} {timbre_info.get('harmonic_quality', '')}".strip()
    
    metadata['timbre'] = input(Fore.CYAN + f"Timbre Description (default: {default_timbre}): " + Style.RESET_ALL) or default_timbre
    
    # Tags as list
    default_tags = ", ".join(existing_metadata.get('tags', []))
    tags_input = input(Fore.CYAN + f"Tags (comma separated) (default: {default_tags}): " + Style.RESET_ALL) or default_tags
    metadata['tags'] = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
    
    # Instrument type
    metadata['instrument_type'] = input(Fore.CYAN + f"Instrument Type (default: {existing_metadata.get('instrument_type', '')}): " + Style.RESET_ALL) or existing_metadata.get('instrument_type', '')
    
    # Quality
    quality_options = ["high", "medium", "low"]
    metadata['quality'] = validate_and_get_input(
        "Quality",
        options=quality_options,
        default=existing_metadata.get('quality', 'medium')
    )
    
    # Genres as list
    default_genres = ", ".join(existing_metadata.get('genre', []))
    genres_input = input(Fore.CYAN + f"Musical Genres (comma separated) (default: {default_genres}): " + Style.RESET_ALL) or default_genres
    metadata['genre'] = [genre.strip() for genre in genres_input.split(',') if genre.strip()]
    
    # License
    metadata['license'] = input(Fore.CYAN + f"License (default: {existing_metadata.get('license', '')}): " + Style.RESET_ALL) or existing_metadata.get('license', '')
    
    # Author
    metadata['author'] = input(Fore.CYAN + f"Author (default: {existing_metadata.get('author', '')}): " + Style.RESET_ALL) or existing_metadata.get('author', '')
    
    # Description
    metadata['description'] = input(Fore.CYAN + f"Description (default: {existing_metadata.get('description', '')}): " + Style.RESET_ALL) or existing_metadata.get('description', '')
    
    # Technical information (only if no existing data)
    if not existing_metadata.get('mapped_notes'):
        print(Fore.YELLOW + "\n=== Technical Information (optional) ===" + Style.RESET_ALL)
        print(Fore.CYAN + "Leave blank to skip or use automatically detected values." + Style.RESET_ALL)
        
        mapped_notes = {}
        min_note = input(Fore.CYAN + "Lowest note (e.g., A0): " + Style.RESET_ALL)
        if min_note:
            mapped_notes['min_note'] = min_note
            
        max_note = input(Fore.CYAN + "Highest note (e.g., C8): " + Style.RESET_ALL)
        if max_note:
            mapped_notes['max_note'] = max_note
            
        missing_notes = input(Fore.CYAN + "Missing notes (comma separated): " + Style.RESET_ALL)
        if missing_notes:
            mapped_notes['missing_notes'] = [note.strip() for note in missing_notes.split(',') if note.strip()]
        
        if mapped_notes:
            metadata['mapped_notes'] = mapped_notes
    
    return metadata

def annotate_soundfont(soundfont_path: str, manager: SoundfontManager, mode: AnalysisMode, 
                      play_test: bool, insert_data: bool = False, debug: bool = False,
                      skip_timbre: bool = False, quality_threshold: Optional[float] = None,
                      audio_driver: Optional[str] = None) -> Optional[SoundfontMetadata]:
    """
    Annotate a soundfont with metadata.
    
    Args:
        soundfont_path: Path to the .sf2 file
        manager: SoundfontManager instance
        mode: Analysis mode
        play_test: If True, play a sound test
        insert_data: If True, always ask for manual data input
        debug: If True, print more detailed error information
        skip_timbre: If True, skip timbre analysis
        quality_threshold: Override threshold for quality classification
        audio_driver: Audio driver for FluidSynth to use
        
    Returns:
        SoundfontMetadata object of the annotated soundfont or None on error
    """
    print(Fore.GREEN + f"\nAnnotating: {soundfont_path}" + Style.RESET_ALL)
    
    try:
        # Automatically extract basic metadata
        auto_metadata = extract_sf2_metadata(soundfont_path)
        
        # Validate size_mb - make sure it's a positive number
        if auto_metadata.get("size_mb", 0) <= 0:
            # Try to get the size directly
            try:
                size_mb = os.path.getsize(soundfont_path) / (1024 * 1024)
                auto_metadata["size_mb"] = round(size_mb, 2)
            except Exception as e:
                if debug:
                    print(Fore.RED + f"Debug - Error getting file size: {e}" + Style.RESET_ALL)
        
        # Depending on the mode, do additional analysis
        if mode == AnalysisMode.FULL or mode == AnalysisMode.INTERACTIVE or insert_data:
            # Analyze timbre
            if not skip_timbre:
                try:
                    timbre_info = analyze_timbre(soundfont_path)
                    auto_metadata["timbre"] = timbre_info
                except Exception as e:
                    if debug:
                        print(Fore.RED + f"Debug - Timbre analysis failed: {e}" + Style.RESET_ALL)
                    # Continue with default timbre info
                    auto_metadata["timbre"] = {
                        "brightness": "medium",
                        "richness": "medium",
                        "attack": "medium",
                        "harmonic_quality": "balanced"
                    }
            else:
                # Use default timbre info
                auto_metadata["timbre"] = {
                    "brightness": "medium",
                    "richness": "medium",
                    "attack": "medium",
                    "harmonic_quality": "balanced"
                }
            
            # Suggest tags
            auto_metadata["tags"] = generate_tag_suggestions(auto_metadata)
            
            # Suggest genres
            auto_metadata["genre"] = suggest_genres(auto_metadata["timbre"])
            
            # Suggest quality - with optional threshold override
            if quality_threshold is not None:
                # A more direct quality assignment based on size
                size_mb = auto_metadata.get("size_mb", 0)
                if size_mb > quality_threshold * 30:
                    auto_metadata["quality"] = "high"
                elif size_mb > quality_threshold * 10:
                    auto_metadata["quality"] = "medium"
                else:
                    auto_metadata["quality"] = "low"
            else:
                auto_metadata["quality"] = suggest_quality(auto_metadata)
        
        # Interactive or insert_data mode
        if mode == AnalysisMode.INTERACTIVE or insert_data:
            # Play the soundfont if requested
            if play_test:
                play_success = play_soundfont_test(soundfont_path, audio_driver, debug)
                if not play_success and debug:
                    print(Fore.YELLOW + "Warning: Failed to play soundfont test" + Style.RESET_ALL)
            
            # Show automatically detected metadata
            print(Fore.YELLOW + "\n=== Automatically Detected Metadata ===" + Style.RESET_ALL)
            for key, value in auto_metadata.items():
                if key != "mapped_notes" and key != "timbre":
                    print(Fore.CYAN + f"{key}: " + Style.RESET_ALL + f"{value}")
            
            if "mapped_notes" in auto_metadata:
                print(Fore.CYAN + "mapped_notes: " + Style.RESET_ALL)
                for key, value in auto_metadata["mapped_notes"].items():
                    print(Fore.CYAN + f"  {key}: " + Style.RESET_ALL + f"{value}")
            
            if "timbre" in auto_metadata and isinstance(auto_metadata["timbre"], dict):
                print(Fore.CYAN + "timbre: " + Style.RESET_ALL)
                for key, value in auto_metadata["timbre"].items():
                    if not key.startswith("spectral_") and not key == "mfcc_features":
                        print(Fore.CYAN + f"  {key}: " + Style.RESET_ALL + f"{value}")
            
            # Ask if user wants to edit the metadata
            edit = validate_and_get_input(
                "Do you want to edit the metadata?",
                options=["y", "n"],
                default="n"
            )
            
            if edit.lower() == "y":
                manual_metadata = get_manual_metadata(auto_metadata)
                
                # Merge automatic metadata with manual metadata
                # (manual metadata takes precedence)
                merged_metadata = {**auto_metadata, **manual_metadata}
                
                # Add the soundfont to the manager
                sf = None
                try:
                    sf = manager.add_soundfont(soundfont_path, auto_analyze=False, save=False)
                except Exception as e:
                    if debug:
                        print(Fore.RED + f"Debug - Error adding soundfont: {e}" + Style.RESET_ALL)
                    raise
                
                if not sf:
                    print(Fore.RED + "Error: Failed to add soundfont to manager" + Style.RESET_ALL)
                    return None
                
                # Update metadata
                if "mapped_notes" in merged_metadata:
                    mapped_notes = merged_metadata["mapped_notes"]
                    sf.mapped_notes = MappedNotes(
                        min_note=mapped_notes.get("min_note", "C0"),
                        max_note=mapped_notes.get("max_note", "C8"),
                        missing_notes=mapped_notes.get("missing_notes", [])
                    )
                
                sf.name = merged_metadata.get("name", sf.name)
                sf.timbre = merged_metadata.get("timbre", sf.timbre)
                sf.tags = merged_metadata.get("tags", sf.tags)
                sf.instrument_type = merged_metadata.get("instrument_type", sf.instrument_type)
                sf.quality = merged_metadata.get("quality", sf.quality)
                sf.genre = merged_metadata.get("genre", sf.genre)
                sf.license = merged_metadata.get("license", sf.license)
                sf.author = merged_metadata.get("author", sf.author)
                sf.description = merged_metadata.get("description", sf.description)
                sf.polyphony = merged_metadata.get("polyphony", sf.polyphony)
                sf.sample_rate = merged_metadata.get("sample_rate", sf.sample_rate)
                sf.bit_depth = merged_metadata.get("bit_depth", sf.bit_depth)
                sf.size_mb = merged_metadata.get("size_mb", sf.size_mb)
                
                return sf
            else:
                # Add the soundfont with the automatic metadata
                try:
                    return manager.add_soundfont(soundfont_path, auto_analyze=True, save=True)
                except Exception as e:
                    if debug:
                        print(Fore.RED + f"Debug - Error adding soundfont: {e}" + Style.RESET_ALL)
                    raise
        else:
            # Non-interactive mode, just add with automatic metadata
            try:
                return manager.add_soundfont(soundfont_path, auto_analyze=True, save=True)
            except Exception as e:
                if debug:
                    print(Fore.RED + f"Debug - Error adding soundfont: {e}" + Style.RESET_ALL)
                raise
    
    except Exception as e:
        print(Fore.RED + f"Error annotating {soundfont_path}: {e}" + Style.RESET_ALL)
        if debug:
            import traceback
            print(Fore.RED + "Debug - Full traceback:" + Style.RESET_ALL)
            traceback.print_exc()
        return None

def save_progress(manager: SoundfontManager, output_file: str, debug: bool = False) -> bool:
    """
    Save the soundfont database with error handling.
    
    Args:
        manager: SoundfontManager instance
        output_file: Output JSON file path
        debug: If True, print more detailed error information
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        manager.save_soundfonts()
        print(Fore.GREEN + f"Soundfonts saved successfully to {output_file}" + Style.RESET_ALL)
        return True
    except Exception as e:
        print(Fore.RED + f"Error saving database to {output_file}: {e}" + Style.RESET_ALL)
        if debug:
            import traceback
            print(Fore.RED + "Debug - Full traceback:" + Style.RESET_ALL)
            traceback.print_exc()
        return False

def main() -> None:
    """Main program function."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Set up analysis mode
    mode = AnalysisMode(args.mode)
    
    # Check for FluidSynth if play option is enabled
    if args.play and not check_fluidsynth_available():
        print(Fore.RED + "Error: FluidSynth is not available in your system path." + Style.RESET_ALL)
        print(Fore.YELLOW + "Please install FluidSynth and make sure it's in your PATH to use the --play option." + Style.RESET_ALL)
        print(Fore.YELLOW + "Continuing without audio playback..." + Style.RESET_ALL)
        args.play = False
    
    # Initialize soundfont manager
    try:
        manager = SoundfontManager(args.output, args.directory)
    except Exception as e:
        print(Fore.RED + f"Error initializing the SoundfontManager: {e}" + Style.RESET_ALL)
        sys.exit(1)
    
    if args.scan:
        # Automatic scanning mode
        print(Fore.YELLOW + f"Scanning directory {args.directory} for soundfonts..." + Style.RESET_ALL)
        try:
            added = manager.scan_directory(args.directory, args.recursive)
            print(Fore.GREEN + f"Added {len(added)} soundfonts to the database." + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"Error scanning directory: {e}" + Style.RESET_ALL)
            if args.debug:
                import traceback
                print(Fore.RED + "Debug - Full traceback:" + Style.RESET_ALL)
                traceback.print_exc()
        return
    
    # List soundfonts in directory
    try:
        soundfonts = list_soundfonts(args.directory, args.recursive)
    except Exception as e:
        print(Fore.RED + f"Error listing soundfonts: {e}" + Style.RESET_ALL)
        if args.debug:
            import traceback
            print(Fore.RED + "Debug - Full traceback:" + Style.RESET_ALL)
            traceback.print_exc()
        sys.exit(1)
    
    if not soundfonts:
        print(Fore.RED + "No soundfonts found in the directory." + Style.RESET_ALL)
        return
    
    print(Fore.YELLOW + f"\n=== {len(soundfonts)} Soundfonts Found ===" + Style.RESET_ALL)
    for i, sf in enumerate(soundfonts):
        print(Fore.CYAN + f"{i + 1}. {os.path.basename(sf)}" + Style.RESET_ALL)
    
    # Count for batch saving
    processed_count = 0
    success_count = 0
    
    # If in interactive mode, allow selecting soundfonts
    if mode == AnalysisMode.INTERACTIVE:
        while True:
            try:
                choice_input = input(Fore.YELLOW + "\nChoose a soundfont to annotate (0 to exit, 'all' to annotate all): " + Style.RESET_ALL)
                
                if choice_input.lower() in ['all', 'a']:
                    # Annotate all soundfonts
                    for i, sf_path in enumerate(soundfonts):
                        result = annotate_soundfont(
                            sf_path, manager, mode, args.play, args.insert_data, args.debug,
                            args.no_timbre_analysis, args.quality_threshold, args.audio_driver
                        )
                        processed_count += 1
                        if result:
                            success_count += 1
                        
                        # Save progress periodically
                        if processed_count % args.batch_size == 0:
                            print(Fore.YELLOW + f"Saving progress ({processed_count}/{len(soundfonts)})..." + Style.RESET_ALL)
                            save_progress(manager, args.output, args.debug)
                    break
                
                choice = int(choice_input)
                if choice == 0:
                    break
                if choice < 1 or choice > len(soundfonts):
                    print(Fore.RED + "Invalid choice." + Style.RESET_ALL)
                    continue
                
                # Annotate the selected soundfont
                sf_path = soundfonts[choice - 1]
                result = annotate_soundfont(
                    sf_path, manager, mode, args.play, args.insert_data, args.debug,
                    args.no_timbre_analysis, args.quality_threshold, args.audio_driver
                )
                if result:
                    success_count += 1
                processed_count += 1
                
                # Save after each annotation in interactive mode
                save_progress(manager, args.output, args.debug)
            
            except ValueError:
                print(Fore.RED + "Invalid input. Enter a number or 'all'." + Style.RESET_ALL)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nOperation cancelled by user." + Style.RESET_ALL)
                break
    else:
        # In non-interactive modes, annotate all soundfonts
        for i, sf_path in enumerate(soundfonts):
            # Check if the soundfont is already annotated and we're not forcing reanalysis
            try:
                rel_path = os.path.relpath(sf_path, args.directory)
                existing = any(sf.path == rel_path for sf in manager.get_all_soundfonts())
                
                if existing and not args.force:
                    print(Fore.YELLOW + f"Skipping {os.path.basename(sf_path)} (already annotated)" + Style.RESET_ALL)
                    continue
                
                result = annotate_soundfont(
                    sf_path, manager, mode, args.play, args.insert_data, args.debug,
                    args.no_timbre_analysis, args.quality_threshold, args.audio_driver
                )
                processed_count += 1
                if result:
                    success_count += 1
                
                # Save progress periodically
                if processed_count % args.batch_size == 0:
                    print(Fore.YELLOW + f"Saving progress ({processed_count}/{len(soundfonts)})..." + Style.RESET_ALL)
                    save_progress(manager, args.output, args.debug)
            
            except Exception as e:
                print(Fore.RED + f"Unexpected error processing {sf_path}: {e}" + Style.RESET_ALL)
                if args.debug:
                    import traceback
                    print(Fore.RED + "Debug - Full traceback:" + Style.RESET_ALL)
                    traceback.print_exc()
    
    # Final save
    if processed_count > 0:
        save_success = save_progress(manager, args.output, args.debug)
        if save_success:
            print(Fore.GREEN + f"\nMetadata saved to {args.output}" + Style.RESET_ALL)
            print(Fore.GREEN + f"Successfully processed {success_count} out of {processed_count} soundfonts." + Style.RESET_ALL)
        else:
            print(Fore.RED + f"\nFailed to save metadata to {args.output}" + Style.RESET_ALL)
    
    # Show statistics
    try:
        stats = manager.get_statistics()
        print(Fore.YELLOW + f"\n=== Soundfont Collection Statistics ===" + Style.RESET_ALL)
        print(Fore.CYAN + f"Total Soundfonts: " + Style.RESET_ALL + f"{stats['total_soundfonts']}")
        print(Fore.CYAN + f"Total Size: " + Style.RESET_ALL + f"{stats['total_size_mb']:.2f} MB")
        print(Fore.CYAN + f"Average Size: " + Style.RESET_ALL + f"{stats['avg_size_mb']:.2f} MB")
        
        # Show top instrument types
        print(Fore.CYAN + "Top Instrument Types: " + Style.RESET_ALL)
        for i, (instrument_type, count) in enumerate(list(stats['instrument_types'].items())[:5]):
            print(f"  {instrument_type}: {count}")
        
        # Show quality distribution
        print(Fore.CYAN + "Quality Distribution: " + Style.RESET_ALL)
        for quality, count in stats['quality_distribution'].items():
            print(f"  {quality}: {count}")
    except Exception as e:
        print(Fore.RED + f"Error generating statistics: {e}" + Style.RESET_ALL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nProgram interrupted by user." + Style.RESET_ALL)
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"Unhandled error: {e}" + Style.RESET_ALL)
        import traceback
        traceback.print_exc()
        sys.exit(1)