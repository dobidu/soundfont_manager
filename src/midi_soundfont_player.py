#!/usr/bin/env python3
import os
import sys
import argparse
import pretty_midi
import time
import random
import tempfile
from typing import List, Dict, Optional, Union, Tuple
from colorama import Fore, Style, init
import numpy as np
from enum import Enum

# Import system modules
from soundfont_manager import SoundfontManager
from soundfont_utils import SoundfontMetadata

# Initialize Colorama
init(autoreset=True)

class ScaleType(Enum):
    """Types of musical scales."""
    MAJOR = "major"
    MINOR = "minor"
    DORIAN = "dorian"
    PHRYGIAN = "phrygian"
    LYDIAN = "lydian"
    MIXOLYDIAN = "mixolydian"
    LOCRIAN = "locrian"
    PENTATONIC_MAJOR = "pentatonic_major"
    PENTATONIC_MINOR = "pentatonic_minor"
    BLUES = "blues"
    CHROMATIC = "chromatic"

class Chord(Enum):
    """Types of chords."""
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    DOMINANT_7TH = "dominant_7th"
    MAJOR_7TH = "major_7th"
    MINOR_7TH = "minor_7th"
    HALF_DIMINISHED_7TH = "half_diminished_7th"
    DIMINISHED_7TH = "diminished_7th"
    SUSPENDED_4TH = "suspended_4th"
    SUSPENDED_2ND = "suspended_2nd"
    SIXTH = "sixth"
    MINOR_6TH = "minor_6th"
    NINTH = "ninth"
    MINOR_9TH = "minor_9th"

