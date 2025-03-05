import os
import shutil
import numpy as np
import pretty_midi
import logging
import tempfile
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, asdict, field
from sf2utils.sf2parse import Sf2File
import librosa
import hashlib

# Configure logging to reduce sf2utils warnings
logging.basicConfig(level=logging.ERROR)  # Only show errors, not warnings

# Constants
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
OCTAVE_RANGE = range(-1, 10)  # From C-1 to B9

# MIDI to note name mapping
MIDI_TO_NOTE = {}
for octave in OCTAVE_RANGE:
    for note_idx, note_name in enumerate(NOTE_NAMES):
        midi_num = (octave + 1) * 12 + note_idx
        if 0 <= midi_num <= 127:
            MIDI_TO_NOTE[midi_num] = f"{note_name}{octave}"

# Reverse mapping: note name to MIDI number
NOTE_TO_MIDI = {v: k for k, v in MIDI_TO_NOTE.items()}

@dataclass
class MappedNotes:
    """Information about the note mapping of a soundfont."""
    min_note: str = "C0"
    max_note: str = "C8"
    missing_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class SoundfontMetadata:
    """Complete metadata for a soundfont."""
    id: int = 0
    name: str = ""
    path: str = ""
    timbre: str = ""
    tags: List[str] = field(default_factory=list)
    instrument_type: str = ""
    quality: str = "medium"
    genre: List[str] = field(default_factory=list)
    mapped_notes: MappedNotes = field(default_factory=MappedNotes)
    polyphony: int = 0
    sample_rate: int = 44100
    bit_depth: int = 16
    size_mb: float = 0.0
    license: str = ""
    author: str = ""
    description: str = ""
    hash: str = ""  # File hash to identify changes
    last_modified: float = 0.0  # Last modified timestamp
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = asdict(self)
        # Ensure mapped_notes is a dictionary
        if isinstance(result['mapped_notes'], MappedNotes):
            result['mapped_notes'] = result['mapped_notes'].to_dict()
        return result

