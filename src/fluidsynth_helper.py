#!/usr/bin/env python3
"""
Helper module for working with FluidSynth
"""

import os
import platform
import shutil
import subprocess
import tempfile
import shlex
import sys
from typing import Optional, Tuple, List

from sound_test import play_wav_simple

def detect_audio_driver() -> str:
    """
    Detect the best audio driver for the current system.
    
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
        
        # Check if pipewire is running
        try:
            result = subprocess.run(
                ['pidof', 'pipewire'], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return 'pulseaudio'  # pipewire often uses pulseaudio compat
        except:
            pass
        
        # Default to alsa on Linux
        return 'alsa'
    elif system == 'darwin':
        return 'coreaudio'
    elif system == 'windows':
        # Windows can use different drivers
        try:
            # Check if wasapi is available (Windows 7+)
            result = subprocess.run(
                ['fluidsynth', '-a', 'wasapi', '--help'], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return 'wasapi'
        except:
            pass
        
        return 'dsound'  # DirectSound is the fallback
    else:
        # Safe default
        return 'alsa'

def find_fluidsynth_executable() -> Optional[str]:
    """
    Find the FluidSynth executable in the system.
    
    Returns:
        Path to FluidSynth executable or None if not found
    """
    # Check if fluidsynth is in PATH
    system = platform.system().lower()
    
    # Define possible executable names
    if system == 'windows':
        executable_names = ['fluidsynth.exe', 'fluidsynth']
    else:
        executable_names = ['fluidsynth']
    
    # Check in PATH
    for exec_name in executable_names:
        try:
            # Use 'where' on Windows, 'which' on Unix-like systems
            find_cmd = 'where' if system == 'windows' else 'which'
            result = subprocess.run(
                [find_cmd, exec_name], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    return path.splitlines()[0]  # Return the first match
        except:
            pass
    
    # Check common installation locations
    common_locations = []
    
    if system == 'windows':
        program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
        common_locations = [
            os.path.join(program_files, 'FluidSynth', 'fluidsynth.exe'),
            os.path.join(program_files_x86, 'FluidSynth', 'fluidsynth.exe'),
            os.path.join(program_files, 'fluidsynth.exe'),
            os.path.join(program_files_x86, 'fluidsynth.exe')
        ]
    elif system == 'darwin':
        common_locations = [
            '/usr/local/bin/fluidsynth',
            '/opt/homebrew/bin/fluidsynth',
            '/usr/bin/fluidsynth'
        ]
    else:  # Linux and others
        common_locations = [
            '/usr/bin/fluidsynth',
            '/usr/local/bin/fluidsynth',
            '/opt/bin/fluidsynth'
        ]
    
    for location in common_locations:
        if os.path.isfile(location):
            return location
    
    return None

def check_fluidsynth_version(executable: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Check FluidSynth version.
    
    Args:
        executable: Path to FluidSynth executable (optional)
        
    Returns:
        Tuple of (success, version_string)
    """
    if not executable:
        executable = find_fluidsynth_executable()
        if not executable:
            return False, None
    
    try:
        result = subprocess.run(
            [executable, '--version'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            # Extract version from output
            version_text = result.stdout or result.stderr
            return True, version_text.strip()
        return False, None
    except:
        return False, None

def play_soundfont(
    soundfont_path: str, 
    midi_file: str, 
    audio_driver: Optional[str] = None, 
    gain: float = 1.0,
    sample_rate: int = 44100,
    verbose: bool = False
) -> bool:
    """
    Play a MIDI file using a soundfont via FluidSynth.
    
    Args:
        soundfont_path: Path to the .sf2 file
        midi_file: Path to the MIDI file
        audio_driver: Audio driver to use (auto-detect if None)
        gain: Audio gain (volume) - default 1.0
        sample_rate: Audio sample rate - default 44100
        verbose: If True, print detailed output
        
    Returns:
        True if playback was successful, False otherwise
    """
    # Find FluidSynth
    fluidsynth_path = find_fluidsynth_executable()
    if not fluidsynth_path:
        if verbose:
            print("Error: FluidSynth not found. Please install it or add it to your PATH.")
        return False
    
    # Check if files exist
    if not os.path.exists(soundfont_path):
        if verbose:
            print(f"Error: Soundfont file not found: {soundfont_path}")
        return False
    
    if not os.path.exists(midi_file):
        if verbose:
            print(f"Error: MIDI file not found: {midi_file}")
        return False
    
    # Auto-detect audio driver if needed
    if audio_driver is None:
        audio_driver = detect_audio_driver()
    
    # Build command
    cmd = [
        fluidsynth_path,
        '-a', audio_driver,       # Audio driver
        '-g', str(gain),          # Gain
        '-r', str(sample_rate),   # Sample rate
        '-l',                     # Don't print banner
    ]
    
    # Add quiet option if not verbose
    if not verbose:
        cmd.append('-q')  # Quiet mode
    
    # Add soundfont and MIDI file
    cmd.append(soundfont_path)
    cmd.append(midi_file)
    
    try:
        if verbose:
            print(f"Running FluidSynth with: {' '.join(cmd)}")
            result = subprocess.run(cmd)
        else:
            result = subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return result.returncode == 0
    except Exception as e:
        if verbose:
            print(f"Error playing soundfont: {e}")
        return False

def render_midi_to_wav(
    soundfont_path: str, 
    midi_file: str, 
    output_wav: str, 
    audio_driver: Optional[str] = None, 
    gain: float = 1.0,
    sample_rate: int = 44100,
    verbose: bool = False
) -> bool:
    """
    Render a MIDI file to a WAV file using a soundfont via FluidSynth.
    
    Args:
        soundfont_path: Path to the .sf2 file
        midi_file: Path to the MIDI file
        output_wav: Path to the output WAV file
        audio_driver: Audio driver to use (auto-detect if None)
        gain: Audio gain (volume) - default 1.0
        sample_rate: Audio sample rate - default 44100
        verbose: If True, print detailed output
        
    Returns:
        True if rendering was successful, False otherwise
    """
    # Find FluidSynth
    fluidsynth_path = find_fluidsynth_executable()
    if not fluidsynth_path:
        if verbose:
            print("Error: FluidSynth not found. Please install it or add it to your PATH.")
        return False
    
    # Check if files exist
    if not os.path.exists(soundfont_path):
        if verbose:
            print(f"Error: Soundfont file not found: {soundfont_path}")
        return False
    
    if not os.path.exists(midi_file):
        if verbose:
            print(f"Error: MIDI file not found: {midi_file}")
        return False
    
    # Build command
    cmd = [
        fluidsynth_path,
        '-nli',                    # No MIDI in, no GUI, no shell
        '-g', str(gain),           # Gain
        '-r', str(sample_rate),    # Sample rate
        '-F', output_wav,          # Output file
        soundfont_path,            # Soundfont file
        midi_file                  # MIDI file
    ]
    
    try:
        if verbose:
            print(f"Running FluidSynth to render: {' '.join(cmd)}")
            result = subprocess.run(cmd)
        else:
            result = subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        if result.returncode != 0:
            if verbose:
                print(f"FluidSynth returned error code: {result.returncode}")
            return False
        
        # Check if output file was created
        if not os.path.exists(output_wav):
            if verbose:
                print(f"Output file was not created: {output_wav}")
            return False
        
        return True
    except Exception as e:
        if verbose:
            print(f"Error rendering MIDI to WAV: {e}")
        return False

def get_available_audio_drivers() -> List[str]:
    """
    Get list of available FluidSynth audio drivers.
    
    Returns:
        List of available audio driver names
    """
    drivers = []
    fluidsynth_path = find_fluidsynth_executable()
    
    if not fluidsynth_path:
        return []
    
    try:
        result = subprocess.run(
            [fluidsynth_path, '-a', 'help'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        output = result.stdout or result.stderr
        if not output:
            return []
        
        # Parse output to find drivers
        in_drivers_section = False
        for line in output.splitlines():
            line = line.strip()
            if 'Audio drivers' in line:
                in_drivers_section = True
                continue
            
            if in_drivers_section:
                if not line or line.startswith('-'):
                    continue
                if ':' in line:
                    driver = line.split(':')[0].strip()
                    if driver:
                        drivers.append(driver)
                else:
                    # End of drivers section
                    in_drivers_section = False
        
        return drivers
    except:
        return []

def run_fluidsynth(sf2_path: str, midi_file: str, output_wav: Optional[str] = None, audio_driver: Optional[str] = None) -> bool:
    """
    Run FluidSynth to either play a MIDI file or render it to a WAV file.
    
    Args:
        sf2_path: Path to the .sf2 file
        midi_file: Path to the MIDI file
        output_wav: Path to the output WAV file (if None, play directly)
        audio_driver: Audio driver to use (auto-detect if None)
        
    Returns:
        True if successful, False otherwise
    """
    from sound_test import test_soundfont
    
    if output_wav:
        # Rendering mode
        success, _ = test_soundfont(sf2_path, False, output_wav)
        return success
    else:
        # Playback mode - tente gerar um WAV temporário e reproduzi-lo
        temp_dir = tempfile.mkdtemp()
        wav_path = os.path.join(temp_dir, "fluidsynth_temp.wav")
        
        try:
            success, wav_file = test_soundfont(sf2_path, False, wav_path)
            
            if success and wav_file:
                from sound_test import play_wav
                return play_wav_simple(wav_file, debug=False)
            
            return False
        
        finally:
            # Limpar arquivos temporários
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass

def install_instructions() -> str:
    """
    Returns installation instructions for FluidSynth based on the current OS.
    
    Returns:
        Installation instructions string
    """
    system = platform.system().lower()
    
    if system == 'linux':
        return """
FluidSynth Installation Instructions (Linux):

Debian/Ubuntu:
    sudo apt-get install fluidsynth

Fedora:
    sudo dnf install fluidsynth

Arch Linux:
    sudo pacman -S fluidsynth
"""
    elif system == 'darwin':
        return """
FluidSynth Installation Instructions (macOS):

Using Homebrew:
    brew install fluidsynth

Using MacPorts:
    sudo port install fluidsynth
"""
    elif system == 'windows':
        return """
FluidSynth Installation Instructions (Windows):

1. Download the installer from: https://www.fluidsynth.org/download/
   or use the Windows Package Manager:
   winget install fluidsynth

2. Install and add the FluidSynth bin directory to your PATH

Alternative: Install via Chocolatey:
    choco install fluidsynth
"""
    else:
        return "Please visit https://www.fluidsynth.org/ for installation instructions for your platform."

if __name__ == "__main__":
    # Simple CLI for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="FluidSynth Helper Utility")
    parser.add_argument("--check", action="store_true", help="Check FluidSynth installation")
    parser.add_argument("--drivers", action="store_true", help="List available audio drivers")
    parser.add_argument("--play", nargs=2, metavar=("SOUNDFONT", "MIDI"), help="Play MIDI file with soundfont")
    parser.add_argument("--render", nargs=3, metavar=("SOUNDFONT", "MIDI", "WAV"), help="Render MIDI file to WAV")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    
    args = parser.parse_args()
    
    if args.check:
        fluidsynth_path = find_fluidsynth_executable()
        if fluidsynth_path:
            success, version = check_fluidsynth_version(fluidsynth_path)
            if success:
                print(f"FluidSynth found: {fluidsynth_path}")
                print(f"Version: {version}")
                print(f"Default audio driver: {detect_audio_driver()}")
            else:
                print(f"FluidSynth found at {fluidsynth_path} but couldn't get version.")
        else:
            print("FluidSynth not found in PATH or common locations.")
            print(install_instructions())
    
    elif args.drivers:
        drivers = get_available_audio_drivers()
        if drivers:
            print("Available audio drivers:")
            for driver in drivers:
                print(f"  - {driver}")
        else:
            print("No audio drivers found or FluidSynth not installed.")
    
    elif args.play:
        soundfont_path, midi_file = args.play
        print(f"Playing {midi_file} with {soundfont_path}...")
        success = play_soundfont(soundfont_path, midi_file, verbose=args.verbose)
        if not success:
            print("Failed to play. Check if FluidSynth is installed correctly.")
    
    elif args.render:
        soundfont_path, midi_file, wav_file = args.render
        print(f"Rendering {midi_file} with {soundfont_path} to {wav_file}...")
        success = render_midi_to_wav(soundfont_path, midi_file, wav_file, verbose=args.verbose)
        if success:
            print(f"Successfully rendered to {wav_file}")
        else:
            print("Failed to render. Check if FluidSynth is installed correctly.")
    
    else:
        parser.print_help()