class MusicGenerator:
    """
    Class for generating MIDI music using soundfonts.
    """
    
    # Dictionary of scales (intervals from the tonic)
    SCALES = {
        ScaleType.MAJOR: [0, 2, 4, 5, 7, 9, 11],
        ScaleType.MINOR: [0, 2, 3, 5, 7, 8, 10],
        ScaleType.DORIAN: [0, 2, 3, 5, 7, 9, 10],
        ScaleType.PHRYGIAN: [0, 1, 3, 5, 7, 8, 10],
        ScaleType.LYDIAN: [0, 2, 4, 6, 7, 9, 11],
        ScaleType.MIXOLYDIAN: [0, 2, 4, 5, 7, 9, 10],
        ScaleType.LOCRIAN: [0, 1, 3, 5, 6, 8, 10],
        ScaleType.PENTATONIC_MAJOR: [0, 2, 4, 7, 9],
        ScaleType.PENTATONIC_MINOR: [0, 3, 5, 7, 10],
        ScaleType.BLUES: [0, 3, 5, 6, 7, 10],
        ScaleType.CHROMATIC: list(range(12))
    }
    
    # Dictionary of chords (intervals from the tonic)
    CHORDS = {
        Chord.MAJOR: [0, 4, 7],
        Chord.MINOR: [0, 3, 7],
        Chord.DIMINISHED: [0, 3, 6],
        Chord.AUGMENTED: [0, 4, 8],
        Chord.DOMINANT_7TH: [0, 4, 7, 10],
        Chord.MAJOR_7TH: [0, 4, 7, 11],
        Chord.MINOR_7TH: [0, 3, 7, 10],
        Chord.HALF_DIMINISHED_7TH: [0, 3, 6, 10],
        Chord.DIMINISHED_7TH: [0, 3, 6, 9],
        Chord.SUSPENDED_4TH: [0, 5, 7],
        Chord.SUSPENDED_2ND: [0, 2, 7],
        Chord.SIXTH: [0, 4, 7, 9],
        Chord.MINOR_6TH: [0, 3, 7, 9],
        Chord.NINTH: [0, 4, 7, 10, 14],
        Chord.MINOR_9TH: [0, 3, 7, 10, 14]
    }
    
    # Mapping of note names to MIDI numbers (C4 = 60)
    NOTE_NAME_TO_MIDI = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
        "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
    }
    
    def __init__(self, soundfont_manager: SoundfontManager):
        """
        Initializes the music generator.
        
        Args:
            soundfont_manager: Instance of SoundfontManager
        """
        self.manager = soundfont_manager
    
    def note_name_to_midi_number(self, note_name: str) -> int:
        """
        Converts a note name to a MIDI number.
        
        Args:
            note_name: Note name (e.g., "C4", "G#3", "Bb5")
            
        Returns:
            MIDI number of the note
        """
        # Extract the note name and octave
        if len(note_name) >= 2:
            if note_name[1] in ['#', 'b']:
                pitch_class = note_name[:2]
                octave = int(note_name[2:]) if len(note_name) > 2 else 4
            else:
                pitch_class = note_name[0]
                octave = int(note_name[1:]) if len(note_name) > 1 else 4
        else:
            pitch_class = note_name
            octave = 4
        
        # Calculate the MIDI number
        midi_num = 12 * (octave + 1) + self.NOTE_NAME_TO_MIDI[pitch_class]
        return midi_num
    
    def get_scale_notes(self, root_note: str, scale_type: ScaleType) -> List[int]:
        """
        Returns the MIDI numbers of the notes in a scale.
        
        Args:
            root_note: Root note of the scale (e.g., "C4")
            scale_type: Type of scale
            
        Returns:
            List of MIDI numbers of the scale notes
        """
        # Convert the root note to a MIDI number
        root_midi = self.note_name_to_midi_number(root_note)
        
        # Get the intervals of the scale
        intervals = self.SCALES[scale_type]
        
        # Generate the scale notes
        return [root_midi + interval for interval in intervals]
    
    def get_chord_notes(self, root_note: str, chord_type: Chord) -> List[int]:
        """
        Returns the MIDI numbers of the notes in a chord.
        
        Args:
            root_note: Root note of the chord (e.g., "C4")
            chord_type: Type of chord
            
        Returns:
            List of MIDI numbers of the chord notes
        """
        # Convert the root note to a MIDI number
        root_midi = self.note_name_to_midi_number(root_note)
        
        # Get the intervals of the chord
        intervals = self.CHORDS[chord_type]
        
        # Generate the chord notes
        return [root_midi + interval for interval in intervals]
    
    def create_chord_progression(self, 
                                key: str, 
                                progression: List[Tuple[int, Chord]], 
                                octave: int = 4, 
                                duration: float = 1.0) -> List[Dict]:
        """
        Creates a chord progression.
        
        Args:
            key: Key (e.g., "C", "F#")
            progression: List of tuples (degree, chord_type)
            octave: Base octave
            duration: Duration of each chord in seconds
            
        Returns:
            List of dictionaries with chord information
        """
        # Convert to MIDI
        key_midi = self.NOTE_NAME_TO_MIDI[key] + 12 * (octave + 1)
        
        # Dictionary of degrees in the major scale
        scale_degrees = {
            1: 0,   # I
            2: 2,   # II
            3: 4,   # III
            4: 5,   # IV
            5: 7,   # V
            6: 9,   # VI
            7: 11   # VII
        }
        
        chords = []
        current_time = 0.0
        
        for degree, chord_type in progression:
            # Calculate the root note of the chord
            root_offset = scale_degrees.get(degree, 0)
            root_midi = key_midi + root_offset
            
            # Get the chord notes
            chord_notes = [root_midi + interval for interval in self.CHORDS[chord_type]]
            
            # Add the chord to the list
            chords.append({
                "notes": chord_notes,
                "start": current_time,
                "end": current_time + duration,
                "velocity": 80
            })
            
            current_time += duration
        
        return chords
    
    def create_melody(self, 
                     scale_notes: List[int], 
                     num_notes: int = 8, 
                     rhythm: Optional[List[float]] = None,
                     velocity_range: Tuple[int, int] = (60, 100)) -> List[Dict]:
        """
        Creates a melody using notes from a scale.
        
        Args:
            scale_notes: List of MIDI numbers of the scale notes
            num_notes: Number of notes in the melody
            rhythm: List of durations for each note (optional)
            velocity_range: Velocity (volume) range of the notes
            
        Returns:
            List of dictionaries with melody note information
        """
        melody = []
        current_time = 0.0
        
        # Use provided rhythm or generate a random one
        if rhythm is None:
            # Generate random durations (between 0.1 and 0.5 seconds)
            rhythm = [round(random.uniform(0.1, 0.5), 2) for _ in range(num_notes)]
        
        # Ensure we have enough durations
        if len(rhythm) < num_notes:
            rhythm = rhythm * (num_notes // len(rhythm) + 1)
            rhythm = rhythm[:num_notes]
        
        # Generate the melody
        for i in range(num_notes):
            # Select a random note from the scale
            note = random.choice(scale_notes)
            
            # Select a random velocity
            velocity = random.randint(velocity_range[0], velocity_range[1])
            
            # Note duration
            duration = rhythm[i]
            
            # Add the note to the melody
            melody.append({
                "note": note,
                "start": current_time,
                "end": current_time + duration,
                "velocity": velocity
            })
            
            current_time += duration
        
        return melody
    
    def create_bass_line(self, 
                        chord_progression: List[Dict], 
                        pattern: str = "simple") -> List[Dict]:
        """
        Creates a bass line based on a chord progression.
        
        Args:
            chord_progression: Chord progression
            pattern: Rhythmic pattern for the bass
            
        Returns:
            List of dictionaries with bass note information
        """
        bass_line = []
        
        for chord in chord_progression:
            chord_start = chord["start"]
            chord_end = chord["end"]
            chord_duration = chord_end - chord_start
            
            # Use the lowest note of the chord as the bass note
            bass_note = min(chord["notes"]) - 12  # One octave below
            
            if pattern == "simple":
                # Simple pattern: one long note per chord
                bass_line.append({
                    "note": bass_note,
                    "start": chord_start,
                    "end": chord_end,
                    "velocity": 100
                })
            
            elif pattern == "walking":
                # Walking bass pattern: four notes per chord
                step_duration = chord_duration / 4
                
                # Chord notes, one octave below
                chord_notes = [note - 12 for note in chord["notes"]]
                
                for i in range(4):
                    if i == 0:
                        # First note is the root
                        note = chord_notes[0]
                    else:
                        # Other notes are chosen randomly
                        note = random.choice(chord_notes)
                    
                    bass_line.append({
                        "note": note,
                        "start": chord_start + i * step_duration,
                        "end": chord_start + (i + 1) * step_duration,
                        "velocity": 90 if i == 0 else 80
                    })
            
            elif pattern == "arpeggiated":
                # Arpeggiated pattern: arpeggio of the chord notes
                step_duration = chord_duration / 4
                
                # Chord notes, one octave below
                chord_notes = [note - 12 for note in chord["notes"]]
                
                # If the chord has less than 4 notes, repeat some
                if len(chord_notes) < 4:
                    chord_notes = chord_notes + chord_notes[:4-len(chord_notes)]
                
                for i in range(4):
                    bass_line.append({
                        "note": chord_notes[i],
                        "start": chord_start + i * step_duration,
                        "end": chord_start + (i + 1) * step_duration,
                        "velocity": 85
                    })
        
        return bass_line
    
    def create_drum_pattern(self, 
                          total_duration: float, 
                          pattern: str = "basic", 
                          beats_per_measure: int = 4,
                          tempo: float = 120.0) -> List[Dict]:
        """
        Creates a drum pattern.
        
        Args:
            total_duration: Total duration in seconds
            pattern: Type of drum pattern
            beats_per_measure: Number of beats per measure
            tempo: Tempo in BPM
            
        Returns:
            List of dictionaries with drum note information
        """
        drum_notes = []
        
        # Duration of one measure in seconds
        measure_duration = (60.0 / tempo) * beats_per_measure
        
        # Duration of one beat
        beat_duration = measure_duration / beats_per_measure
        
        # Number of measures
        num_measures = max(1, int(total_duration / measure_duration))
        
        # MIDI note for each drum part
        KICK = 36    # Kick drum
        SNARE = 38   # Snare drum
        CLOSED_HH = 42  # Closed hi-hat
        OPEN_HH = 46    # Open hi-hat
        
        # Drum patterns (1 = hit, 0 = silence)
        patterns = {
            "basic": {
                KICK: [1, 0, 0, 0, 1, 0, 0, 0],
                SNARE: [0, 0, 1, 0, 0, 0, 1, 0],
                CLOSED_HH: [1, 1, 1, 1, 1, 1, 1, 1]
            },
            "rock": {
                KICK: [1, 0, 0, 1, 0, 1, 0, 0],
                SNARE: [0, 0, 1, 0, 0, 0, 1, 0],
                CLOSED_HH: [1, 1, 1, 1, 1, 1, 1, 1]
            },
            "jazz": {
                KICK: [1, 0, 0, 0, 1, 0, 0, 0],
                SNARE: [0, 0, 1, 0, 0, 0, 1, 0],
                CLOSED_HH: [1, 0, 1, 0, 1, 0, 1, 0],
                OPEN_HH: [0, 1, 0, 1, 0, 1, 0, 1]
            }
        }
        
        # Use the specified pattern or the basic one
        drum_pattern = patterns.get(pattern, patterns["basic"])
        
        # Number of steps in the pattern
        pattern_steps = 8
        step_duration = beat_duration / 2  # 8 steps in 4 beats
        
        # Generate drum notes for each measure
        for measure in range(num_measures):
            measure_start = measure * measure_duration
            
            for step in range(pattern_steps):
                step_start = measure_start + step * step_duration
                step_end = step_start + step_duration
                
                for drum, hits in drum_pattern.items():
                    if step < len(hits) and hits[step]:
                        velocity = 100 if drum in [KICK, SNARE] else 80
                        
                        drum_notes.append({
                            "note": drum,
                            "start": step_start,
                            "end": step_end,
                            "velocity": velocity
                        })
        
        return drum_notes
    
    def create_midi(self, 
                   instruments: Dict[str, int], 
                   parts: Dict[str, List[Dict]], 
                   output_file: str) -> None:
        """
        Creates a MIDI file with multiple parts.
        
        Args:
            instruments: Dictionary with part name and MIDI program
            parts: Dictionary with part name and list of notes
            output_file: Path to the output MIDI file
        """
        # Create a PrettyMIDI object
        midi = pretty_midi.PrettyMIDI()
        
        # Add each part
        for part_name, program in instruments.items():
            if part_name not in parts:
                continue
            
            # Create an instrument
            instrument = pretty_midi.Instrument(program=program)
            
            # Add the notes
            for note_info in parts[part_name]:
                if "notes" in note_info:
                    # Chord (multiple notes)
                    for note in note_info["notes"]:
                        midi_note = pretty_midi.Note(
                            velocity=note_info["velocity"],
                            pitch=note,
                            start=note_info["start"],
                            end=note_info["end"]
                        )
                        instrument.notes.append(midi_note)
                else:
                    # Single note
                    midi_note = pretty_midi.Note(
                        velocity=note_info["velocity"],
                        pitch=note_info["note"],
                        start=note_info["start"],
                        end=note_info["end"]
                    )
                    instrument.notes.append(midi_note)
            
            # Add the instrument to the MIDI
            midi.instruments.append(instrument)
        
        # Save the MIDI file
        midi.write(output_file)
    
    def generate_composition(self, 
                           key: str = "C", 
                           scale_type: ScaleType = ScaleType.MAJOR,
                           tempo: float = 120.0,
                           num_measures: int = 4,
                           style: str = "pop",
                           output_file: str = "composition.mid") -> str:
        """
        Generates a complete musical composition.
        
        Args:
            key: Key (e.g., "C", "F#")
            scale_type: Type of scale
            tempo: Tempo in BPM
            num_measures: Number of measures
            style: Musical style
            output_file: Path to the output MIDI file
            
        Returns:
            Path to the generated MIDI file
        """
        # Duration of one measure in seconds
        measure_duration = (60.0 / tempo) * 4  # Assuming 4/4
        
        # Total duration of the composition
        total_duration = measure_duration * num_measures
        
        # Chord progressions by style
        style_progressions = {
            "pop": [
                [(1, Chord.MAJOR), (4, Chord.MAJOR), (5, Chord.MAJOR), (5, Chord.MAJOR)],
                [(1, Chord.MAJOR), (5, Chord.MAJOR), (6, Chord.MINOR), (4, Chord.MAJOR)],
                [(1, Chord.MAJOR), (4, Chord.MAJOR), (5, Chord.MAJOR), (1, Chord.MAJOR)]
            ],
            "rock": [
                [(1, Chord.MAJOR), (5, Chord.MAJOR), (6, Chord.MINOR), (4, Chord.MAJOR)],
                [(1, Chord.MAJOR), (4, Chord.MAJOR), (1, Chord.MAJOR), (5, Chord.MAJOR)],
                [(1, Chord.POWER), (5, Chord.POWER), (6, Chord.POWER), (4, Chord.POWER)]
            ],
            "jazz": [
                [(2, Chord.MINOR_7TH), (5, Chord.DOMINANT_7TH), (1, Chord.MAJOR_7TH), (1, Chord.MAJOR_7TH)],
                [(1, Chord.MAJOR_7TH), (4, Chord.DOMINANT_7TH), (3, Chord.MINOR_7TH), (6, Chord.MINOR_7TH)],
                [(2, Chord.MINOR_7TH), (5, Chord.DOMINANT_7TH), (1, Chord.MAJOR_7TH), (6, Chord.MINOR_7TH)]
            ],
            "classical": [
                [(1, Chord.MAJOR), (4, Chord.MAJOR), (5, Chord.MAJOR), (1, Chord.MAJOR)],
                [(1, Chord.MAJOR), (5, Chord.MAJOR), (6, Chord.MINOR), (3, Chord.MINOR)],
                [(1, Chord.MAJOR), (4, Chord.MAJOR), (5, Chord.DOMINANT_7TH), (1, Chord.MAJOR)]
            ]
        }
        
        # Select a progression for the chosen style
        progression = random.choice(style_progressions.get(style, style_progressions["pop"]))
        
        # Create the chord progression
        chord_progression = self.create_chord_progression(
            key=key,
            progression=progression,
            octave=3,
            duration=measure_duration
        )
        
        # Create a scale for the melody
        scale_notes = self.get_scale_notes(f"{key}4", scale_type)
        
        # Create the melody
        num_melody_notes = num_measures * 8  # 8 notes per measure
        melody = self.create_melody(
            scale_notes=scale_notes,
            num_notes=num_melody_notes,
            rhythm=None,  # Random rhythm
            velocity_range=(70, 100)
        )
        
        # Create the bass line
        if style == "jazz":
            bass_pattern = "walking"
        elif style == "rock":
            bass_pattern = "arpeggiated"
        else:
            bass_pattern = "simple"
        
        bass_line = self.create_bass_line(
            chord_progression=chord_progression,
            pattern=bass_pattern
        )
        
        # Create the drum pattern
        if style == "jazz":
            drum_pattern = "jazz"
        elif style == "rock":
            drum_pattern = "rock"
        else:
            drum_pattern = "basic"
        
        drum_part = self.create_drum_pattern(
            total_duration=total_duration,
            pattern=drum_pattern,
            tempo=tempo
        )
        
        # Define instruments by style
        style_instruments = {
            "pop": {
                "melody": 0,  # Piano
                "chord": 0,   # Piano
                "bass": 33,   # Fingered electric bass
                "drum": 0     # Drum kit (GM)
            },
            "rock": {
                "melody": 29,  # Distorted guitar
                "chord": 29,   # Distorted guitar
                "bass": 33,    # Fingered electric bass
                "drum": 0      # Drum kit (GM)
            },
            "jazz": {
                "melody": 66,  # Tenor saxophone
                "chord": 0,    # Piano
                "bass": 32,    # Acoustic bass
                "drum": 0      # Drum kit (GM)
            },
            "classical": {
                "melody": 73,  # Flute
                "chord": 48,   # Strings
                "bass": 43,    # Contrabass
                "drum": 0      # (No drums for classical)
            }
        }
        
        instruments = style_instruments.get(style, style_instruments["pop"])
        
        # Parts of the composition
        parts = {
            "melody": melody,
            "chord": chord_progression,
            "bass": bass_line
        }
        
        # Add drums except for classical style
        if style != "classical":
            parts["drum"] = drum_part
        
        # Create the MIDI file
        self.create_midi(
            instruments=instruments,
            parts=parts,
            output_file=output_file
        )
        
        return output_file
    
    def play_composition_with_soundfont(self, 
                                      midi_file: str, 
                                      soundfont_id: Optional[int] = None,
                                      instrument_type: Optional[str] = None,
                                      quality: Optional[str] = None,
                                      tags: Optional[List[str]] = None) -> None:
        """
        Plays a MIDI composition using a soundfont.
        
        Args:
            midi_file: Path to the MIDI file
            soundfont_id: Soundfont ID (optional)
            instrument_type: Instrument type for selection (optional)
            quality: Desired quality (optional)
            tags: Tags to filter soundfonts (optional)
        """
        # Select a soundfont
        if soundfont_id is not None:
            soundfont = self.manager.get_soundfont_by_id(soundfont_id)
            if not soundfont:
                print(Fore.RED + f"Soundfont not found with ID: {soundfont_id}" + Style.RESET_ALL)
                return
        else:
            # Filter soundfonts based on criteria
            filtered = self.manager.get_all_soundfonts()
            
            if instrument_type:
                filtered = self.manager.get_soundfonts_by_instrument_type(instrument_type)
            
            if quality:
                filtered = [sf for sf in filtered if sf.quality == quality]
            
            if tags:
                tag_matches = self.manager.get_soundfonts_by_tags(tags)
                filtered = [sf for sf in filtered if sf in tag_matches]
            
            if not filtered:
                print(Fore.RED + "No soundfont found with the specified criteria." + Style.RESET_ALL)
                return
            
            # Select a random soundfont from the filtered ones
            soundfont = random.choice(filtered)
        
        print(Fore.GREEN + f"\nPlaying composition with soundfont: {soundfont.name}" + Style.RESET_ALL)
        print(Fore.CYAN + f"Instrument type: {soundfont.instrument_type}" + Style.RESET_ALL)
        print(Fore.CYAN + f"Quality: {soundfont.quality}" + Style.RESET_ALL)
        print(Fore.CYAN + f"Tags: {', '.join(soundfont.tags)}" + Style.RESET_ALL)
        
        # Get the absolute path of the soundfont
        sf_path = self.manager.get_absolute_path(soundfont)
        
        # Play the MIDI with FluidSynth
        os.system(f"fluidsynth -a alsa -g 1.0 {sf_path} {midi_file}")

def setup_argparse() -> argparse.ArgumentParser:
    """
    Configures the command-line argument parser.
    
    Returns:
        Configured ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="MIDI music generator and player with Soundfonts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "-d", "--db",
        help="JSON file for the soundfont database",
        default="soundfonts.json"
    )
    
    parser.add_argument(
        "-s", "--sf-dir",
        help="Base directory for soundfonts",
        default="."
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output MIDI file",
        default="composition.mid"
    )
    
    parser.add_argument(
        "-k", "--key",
        help="Key of the composition",
        default="C",
        choices=["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
    )
    
    parser.add_argument(
        "-t", "--tempo",
        help="Tempo in BPM",
        type=float,
        default=120.0
    )
    
    parser.add_argument(
        "-m", "--measures",
        help="Number of measures",
        type=int,
        default=4
    )
    
    parser.add_argument(
        "--scale",
        help="Scale type",
        default=ScaleType.MAJOR.value,
        choices=[scale.value for scale in ScaleType]
    )
    
    parser.add_argument(
        "--style",
        help="Musical style",
        default="pop",
        choices=["pop", "rock", "jazz", "classical"]
    )
    
    parser.add_argument(
        "--sf-id",
        help="Specific soundfont ID for playback",
        type=int
    )
    
    parser.add_argument(
        "--instrument-type",
        help="Instrument type to filter soundfonts"
    )
    
    parser.add_argument(
        "--quality",
        help="Soundfont quality",
        choices=["high", "medium", "low"]
    )
    
    parser.add_argument(
        "--tags",
        help="Tags to filter soundfonts (comma-separated)"
    )
    
    parser.add_argument(
        "--no-play",
        help="Only generate MIDI without playback",
        action="store_true"
    )
    
    parser.add_argument(
        "--list-soundfonts",
        help="List all available soundfonts",
        action="store_true"
    )
    
    return parser

def list_all_soundfonts(manager: SoundfontManager) -> None:
    """
    Lists all available soundfonts.
    
    Args:
        manager: Instance of SoundfontManager
    """
    soundfonts = manager.get_all_soundfonts()
    
    if not soundfonts:
        print(Fore.RED + "No soundfonts found in the database." + Style.RESET_ALL)
        return
    
    print(Fore.YELLOW + f"\n=== {len(soundfonts)} Available Soundfonts ===" + Style.RESET_ALL)
    
    for sf in soundfonts:
        print(Fore.GREEN + f"\nID: {sf.id} - {sf.name}" + Style.RESET_ALL)
        print(Fore.CYAN + f"  Type: {sf.instrument_type}" + Style.RESET_ALL)
        print(Fore.CYAN + f"  Quality: {sf.quality}" + Style.RESET_ALL)
        print(Fore.CYAN + f"  Tags: {', '.join(sf.tags)}" + Style.RESET_ALL)
        print(Fore.CYAN + f"  Genres: {', '.join(sf.genre)}" + Style.RESET_ALL)
        print(Fore.CYAN + f"  Size: {sf.size_mb:.2f} MB" + Style.RESET_ALL)

def main() -> None:
    """Main function of the program."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Initialize the soundfont manager
    manager = SoundfontManager(args.db, args.sf_dir)
    
    # List all soundfonts and exit
    if args.list_soundfonts:
        list_all_soundfonts(manager)
        return
    
    # Initialize the music generator
    generator = MusicGenerator(manager)
    
    # Generate the composition
    print(Fore.YELLOW + "\n=== Generating Musical Composition ===" + Style.RESET_ALL)
    print(Fore.CYAN + f"Key: {args.key}" + Style.RESET_ALL)
    print(Fore.CYAN + f"Scale: {args.scale}" + Style.RESET_ALL)
    print(Fore.CYAN + f"Style: {args.style}" + Style.RESET_ALL)
    print(Fore.CYAN + f"Tempo: {args.tempo} BPM" + Style.RESET_ALL)
    print(Fore.CYAN + f"Measures: {args.measures}" + Style.RESET_ALL)
    
    midi_file = generator.generate_composition(
        key=args.key,
        scale_type=ScaleType(args.scale),
        tempo=args.tempo,
        num_measures=args.measures,
        style=args.style,
        output_file=args.output
    )
    
    print(Fore.GREEN + f"\nComposition generated successfully: {midi_file}" + Style.RESET_ALL)
    
    # Play the composition
    if not args.no_play:
        # Process the tags
        tags = None
        if args.tags:
            tags = [tag.strip() for tag in args.tags.split(',') if tag.strip()]
        
        # Play with soundfont
        generator.play_composition_with_soundfont(
            midi_file=midi_file,
            soundfont_id=args.sf_id,
            instrument_type=args.instrument_type,
            quality=args.quality,
            tags=tags
        )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nProgram interrupted by user." + Style.RESET_ALL)
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"Error: {e}" + Style.RESET_ALL)
        sys.exit(1)