def decode_safely(value) -> str:
    """
    Safely decode a value that might be bytes or already a string.
    
    Args:
        value: The value to decode (bytes or str)
        
    Returns:
        Decoded string
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode('latin-1', errors='replace').strip()
    return str(value).strip()

def safe_get_attr(obj: Any, attr_name: str, default: Any = None) -> Any:
    """
    Safely get an attribute from an object, returning a default if it doesn't exist.
    
    Args:
        obj: Object to get attribute from
        attr_name: Name of the attribute
        default: Default value if attribute doesn't exist
        
    Returns:
        Attribute value or default
    """
    try:
        return getattr(obj, attr_name, default)
    except:
        return default

def extract_sf2_metadata(sf2_path: str) -> Dict:
    """
    Automatically extract technical metadata from an SF2 file.
    
    Args:
        sf2_path: Path to the .sf2 file
        
    Returns:
        Dictionary with extracted metadata
    """
    # Check if file exists
    if not os.path.exists(sf2_path):
        raise FileNotFoundError(f"File not found: {sf2_path}")
    
    # Calculate file size in MB - do this outside of try/except to ensure it's captured
    try:
        size_mb = os.path.getsize(sf2_path) / (1024 * 1024)
    except Exception as e:
        print(f"Warning: Error getting file size: {e}")
        size_mb = 0.0
    
    # Calculate file hash for quick change identification
    try:
        file_hash = calculate_file_hash(sf2_path)
    except Exception as e:
        print(f"Warning: Error calculating file hash: {e}")
        file_hash = ""
    
    # Last modified timestamp
    try:
        last_modified = os.path.getmtime(sf2_path)
    except Exception as e:
        print(f"Warning: Error getting last modified time: {e}")
        last_modified = 0.0
    
    # Default metadata
    metadata = {
        "name": os.path.basename(sf2_path).replace('.sf2', ''),
        "author": "Unknown",
        "description": "",
        "instrument_type": "unknown",
        "mapped_notes": MappedNotes().to_dict(),
        "polyphony": 32,
        "sample_rate": 44100,
        "bit_depth": 16,
        "size_mb": round(size_mb, 2),
        "hash": file_hash,
        "last_modified": last_modified
    }
    
    try:
        # Load SF2 file with sf2utils
        with open(sf2_path, 'rb') as sf2_file:
            sf2 = Sf2File(sf2_file)
            
            # Extract basic information with careful attribute checking
            
            # Name
            bank_name = None
            if hasattr(sf2.info, 'bank_name'):
                bank_name = decode_safely(sf2.info.bank_name)
            if bank_name and bank_name.strip():
                metadata["name"] = bank_name
            
            # Author - check different possible attribute names
            author = None
            for attr in ['engineers', 'copyright', 'manufacturer']:
                if hasattr(sf2.info, attr):
                    author = decode_safely(safe_get_attr(sf2.info, attr))
                    if author and author.strip():
                        metadata["author"] = author
                        break
            
            # Comments/description
            if hasattr(sf2.info, 'comment'):
                comment = decode_safely(sf2.info.comment)
                if comment and comment.strip():
                    metadata["description"] = comment
            
            # Analyze presets to determine instrument type
            try:
                instrument_types = set()
                if hasattr(sf2, 'presets'):
                    for preset in sf2.presets:
                        # Check if preset has a name attribute
                        if hasattr(preset, 'name'):
                            # Extract preset name that usually contains the instrument type
                            preset_name = decode_safely(preset.name)
                            # Categorize based on name
                            inferred_type = infer_instrument_type(preset_name)
                            if inferred_type:
                                instrument_types.add(inferred_type)
                
                # If multiple types were found, use "multi" or the most common
                if instrument_types:
                    metadata["instrument_type"] = "multi" if len(instrument_types) > 1 else next(iter(instrument_types))
            except Exception as e:
                print(f"Warning: Error analyzing preset information: {e}")
            
            # Note mapping analysis
            try:
                mapped_notes = analyze_note_mapping(sf2)
                metadata["mapped_notes"] = mapped_notes.to_dict()
            except Exception as e:
                print(f"Warning: Error analyzing note mapping: {e}")
            
            # Extract sample rate from samples
            try:
                if hasattr(sf2, 'samples'):
                    sample_rates = set()
                    for sample in sf2.samples:
                        if hasattr(sample, 'sample_rate'):
                            sample_rates.add(sample.sample_rate)
                    
                    if sample_rates:
                        metadata["sample_rate"] = max(sample_rates)
            except Exception as e:
                print(f"Warning: Error extracting sample rate: {e}")
            
            # Check bit depth
            try:
                if hasattr(sf2, 'samples'):
                    bit_depths = set()
                    for sample in sf2.samples:
                        # sf2utils doesn't directly provide bit_depth, so we infer from data
                        if hasattr(sample, 'bit_depth'):
                            bit_depths.add(sample.bit_depth)
                    
                    if bit_depths:
                        metadata["bit_depth"] = max(bit_depths)
            except Exception as e:
                print(f"Warning: Error checking bit depth: {e}")
            
            # Estimate polyphony based on instruments and zones
            try:
                polyphony = estimate_polyphony(sf2)
                metadata["polyphony"] = polyphony
            except Exception as e:
                print(f"Warning: Error estimating polyphony: {e}")
    
    except Exception as e:
        print(f"Warning: Error extracting SF2 metadata: {e}")
        # Fall back to default metadata if extraction fails
    
    return metadata

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

'''
def analyze_note_mapping(sf2: Sf2File) -> MappedNotes:
    """
    Analyze the note mapping in an SF2 file.
    
    Args:
        sf2: Loaded Sf2File object
        
    Returns:
        MappedNotes object with min_note, max_note and missing_notes
    """
    covered_notes = set()
    
    try:
        # Primeiro, verificar os presets e seus bags
        if hasattr(sf2, 'presets') and sf2.presets:
            for preset in sf2.presets:
                if hasattr(preset, 'bags') and preset.bags:
                    for bag_idx, bag in enumerate(preset.bags):
                        key_range = None
                        
                        # Verificar se o bag tem geradores
                        if hasattr(bag, 'gens') and bag.gens:
                            for gen in bag.gens:
                                if hasattr(gen, 'oper') and gen.oper == 43:  # keyRange
                                    key_range = gen.val
                                    break
                        
                        # Se encontrou um key range
                        if key_range and hasattr(key_range, 'lo') and hasattr(key_range, 'hi'):
                            # Adicionar todas as notas neste range
                            for note in range(key_range.lo, key_range.hi + 1):
                                if 0 <= note <= 127:
                                    covered_notes.add(note)
        
        # Segundo, verificar instrumentos e seus bags
        if (not covered_notes) and hasattr(sf2, 'instruments') and sf2.instruments:
            for instr in sf2.instruments:
                if hasattr(instr, 'bags') and instr.bags:
                    for bag in instr.bags:
                        key_range = None
                        
                        if hasattr(bag, 'gens') and bag.gens:
                            for gen in bag.gens:
                                if hasattr(gen, 'oper') and gen.oper == 43:  # keyRange
                                    key_range = gen.val
                                    break
                        
                        if key_range and hasattr(key_range, 'lo') and hasattr(key_range, 'hi'):
                            for note in range(key_range.lo, key_range.hi + 1):
                                if 0 <= note <= 127:
                                    covered_notes.add(note)
        
        # Terceiro, verificar as amostras diretamente
        if (not covered_notes) and hasattr(sf2, 'samples') and sf2.samples:
            for sample in sf2.samples:
                if hasattr(sample, 'original_key') and 0 <= sample.original_key <= 127:
                    covered_notes.add(sample.original_key)
                if hasattr(sample, 'original_pitch') and 0 <= sample.original_pitch <= 127:
                    covered_notes.add(sample.original_pitch)
    
    except Exception as e:
        print(f"Error in note mapping analysis: {e}")
    
    # Se nenhuma nota foi detectada, use um intervalo padrão com base no tipo de instrumento
    if not covered_notes:
        # Tente inferir um range padrão baseado nos nomes dos presets
        instrument_type = "unknown"
        try:
            if hasattr(sf2, 'presets') and sf2.presets:
                for preset in sf2.presets:
                    if hasattr(preset, 'name'):
                        preset_name = decode_safely(preset.name)
                        instrument_type = infer_instrument_type(preset_name)
                        if instrument_type != "unknown":
                            break
        except:
            pass
        
        # Defina intervalos padrão por tipo de instrumento
        if "bass" in instrument_type.lower():
            # Baixo: tipicamente E1 até G4
            for note in range(28, 67):  # E1=28, G4=67
                covered_notes.add(note)
        elif "guitar" in instrument_type.lower():
            # Guitarra: típica E2 até E6
            for note in range(40, 88):  # E2=40, E6=88
                covered_notes.add(note)
        elif "piano" in instrument_type.lower():
            # Piano: A0 até C8
            for note in range(21, 108):  # A0=21, C8=108
                covered_notes.add(note)
        elif "brass" in instrument_type.lower() or "wind" in instrument_type.lower():
            # Metais/sopro: F2 até F6
            for note in range(41, 89):  # F2=41, F6=89
                covered_notes.add(note)
        elif "drum" in instrument_type.lower() or "percussion" in instrument_type.lower():
            # Percussão: toda a faixa de MIDI
            for note in range(0, 128):
                covered_notes.add(note)
        else:
            # Padrão: C1 até C7
            for note in range(36, 96):  # C1=36, C7=96
                covered_notes.add(note)
    
    # Determine min and max note
    min_note_midi = min(covered_notes) if covered_notes else 0
    max_note_midi = max(covered_notes) if covered_notes else 127
    
    min_note = MIDI_TO_NOTE.get(min_note_midi, "C0")
    max_note = MIDI_TO_NOTE.get(max_note_midi, "C8")
    
    # Determine missing notes in range
    all_possible_notes = set(range(min_note_midi, max_note_midi + 1))
    missing_midi_notes = all_possible_notes - covered_notes
    missing_notes = [MIDI_TO_NOTE.get(n, f"Unknown-{n}") for n in missing_midi_notes]
    
    return MappedNotes(
        min_note=min_note,
        max_note=max_note,
        missing_notes=missing_notes
    )
'''

def analyze_note_mapping(sf2: Sf2File) -> MappedNotes:
    """
    Analyze the note mapping in an SF2 file with improved detection.
    
    Args:
        sf2: Loaded Sf2File object
        
    Returns:
        MappedNotes object with min_note, max_note and missing_notes
    """
    covered_notes = set()
    
    try:
        # First, check instrument key ranges (often more reliable source)
        instruments_found = False
        if hasattr(sf2, 'instruments') and sf2.instruments:
            for instr in sf2.instruments:
                if hasattr(instr, 'name') and instr.name:  # Skip unnamed instruments (often terminator)
                    instr_name = decode_safely(instr.name)
                    if instr_name == "EOI":  # End of instruments marker
                        continue
                        
                    if hasattr(instr, 'bags') and instr.bags:
                        instruments_found = True
                        for bag_idx, bag in enumerate(instr.bags):
                            key_range = None
                            
                            # Check if bag has generators
                            if hasattr(bag, 'gens') and bag.gens:
                                for gen in bag.gens:
                                    if hasattr(gen, 'oper') and gen.oper == 43:  # keyRange
                                        key_range = gen.val
                                        break
                            
                            # If key range found
                            if key_range and hasattr(key_range, 'lo') and hasattr(key_range, 'hi'):
                                # Add all notes in this range
                                for note in range(key_range.lo, key_range.hi + 1):
                                    if 0 <= note <= 127:
                                        covered_notes.add(note)
        
        # Second, check preset key ranges if no instruments found
        if not covered_notes and hasattr(sf2, 'presets') and sf2.presets:
            for preset in sf2.presets:
                if hasattr(preset, 'name') and preset.name:
                    preset_name = decode_safely(preset.name)
                    if preset_name == "EOP":  # End of presets marker
                        continue
                        
                    if hasattr(preset, 'bags') and preset.bags:
                        for bag_idx, bag in enumerate(preset.bags):
                            key_range = None
                            
                            # Check if bag has generators
                            if hasattr(bag, 'gens') and bag.gens:
                                for gen in bag.gens:
                                    if hasattr(gen, 'oper') and gen.oper == 43:  # keyRange
                                        key_range = gen.val
                                        break
                            
                            # If key range found
                            if key_range and hasattr(key_range, 'lo') and hasattr(key_range, 'hi'):
                                # Add all notes in this range
                                for note in range(key_range.lo, key_range.hi + 1):
                                    if 0 <= note <= 127:
                                        covered_notes.add(note)
        
        # Third, check the samples directly (fallback)
        if not covered_notes and hasattr(sf2, 'samples') and sf2.samples:
            for sample in sf2.samples:
                if hasattr(sample, 'sample_name') and sample.sample_name:
                    sample_name = decode_safely(sample.sample_name)
                    if sample_name == "EOS":  # End of samples marker
                        continue
                
                # Check for original key
                if hasattr(sample, 'original_key') and 0 <= sample.original_key <= 127:
                    covered_notes.add(sample.original_key)
                
                # Check for original pitch (alternative name in some implementations)
                if hasattr(sample, 'original_pitch') and 0 <= sample.original_pitch <= 127:
                    covered_notes.add(sample.original_pitch)
                    
                # Try to infer range from sample loops
                # Many soundfonts use looped samples that cover multiple notes
                if (hasattr(sample, 'sample_rate') and sample.sample_rate > 0 and 
                    hasattr(sample, 'start_loop') and hasattr(sample, 'end_loop')):
                    
                    # The presence of loops often indicates a playable sample
                    # We'll add a small range around the original key as a fallback
                    if hasattr(sample, 'original_key') and 0 <= sample.original_key <= 127:
                        base_note = sample.original_key
                        # Add a basic range of +/- 12 semitones (one octave) around the original key
                        for note in range(max(0, base_note - 12), min(127, base_note + 12) + 1):
                            covered_notes.add(note)
    
    except Exception as e:
        print(f"Error in note mapping analysis: {e}")
    
    # If all detection methods failed, try a more aggressive approach
    if not covered_notes:
        # Analyze instrument/preset names to detect instrument type
        instrument_type = "unknown"
        try:
            # First check instrument names
            if hasattr(sf2, 'instruments') and sf2.instruments:
                for instr in sf2.instruments:
                    if hasattr(instr, 'name') and instr.name:
                        instr_name = decode_safely(instr.name)
                        detected_type = infer_instrument_type(instr_name)
                        if detected_type != "unknown":
                            instrument_type = detected_type
                            break
            
            # If no type found, check preset names
            if instrument_type == "unknown" and hasattr(sf2, 'presets') and sf2.presets:
                for preset in sf2.presets:
                    if hasattr(preset, 'name') and preset.name:
                        preset_name = decode_safely(preset.name)
                        detected_type = infer_instrument_type(preset_name)
                        if detected_type != "unknown":
                            instrument_type = detected_type
                            break
        except:
            pass
        
        # If the SF2 has samples but we couldn't detect key ranges,
        # assume it's a full-range instrument (rare for a soundfont to have just one note)
        if hasattr(sf2, 'samples') and len(sf2.samples) > 0:
            # Define ranges by instrument type as fallback
            if "bass" in instrument_type.lower():
                # Bass: typically E1 to G4
                for note in range(28, 68):  # E1=28, G4=67
                    covered_notes.add(note)
            elif "guitar" in instrument_type.lower():
                # Guitar: typical E2 to E6
                for note in range(40, 89):  # E2=40, E6=88
                    covered_notes.add(note)
            elif "piano" in instrument_type.lower():
                # Piano: A0 to C8
                for note in range(21, 109):  # A0=21, C8=108
                    covered_notes.add(note)
            elif "brass" in instrument_type.lower() or "wind" in instrument_type.lower():
                # Brass/wind: F2 to F6
                for note in range(41, 90):  # F2=41, F6=89
                    covered_notes.add(note)
            elif "drum" in instrument_type.lower() or "percussion" in instrument_type.lower():
                # Percussion: full MIDI range
                for note in range(0, 128):
                    covered_notes.add(note)
            elif "synth" in instrument_type.lower() or "pad" in instrument_type.lower():
                # Synths and pads: C2 to C7
                for note in range(36, 96):  # C2=36, C7=96
                    covered_notes.add(note)
            else:
                # Default: C1 to C7 (standard keyboard range)
                for note in range(36, 96):  # C1=36, C7=96
                    covered_notes.add(note)
    
    # If still no notes found, use a conservative default range
    if not covered_notes:
        # Default range: just assuming C3 to C5 as minimum playable range for any instrument
        for note in range(48, 73):  # C3=48, C5=72
            covered_notes.add(note)
    
    # Determine min and max note
    min_note_midi = min(covered_notes) if covered_notes else 0
    max_note_midi = max(covered_notes) if covered_notes else 127
    
    min_note = MIDI_TO_NOTE.get(min_note_midi, "C0")
    max_note = MIDI_TO_NOTE.get(max_note_midi, "C8")
    
    # For debugging
    #print(f"Note range: {min_note} - {max_note}, total notes: {len(covered_notes)}")
    
    # Check for anomalous results - if min and max are identical and it's C4, 
    # it's likely our detection failed and defaulted somewhere
    if min_note == max_note and min_note == "C4" and len(sf2.samples) > 0:
        # Force a more reasonable range based on the number of samples
        num_samples = len(sf2.samples)
        if num_samples >= 10:
            # With many samples, assume a wide range (C2-C6)
            min_note_midi = 36  # C2
            max_note_midi = 84  # C6
            min_note = "C2"
            max_note = "C6"
            covered_notes = set(range(min_note_midi, max_note_midi + 1))
        else:
            # Fewer samples, assume narrower range (C3-C5)
            min_note_midi = 48  # C3
            max_note_midi = 72  # C5
            min_note = "C3"
            max_note = "C5"
            covered_notes = set(range(min_note_midi, max_note_midi + 1))
    
    # Determine missing notes in range
    all_possible_notes = set(range(min_note_midi, max_note_midi + 1))
    missing_midi_notes = all_possible_notes - covered_notes
    missing_notes = [MIDI_TO_NOTE.get(n, f"Unknown-{n}") for n in missing_midi_notes]
    
    return MappedNotes(
        min_note=min_note,
        max_note=max_note,
        missing_notes=missing_notes
    )

def estimate_polyphony(sf2: Sf2File) -> int:
    """
    Estimate polyphony based on number of instruments and zones.
    
    Args:
        sf2: Loaded Sf2File object
        
    Returns:
        Estimated polyphony value
    """
    # Contagem de amostras
    num_samples = len(sf2.samples) if hasattr(sf2, 'samples') else 0
    
    # Contagem de instrumentos
    num_instruments = len(sf2.instruments) if hasattr(sf2, 'instruments') else 0
    
    # Calcular uma pontuação para estimar a polifonia
    score = num_samples * 0.7 + num_instruments * 0.3
    
    # Classificar com base na pontuação
    if score <= 10:
        return 32
    elif score <= 30:
        return 64
    else:
        return 128  # Grande soundfonts geralmente suportam 128 vozes

def infer_instrument_type(preset_name: str) -> str:
    """
    Infer instrument type based on preset name.
    
    Args:
        preset_name: Preset name
        
    Returns:
        Inferred instrument type
    """
    preset_name = preset_name.lower()
    
    # Dictionary of keywords to instrument types
    instrument_keywords = {
        "piano": "piano",
        "grand": "piano",
        "upright": "piano",
        "keyboard": "keyboard",
        "organ": "organ",
        "guitar": "guitar",
        "bass": "bass",
        "string": "strings",
        "violin": "strings",
        "cello": "strings",
        "viola": "strings",
        "contrabass": "strings",
        "drum": "drums",
        "kit": "drums",
        "percussion": "percussion",
        "horn": "brass",
        "trumpet": "brass",
        "trombone": "brass",
        "tuba": "brass",
        "brass": "brass",
        "saxophone": "woodwind",
        "sax": "woodwind",
        "flute": "woodwind",
        "clarinet": "woodwind",
        "oboe": "woodwind",
        "woodwind": "woodwind",
        "synth": "synthesizer",
        "pad": "synthesizer",
        "lead": "synthesizer",
        "sfx": "effects",
        "effect": "effects",
        "choir": "vocal",
        "voice": "vocal",
        "vocal": "vocal",
        "rhodes": "keyboard",
        "wurlitzer": "keyboard",
        "mellotron": "keyboard",
        "clavi": "keyboard",
        "epiano": "keyboard",
        "e-piano": "keyboard",
        "electric piano": "keyboard",
        "electric bass": "bass",
        "acoustic bass": "bass",
        "orch": "orchestral",
        "ensemble": "ensemble",
        "orchestra": "orchestral",
        "marimba": "percussion",
        "vibraphone": "percussion",
        "xylophone": "percussion",
        "cymbal": "percussion",
        "harp": "harp",
        "mallet": "percussion"        
    }
    
    # Check if any keyword is in the preset name
    for keyword, instrument_type in instrument_keywords.items():
        if keyword in preset_name:
            return instrument_type
    
    # Look for additional clues in the filename
    basename = os.path.basename(preset_name)
    for keyword, instrument_type in instrument_keywords.items():
        if keyword in basename:
            return instrument_type
    
    return "unknown"

def analyze_timbre(sf2_path: str, midi_test_file: Optional[str] = None) -> Dict:
    """
    Analyze the timbre of a soundfont using acoustic features.
    
    Args:
        sf2_path: Path to the .sf2 file
        midi_test_file: MIDI test file path (optional)
        
    Returns:
        Dictionary with timbre characteristics
    """
    # Default timbre characteristics in case analysis fails
    default_timbre = {
        "brightness": "medium",
        "richness": "medium",
        "attack": "medium",
        "harmonic_quality": "balanced",
        "spectral_centroid": 0.0,
        "spectral_bandwidth": 0.0,
        "spectral_rolloff": 0.0,
        "zero_crossing_rate": 0.0,
        "mfcc_features": [0.0] * 13
    }
    
    try:
        from sound_test import test_soundfont
        
        # Gerar um arquivo WAV com o teste de som
        temp_dir = tempfile.mkdtemp()
        wav_path = os.path.join(temp_dir, "timbre_analysis.wav")
        
        success, actual_wav_path = test_soundfont(sf2_path, False, wav_path)
        
        if not success or not actual_wav_path:
            print("Warning: Failed to generate test audio for timbre analysis")
            return default_timbre
        
        # Load the WAV file with librosa
        try:
            y, sr = librosa.load(actual_wav_path, sr=None)
            
            # Verifique se o áudio contém dados reais
            if len(y) == 0 or np.all(y == 0):
                print("Warning: Generated audio file is empty or silent")
                return default_timbre
            
            # Extract timbre features
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y).mean()
            
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_means = mfccs.mean(axis=1)
            
            # Analyze harmonicity
            harmonics = librosa.effects.harmonic(y)
            percussive = librosa.effects.percussive(y)
            harmonic_ratio = np.sum(harmonics**2) / (np.sum(percussive**2) + 1e-8)
            
            # Classify features
            brightness = map_value_to_category(spectral_centroid, 
                                             [500, 1500, 3000], 
                                             ["dark", "medium", "bright", "very bright"])
            
            richness = map_value_to_category(spectral_bandwidth,
                                          [500, 1500, 3000],
                                          ["simple", "medium", "rich", "very rich"])
            
            attack_quality = map_value_to_category(zero_crossing_rate * 10000,
                                                [50, 150, 300],
                                                ["soft", "medium", "hard", "aggressive"])
            
            harmonic_quality = map_value_to_category(harmonic_ratio,
                                                  [0.5, 2, 5],
                                                  ["percussive", "balanced", "harmonic", "very harmonic"])
            
            return {
                "brightness": brightness,
                "richness": richness,
                "attack": attack_quality,
                "harmonic_quality": harmonic_quality,
                "spectral_centroid": float(spectral_centroid),
                "spectral_bandwidth": float(spectral_bandwidth),
                "spectral_rolloff": float(spectral_rolloff),
                "zero_crossing_rate": float(zero_crossing_rate),
                "mfcc_features": [float(x) for x in mfcc_means]
            }
        
        except Exception as e:
            print(f"Warning: Error in audio analysis: {e}")
            
    except Exception as e:
        print(f"Warning: Error in timbre analysis: {e}")
    
    finally:
        # Clean up temp directory
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
    
    # Return default values if analysis fails
    return default_timbre


def map_value_to_category(value: float, thresholds: List[float], categories: List[str]) -> str:
    """
    Map a value to a category based on thresholds.
    
    Args:
        value: Numeric value
        thresholds: List of thresholds
        categories: List of categories (must have len(thresholds) + 1 elements)
        
    Returns:
        Category corresponding to the value
    """
    for i, threshold in enumerate(thresholds):
        if value < threshold:
            return categories[i]
    return categories[-1]

def create_test_midi(output_file: str = "") -> str:
    """
    Create a test MIDI file with a sequence of notes
    spanning different frequency ranges.
    
    Args:
        output_file: Output file path (optional, will create temp file if not provided)
        
    Returns:
        Path to the created MIDI file
    """
    # Criar um arquivo temporário se não for especificado
    if not output_file:
        fd, output_file = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
    
    try:
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)  # Piano
        
        # Define a sequence of notes to test different register parts
        test_sequence = [
            # Low frequencies
            {"note": 36, "start": 0.0, "end": 0.5, "velocity": 100},     # C2
            {"note": 40, "start": 0.5, "end": 1.0, "velocity": 100},     # E2
            {"note": 43, "start": 1.0, "end": 1.5, "velocity": 100},     # G2
            
            # Mid frequencies
            {"note": 60, "start": 1.5, "end": 2.0, "velocity": 100},     # C4
            {"note": 64, "start": 2.0, "end": 2.5, "velocity": 100},     # E4
            {"note": 67, "start": 2.5, "end": 3.0, "velocity": 100},     # G4
            
            # High frequencies
            {"note": 84, "start": 3.0, "end": 3.5, "velocity": 100},     # C6
            {"note": 88, "start": 3.5, "end": 4.0, "velocity": 100},     # E6
            {"note": 91, "start": 4.0, "end": 4.5, "velocity": 100},     # G6
            
            # Final chord
            {"note": 48, "start": 4.5, "end": 6.0, "velocity": 100},     # C3
            {"note": 52, "start": 4.5, "end": 6.0, "velocity": 100},     # E3
            {"note": 55, "start": 4.5, "end": 6.0, "velocity": 100},     # G3
            {"note": 60, "start": 4.5, "end": 6.0, "velocity": 100},     # C4
        ]
        
        # Add notes to the instrument
        for note_info in test_sequence:
            note = pretty_midi.Note(
                velocity=note_info["velocity"], 
                pitch=note_info["note"], 
                start=note_info["start"], 
                end=note_info["end"]
            )
            instrument.notes.append(note)
        
        # Add the instrument to the MIDI
        midi.instruments.append(instrument)
        
        # Save the MIDI file
        midi.write(output_file)
        
        return output_file
    
    except Exception as e:
        print(f"Warning: Error creating test MIDI: {e}")
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass
        return ""

def generate_tag_suggestions(metadata: Dict) -> List[str]:
    """
    Generate tag suggestions based on metadata.
    
    Args:
        metadata: Dictionary with soundfont metadata
        
    Returns:
        List of suggested tags
    """
    tags = set()
    
    # Add instrument type as tag
    if "instrument_type" in metadata and metadata["instrument_type"]:
        tags.add(metadata["instrument_type"])
    
    # Add timbre characteristics
    if "timbre" in metadata:
        timbre_info = metadata.get("timbre", {})
        if isinstance(timbre_info, dict):
            for key, value in timbre_info.items():
                if key in ["brightness", "richness", "attack", "harmonic_quality"] and value:
                    tags.add(value)
        elif isinstance(timbre_info, str):
            # Split timbre description into words and add as tags
            for word in timbre_info.lower().split():
                if len(word) > 3:  # Ignore very short words
                    tags.add(word)
    
    # Add quality as tag
    if "quality" in metadata and metadata["quality"]:
        tags.add(metadata["quality"])
    
    # Add genres as tags
    if "genre" in metadata and metadata["genre"]:
        for genre in metadata["genre"]:
            if genre:
                tags.add(genre)
    
    # Add name-based tags
    if "name" in metadata and metadata["name"]:
        name = metadata["name"].lower()
        # Check for common instruments in the name
        instruments = ["piano", "guitar", "bass", "drum", "synth", "strings", "brass", "organ"]
        for instrument in instruments:
            if instrument in name:
                tags.add(instrument)
    
    # Convert to list and sort
    return sorted(list(tags))

def suggest_genres(timbre_info: Dict) -> List[str]:
    """
    Suggest musical genres based on timbre characteristics.
    
    Args:
        timbre_info: Dictionary with timbre information
        
    Returns:
        List of suggested genres
    """
    genres = []
    
    # Simple mapping of characteristics to genres
    if timbre_info.get("brightness") == "bright" and timbre_info.get("attack") == "hard":
        genres.extend(["rock", "metal", "electronic"])
    
    if timbre_info.get("brightness") == "dark" and timbre_info.get("harmonic_quality") == "harmonic":
        genres.extend(["classical", "jazz", "ambient"])
    
    if timbre_info.get("richness") == "rich" and timbre_info.get("harmonic_quality") == "harmonic":
        genres.extend(["classical", "orchestral", "film"])
    
    if timbre_info.get("attack") == "soft" and timbre_info.get("harmonic_quality") == "harmonic":
        genres.extend(["ambient", "new age", "chill"])
    
    if timbre_info.get("brightness") == "medium" and timbre_info.get("attack") == "medium":
        genres.extend(["pop", "folk", "world"])
    
    if timbre_info.get("harmonic_quality") == "percussive":
        genres.extend(["percussion", "hip hop", "electronic"])
    
    # Some other common combinations
    if timbre_info.get("brightness") == "dark" and timbre_info.get("attack") == "soft":
        genres.extend(["ambient", "chill"])
    
    if timbre_info.get("brightness") == "bright" and timbre_info.get("richness") == "simple":
        genres.extend(["electronic", "techno"])
    
    # Make sure we always have at least one genre
    if not genres:
        genres = ["versatile"]
    
    # Remove duplicates and sort
    return sorted(list(set(genres)))

def suggest_quality(metadata: Dict) -> str:
    """
    Suggest the quality of a soundfont based on its metadata.
    
    Args:
        metadata: Dictionary with soundfont metadata
        
    Returns:
        Suggested quality: 'high', 'medium' or 'low'
    """
    # Factors that influence quality
    factors = {
        "size": 0,        # File size
        "sample_rate": 0, # Sample rate
        "bit_depth": 0,   # Bit depth
        "coverage": 0     # Note coverage
    }
    
    # Size evaluation
    size_mb = metadata.get("size_mb", 0)
    if size_mb > 30:
        factors["size"] = 2  # High
    elif size_mb > 10:
        factors["size"] = 1  # Medium
    else:
        factors["size"] = 0  # Low
    
    # Sample rate evaluation
    sample_rate = metadata.get("sample_rate", 0)
    if sample_rate >= 44100:
        factors["sample_rate"] = 2  # High
    elif sample_rate >= 22050:
        factors["sample_rate"] = 1  # Medium
    else:
        factors["sample_rate"] = 0  # Low
    
    # Bit depth evaluation
    bit_depth = metadata.get("bit_depth", 0)
    if bit_depth >= 24:
        factors["bit_depth"] = 2  # High
    elif bit_depth >= 16:
        factors["bit_depth"] = 1  # Medium
    else:
        factors["bit_depth"] = 0  # Low
    
    # Note coverage evaluation
    mapped_notes = metadata.get("mapped_notes", {})
    if isinstance(mapped_notes, dict):
        missing_notes = mapped_notes.get("missing_notes", [])
        if len(missing_notes) < 5:
            factors["coverage"] = 2  # High
        elif len(missing_notes) < 20:
            factors["coverage"] = 1  # Medium
        else:
            factors["coverage"] = 0  # Low
    
    # Calculate total score
    total_score = sum(factors.values())
    max_score = 8  # Maximum possible score
    
    # Determine quality based on percentage of maximum score
    percentage = total_score / max_score if max_score > 0 else 0
    if percentage >= 0.7:
        return "high"
    elif percentage >= 0.4:
        return "medium"
    else:
        return "low"

def test_note_range(soundfont_path: str, output_dir: Optional[str] = None) -> Tuple[str, str, List[int]]:
    """
    Test a soundfont by playing notes across the MIDI range to detect playable notes.
    
    Args:
        soundfont_path: Path to the .sf2 file
        output_dir: Directory to save test files (optional)
        
    Returns:
        Tuple of (min_note, max_note, list of missing notes)
    """
    import tempfile
    import os
    from sound_test import simplified_midi_for_test
    from fluidsynth_helper import run_fluidsynth
    
    # Create a temporary directory for MIDI and WAV files
    if output_dir:
        temp_dir = output_dir
        os.makedirs(temp_dir, exist_ok=True)
    else:
        temp_dir = tempfile.mkdtemp()
    
    # Notes to test across the range (C1 to C7)
    # We'll test notes at different octaves to find the range
    test_notes = [
        # Bass register
        24,  # C1
        36,  # C2
        # Middle register
        48,  # C3
        60,  # C4 (middle C)
        # High register
        72,  # C5
        84,  # C6
        96   # C7
    ]
    
    # Test additional notes if we find the extremes of the range
    extended_bass = [26, 28, 29, 31, 33, 35]  # D1 to B1
    extended_treble = [86, 88, 89, 91, 93, 95]  # D6 to B6
    
    # Dictionary to track which notes are playable
    playable_notes = {}
    
    print(f"\nTesting note range for {os.path.basename(soundfont_path)}...")
    
    # Test each note
    for note in test_notes:
        note_name = MIDI_TO_NOTE.get(note, f"Unknown-{note}")
        midi_path = os.path.join(temp_dir, f"note_{note}.mid")
        wav_path = os.path.join(temp_dir, f"note_{note}.wav")
        
        # Create a simple MIDI file with a single note
        create_single_note_midi(midi_path, note)
        
        # Render to WAV using FluidSynth
        success = run_fluidsynth(soundfont_path, midi_path, wav_path)
        
        # Check if the WAV file was created and has content
        if success and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
            # Additional check: analyze the WAV to confirm it's not silent
            if not is_silent_wav(wav_path):
                playable_notes[note] = True
                print(f"  ✓ Note {note_name} (MIDI {note}) is playable")
            else:
                playable_notes[note] = False
                print(f"  ✗ Note {note_name} (MIDI {note}) is silent")
        else:
            playable_notes[note] = False
            print(f"  ✗ Note {note_name} (MIDI {note}) is not playable")
    
    # If C1 is playable, test lower notes
    if playable_notes.get(24, False):
        for note in [12, 16, 19, 21]:  # C0, E0, G0, A0
            note_name = MIDI_TO_NOTE.get(note, f"Unknown-{note}")
            midi_path = os.path.join(temp_dir, f"note_{note}.mid")
            wav_path = os.path.join(temp_dir, f"note_{note}.wav")
            
            create_single_note_midi(midi_path, note)
            success = run_fluidsynth(soundfont_path, midi_path, wav_path)
            
            if success and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                if not is_silent_wav(wav_path):
                    playable_notes[note] = True
                    print(f"  ✓ Note {note_name} (MIDI {note}) is playable")
                else:
                    playable_notes[note] = False
                    print(f"  ✗ Note {note_name} (MIDI {note}) is silent")
            else:
                playable_notes[note] = False
                print(f"  ✗ Note {note_name} (MIDI {note}) is not playable")
    
    # If C7 is playable, test higher notes
    if playable_notes.get(96, False):
        for note in [100, 103, 108]:  # E7, G7, C8
            note_name = MIDI_TO_NOTE.get(note, f"Unknown-{note}")
            midi_path = os.path.join(temp_dir, f"note_{note}.mid")
            wav_path = os.path.join(temp_dir, f"note_{note}.wav")
            
            create_single_note_midi(midi_path, note)
            success = run_fluidsynth(soundfont_path, midi_path, wav_path)
            
            if success and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                if not is_silent_wav(wav_path):
                    playable_notes[note] = True
                    print(f"  ✓ Note {note_name} (MIDI {note}) is playable")
                else:
                    playable_notes[note] = False
                    print(f"  ✗ Note {note_name} (MIDI {note}) is silent")
            else:
                playable_notes[note] = False
                print(f"  ✗ Note {note_name} (MIDI {note}) is not playable")
    
    # Determine the min and max playable notes
    playable_midi_notes = [note for note, is_playable in playable_notes.items() if is_playable]
    
    if playable_midi_notes:
        min_midi = min(playable_midi_notes)
        max_midi = max(playable_midi_notes)
        
        min_note = MIDI_TO_NOTE.get(min_midi, f"Unknown-{min_midi}")
        max_note = MIDI_TO_NOTE.get(max_midi, f"Unknown-{max_midi}")
        
        # Find missing notes within the range
        all_notes_in_range = set(range(min_midi, max_midi + 1))
        missing_notes = []
        
        # Test a sample of notes within the range to detect missing notes
        test_within_range = []
        step = 3 if (max_midi - min_midi) > 24 else 1
        for note in range(min_midi, max_midi + 1, step):
            if note not in playable_midi_notes:
                test_within_range.append(note)
        
        # Test the additional notes
        for note in test_within_range:
            note_name = MIDI_TO_NOTE.get(note, f"Unknown-{note}")
            midi_path = os.path.join(temp_dir, f"note_{note}.mid")
            wav_path = os.path.join(temp_dir, f"note_{note}.wav")
            
            create_single_note_midi(midi_path, note)
            success = run_fluidsynth(soundfont_path, midi_path, wav_path)
            
            if success and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                if not is_silent_wav(wav_path):
                    playable_notes[note] = True
                    print(f"  ✓ Note {note_name} (MIDI {note}) is playable")
                else:
                    missing_notes.append(note)
                    print(f"  ✗ Note {note_name} (MIDI {note}) is silent")
            else:
                missing_notes.append(note)
                print(f"  ✗ Note {note_name} (MIDI {note}) is not playable")
        
        # Update the min/max based on all tests
        playable_midi_notes = [note for note, is_playable in playable_notes.items() if is_playable]
        min_midi = min(playable_midi_notes)
        max_midi = max(playable_midi_notes)
        
        min_note = MIDI_TO_NOTE.get(min_midi, f"Unknown-{min_midi}")
        max_note = MIDI_TO_NOTE.get(max_midi, f"Unknown-{max_midi}")
        
        print(f"\nPlayable range: {min_note} (MIDI {min_midi}) to {max_note} (MIDI {max_midi})")
        
        # Convert missing MIDI notes to note names
        missing_note_names = [MIDI_TO_NOTE.get(n, f"Unknown-{n}") for n in sorted(missing_notes)]
        
        if missing_note_names:
            print(f"Missing notes: {', '.join(missing_note_names)}")
        else:
            print("No missing notes detected within the range.")
        
        return min_note, max_note, missing_note_names
    else:
        print("No playable notes detected.")
        return "C4", "C4", []  # Default fallback
    
    # Clean up temporary files if needed
    if not output_dir:
        import shutil
        shutil.rmtree(temp_dir)

