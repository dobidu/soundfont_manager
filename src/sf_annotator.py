#!/usr/bin/env python3
import os
import json
import argparse
import pretty_midi
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
    create_test_midi,
    test_note_range
)

from fluidsynth_helper import (
    run_fluidsynth,
    detect_audio_driver
)

from soundfont_manager import SoundfontManager

from sound_test import (
    play_wav_simple,
    create_single_note_midi,
    is_silent_wav
)

# Initialize Colorama
init(autoreset=True)

def check_audio_dependencies(debug=False):
    """
    Check which audio playback modules are available and try to 
    install one if necessary.
    
    Args:
        debug: If True, shows debug info
        
    Returns:
        True if at least one dependency is available
    """
    available_packages = []
    
    try:
        import pygame
        available_packages.append("pygame")
    except ImportError:
        if debug:
            print("pygame not available")
    
    try:
        import playsound
        available_packages.append("playsound")
    except ImportError:
        if debug:
            print("playsound not available")
    
    try:
        import simpleaudio
        available_packages.append("simpleaudio")
    except ImportError:
        if debug:
            print("simpleaudio not available")
    
    try:
        import sounddevice
        import soundfile
        available_packages.append("sounddevice+soundfile")
    except ImportError:
        if debug:
            print("sounddevice and/or soundfile not available")
    
    # Se nenhum pacote estiver disponível, tente instalar um
    if not available_packages:
        try:
            print("No audio library found. Trying to install pygame...")
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "pygame"], 
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
            
            # Verificar se conseguimos instalar
            try:
                import pygame
                available_packages.append("pygame")
                print("pygame installed!")
            except ImportError:
                pass
        except Exception as e:
            if debug:
                print(f"pygame was not installed: {e}")
    
    if debug:
        if available_packages:
            print(f"Available audio libraries: {', '.join(available_packages)}")
        else:
            print("No audio library available.")
    
    return len(available_packages) > 0

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
    
    # New argument for note range testing
    parser.add_argument(
        "--test-note-range",
        help="Perform comprehensive test of playable note range",
        action="store_true"
    )
    
    # New argument for test a specific soundfont's note range
    parser.add_argument(
        "--test-sf",
        help="Test a specific soundfont file (path to .sf2 file)",
        type=str,
        default=None
    )
    
    return parser

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
    # Check audio dependencies first
    audio_available = check_audio_dependencies(debug)
    if not audio_available and debug:
        print(Fore.YELLOW + "No audio library found. Playback may be limited." + Style.RESET_ALL)
    
    print(Fore.YELLOW + "\nGenerating soundfont test..." + Style.RESET_ALL)
    print(Fore.YELLOW + "Please wait, this may take a few seconds." + Style.RESET_ALL)
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    wav_path = os.path.join(temp_dir, "soundfont_test.wav")
    
    # Generate the WAV file
    success = test_soundfont_simple(soundfont_path, wav_path, debug)
    
    if success:
        print(Fore.GREEN + "Soundfont test completed successfully!" + Style.RESET_ALL)
        
        if debug:
            print(Fore.CYAN + f"Generated WAV file: {wav_path}" + Style.RESET_ALL)
        
        # Ask if the user wants to hear the sound
        play_sound = validate_and_get_input(
            "Do you want to hear the generated sound?",
            options=["y", "n"],
            default="y"
        )
        
        if play_sound.lower() == "y":
            played = play_wav_simple(wav_path, debug)
            
            if not played:
                print(Fore.YELLOW + "Unable to play the sound automatically." + Style.RESET_ALL)
                print(Fore.YELLOW + f"You can find the test file at: {wav_path}" + Style.RESET_ALL)
                
                # Suggest alternative options
                system = platform.system().lower()
                if system == 'linux':
                    print(Fore.YELLOW + "Try playing manually with: aplay " + wav_path + Style.RESET_ALL)
                elif system == 'darwin':
                    print(Fore.YELLOW + "Try playing manually with: afplay " + wav_path + Style.RESET_ALL)
                elif system == 'windows':
                    print(Fore.YELLOW + "Try opening the file with the default Windows audio player." + Style.RESET_ALL)
    else:
        print(Fore.RED + "Failed to generate the sound test for this soundfont." + Style.RESET_ALL)
        if debug:
            print(Fore.RED + "Make sure FluidSynth is installed correctly and the soundfont is valid." + Style.RESET_ALL)
    
    return success

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
                      audio_driver: Optional[str] = None, test_note_range: bool = False) -> Optional[SoundfontMetadata]:
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
        test_note_range: If True, perform comprehensive note range test
        
    Returns:
        SoundfontMetadata object of the annotated soundfont or None on error
    """
    print(Fore.GREEN + f"\nAnnotating: {soundfont_path}" + Style.RESET_ALL)
    
    try:
        # Automatically extract basic metadata
        auto_metadata = extract_sf2_metadata(soundfont_path)

        original_tags = auto_metadata.get("tags", [])

        filename = os.path.basename(soundfont_path)
        if "path" not in auto_metadata:
            auto_metadata["path"] = soundfont_path
        
        # Validate size_mb - make sure it's a positive number
        if auto_metadata.get("size_mb", 0) <= 0:
            # Try to get the size directly
            try:
                size_mb = os.path.getsize(soundfont_path) / (1024 * 1024)
                auto_metadata["size_mb"] = round(size_mb, 2)
            except Exception as e:
                if debug:
                    print(Fore.RED + f"Debug - Error getting file size: {e}" + Style.RESET_ALL)
        
        # Test note range if requested
        if test_note_range:
            print(Fore.YELLOW + "\nTesting note range (this may take a minute)..." + Style.RESET_ALL)
            try:
                min_note, max_note, missing_notes = test_note_range(soundfont_path)
                
                # Update metadata with tested note mapping
                if "mapped_notes" not in auto_metadata:
                    auto_metadata["mapped_notes"] = {}
                
                auto_metadata["mapped_notes"]["min_note"] = min_note
                auto_metadata["mapped_notes"]["max_note"] = max_note
                auto_metadata["mapped_notes"]["missing_notes"] = missing_notes
                
                print(Fore.GREEN + f"Note range test complete: {min_note} to {max_note}" + Style.RESET_ALL)
            except Exception as e:
                if debug:
                    print(Fore.RED + f"Debug - Note range test failed: {e}" + Style.RESET_ALL)
                    import traceback
                    traceback.print_exc()
        
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
            suggested_tags = generate_tag_suggestions(auto_metadata)
            # auto_metadata["tags"] = generate_tag_suggestions(auto_metadata)
            if debug:
                print(f"Original tags: {original_tags}")
                print(f"Suggested tags: {suggested_tags}")
            
            all_tags = set(original_tags)
            all_tags.update(suggested_tags)

            auto_metadata["tags"] = sorted(list(all_tags))
            if debug:
                print(f"Final tags: {auto_metadata['tags']}")
            
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
                
                # Create a new SoundfontMetadata object with the merged data
                mapped_notes = merged_metadata.get("mapped_notes", {})
                if mapped_notes:
                    mapped_notes_obj = MappedNotes(
                        min_note=mapped_notes.get("min_note", "C0"),
                        max_note=mapped_notes.get("max_note", "C8"),
                        missing_notes=mapped_notes.get("missing_notes", [])
                    )
                else:
                    mapped_notes_obj = MappedNotes()
                
                # Create the soundfont metadata object from merged data
                sf = SoundfontMetadata(
                    id=manager.next_id,
                    name=merged_metadata.get("name", ""),
                    path=manager._get_relative_path(soundfont_path),
                    timbre=merged_metadata.get("timbre", ""),
                    tags=merged_metadata.get("tags", []),
                    instrument_type=merged_metadata.get("instrument_type", ""),
                    quality=merged_metadata.get("quality", "medium"),
                    genre=merged_metadata.get("genre", []),
                    mapped_notes=mapped_notes_obj,
                    polyphony=merged_metadata.get("polyphony", 32),
                    sample_rate=merged_metadata.get("sample_rate", 44100),
                    bit_depth=merged_metadata.get("bit_depth", 16),
                    size_mb=merged_metadata.get("size_mb", 0.0),
                    license=merged_metadata.get("license", ""),
                    author=merged_metadata.get("author", ""),
                    description=merged_metadata.get("description", ""),
                    hash=merged_metadata.get("hash", ""),
                    last_modified=merged_metadata.get("last_modified", 0.0)
                )
                
                # Add the soundfont to the manager
                manager.soundfonts.append(sf)
                manager.next_id += 1
                manager._build_indices()
                
                return sf
            else:
                rel_path = manager._get_relative_path(soundfont_path)
                
                # Creating a complete object with all metadata
                mapped_notes = auto_metadata.get("mapped_notes", {})
                mapped_notes_obj = MappedNotes(
                    min_note=mapped_notes.get("min_note", "C0"),
                    max_note=mapped_notes.get("max_note", "C8"),
                    missing_notes=mapped_notes.get("missing_notes", [])
                )
                
                sf = SoundfontMetadata(
                    id=manager.next_id,
                    name=auto_metadata.get("name", ""),
                    path=rel_path,
                    timbre=auto_metadata.get("timbre", ""),
                    tags=auto_metadata.get("tags", []),
                    instrument_type=auto_metadata.get("instrument_type", ""),
                    quality=auto_metadata.get("quality", "medium"),
                    genre=auto_metadata.get("genre", []),
                    mapped_notes=mapped_notes_obj,
                    polyphony=auto_metadata.get("polyphony", 32),
                    sample_rate=auto_metadata.get("sample_rate", 44100),
                    bit_depth=auto_metadata.get("bit_depth", 16),
                    size_mb=auto_metadata.get("size_mb", 0.0),
                    license=auto_metadata.get("license", ""),
                    author=auto_metadata.get("author", ""),
                    description=auto_metadata.get("description", ""),
                    hash=auto_metadata.get("hash", ""),
                    last_modified=auto_metadata.get("last_modified", 0.0)
                )
                
                # Add to the manager
                manager.soundfonts.append(sf)
                manager.next_id += 1
                manager._build_indices()
                
                return sf
        else:
            # Non-interactive mode, add with automatic metadata
            # Also preserving all detected metadata
            rel_path = manager._get_relative_path(soundfont_path)
            
            # Creating a complete object with all metadata
            mapped_notes = auto_metadata.get("mapped_notes", {})
            mapped_notes_obj = MappedNotes(
                min_note=mapped_notes.get("min_note", "C0"),
                max_note=mapped_notes.get("max_note", "C8"),
                missing_notes=mapped_notes.get("missing_notes", [])
            )
            
            sf = SoundfontMetadata(
                id=manager.next_id,
                name=auto_metadata.get("name", ""),
                path=rel_path,
                timbre=auto_metadata.get("timbre", ""),
                tags=auto_metadata.get("tags", []),
                instrument_type=auto_metadata.get("instrument_type", ""),
                quality=auto_metadata.get("quality", "medium"),
                genre=auto_metadata.get("genre", []),
                mapped_notes=mapped_notes_obj,
                polyphony=auto_metadata.get("polyphony", 32),
                sample_rate=auto_metadata.get("sample_rate", 44100),
                bit_depth=auto_metadata.get("bit_depth", 16),
                size_mb=auto_metadata.get("size_mb", 0.0),
                license=auto_metadata.get("license", ""),
                author=auto_metadata.get("author", ""),
                description=auto_metadata.get("description", ""),
                hash=auto_metadata.get("hash", ""),
                last_modified=auto_metadata.get("last_modified", 0.0)
            )
            
            # Add to the manager
            manager.soundfonts.append(sf)
            manager.next_id += 1
            manager._build_indices()
            
            return sf
    
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

def simplified_midi_for_test(output_file: str) -> bool:
    """Cria um arquivo MIDI simples com apenas três notas centrais para teste."""
    try:
        import pretty_midi
        
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)  # Piano
        
        # Apenas três notas simples (C4, E4, G4) com velocidade mais baixa
        notes = [
            {"note": 60, "start": 0.0, "end": 0.5, "velocity": 80},  # C4
            {"note": 64, "start": 0.5, "end": 1.0, "velocity": 80},  # E4
            {"note": 67, "start": 1.0, "end": 2.0, "velocity": 80},  # G4
        ]
        
        for note_info in notes:
            note = pretty_midi.Note(
                velocity=note_info["velocity"],
                pitch=note_info["note"],
                start=note_info["start"],
                end=note_info["end"]
            )
            instrument.notes.append(note)
        
        midi.instruments.append(instrument)
        midi.write(output_file)
        
        return os.path.exists(output_file)
    except Exception as e:
        print(f"Error creating simplified MIDI: {e}")
        return False

def test_soundfont_simple(soundfont_path: str, wav_output: str, debug: bool = False) -> bool:
    """Versão simplificada para testar soundfont e gerar WAV."""
    if not os.path.exists(soundfont_path):
        if debug:
            print(f"Error: Soundfont file not found: {soundfont_path}")
        return False
    
    # Verificar se o FluidSynth está disponível
    fluidsynth_available = False
    try:
        result = subprocess.run(['fluidsynth', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        fluidsynth_available = (result.returncode == 0)
    except:
        if debug:
            print("Error: FluidSynth not found.")
        return False
    
    if not fluidsynth_available:
        return False
    
    # Criar arquivo MIDI temporário
    temp_midi = None
    try:
        # Criar arquivo MIDI temporário
        fd, temp_midi = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        
        if not simplified_midi_for_test(temp_midi):
            if debug:
                print("Error creating MIDI file for test.")
            return False
        
        # Renderizar para WAV usando FluidSynth
        cmd = [
            'fluidsynth',
            '-ni',                # No shell interface
            '-g', '0.7',          # Gain (volume mais baixo)
            '-F', wav_output,     # Arquivo WAV de saída
            soundfont_path,       # Soundfont
            temp_midi             # Arquivo MIDI
        ]
        
        if debug:
            print(f"Executing command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0 and os.path.exists(wav_output) and os.path.getsize(wav_output) > 0:
            return True
        else:
            if debug:
                print(f"Error rendering: {result.stderr}")
            return False
    
    except Exception as e:
        if debug:
            print(f"Error during soundfont test: {e}")
        return False
    
    finally:
        # Limpar arquivo MIDI temporário
        if temp_midi and os.path.exists(temp_midi):
            try:
                os.remove(temp_midi)
            except:
                pass
    
    return False

def main() -> None:
    print(Fore.YELLOW + "=== Soundfont Annotator ===" + Style.RESET_ALL)
    """Main program function."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Check if there's a specific soundfont to test
    if args.test_sf:
        if not os.path.exists(args.test_sf):
            print(Fore.RED + f"Error: Soundfont file not found: {args.test_sf}" + Style.RESET_ALL)
            sys.exit(1)
            
        print(Fore.YELLOW + f"\n=== Testing soundfont: {args.test_sf} ===" + Style.RESET_ALL)
        
        # First test the note range
        print(Fore.CYAN + "\nPerforming note range test..." + Style.RESET_ALL)
        try:
            min_note, max_note, missing_notes = test_note_range(args.test_sf)
            
            print(Fore.GREEN + "\nNote range test results:" + Style.RESET_ALL)
            print(Fore.CYAN + f"Min note: {min_note}" + Style.RESET_ALL)
            print(Fore.CYAN + f"Max note: {max_note}" + Style.RESET_ALL)
            
            if missing_notes:
                print(Fore.CYAN + f"Missing notes: {', '.join(missing_notes)}" + Style.RESET_ALL)
            else:
                print(Fore.CYAN + "No missing notes detected in range." + Style.RESET_ALL)
                
            # Also play a test sound if requested
            if args.play:
                print(Fore.YELLOW + "\nPlaying test sound..." + Style.RESET_ALL)
                play_soundfont_test(args.test_sf, args.audio_driver, args.debug)
        
        except Exception as e:
            print(Fore.RED + f"Error during note range test: {e}" + Style.RESET_ALL)
            if args.debug:
                import traceback
                traceback.print_exc()
        
        # Exit after testing the specific soundfont
        return
    
    # Set up analysis mode
    mode = AnalysisMode(args.mode)
    
    # Check for FluidSynth if play option is enabled
    if args.play and not check_fluidsynth_available():
        print(Fore.RED + "Error: FluidSynth is not available in your system path." + Style.RESET_ALL)
        print(Fore.YELLOW + "Please install FluidSynth and make sure it's in your PATH to use the --play option." + Style.RESET_ALL)
        print(Fore.YELLOW + "Continuing without audio playback..." + Style.RESET_ALL)
        args.play = False
    
    if args.play:
        audio_available = check_audio_dependencies(args.debug)
        if not audio_available:
            print(Fore.YELLOW + "Warning: No audio playback library found." + Style.RESET_ALL)
            print(Fore.YELLOW + "For a better experience, install at least one of the following libraries:" + Style.RESET_ALL)
            print(Fore.YELLOW + "  - pygame:     pip install pygame" + Style.RESET_ALL)
            print(Fore.YELLOW + "  - playsound:  pip install playsound" + Style.RESET_ALL)
            print(Fore.YELLOW + "  - simpleaudio: pip install simpleaudio" + Style.RESET_ALL)
            print(Fore.YELLOW + "  - sounddevice: pip install sounddevice soundfile" + Style.RESET_ALL)
            print(Fore.YELLOW + "Continuing without automatic audio playback..." + Style.RESET_ALL)
            
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
                            args.no_timbre_analysis, args.quality_threshold, args.audio_driver,
                            args.test_note_range
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
                    args.no_timbre_analysis, args.quality_threshold, args.audio_driver,
                    args.test_note_range
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
                    args.no_timbre_analysis, args.quality_threshold, args.audio_driver,
                    args.test_note_range
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
