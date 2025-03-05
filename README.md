# Soundfont Management System

A comprehensive Python system for managing, analyzing, and utilizing soundfonts in MIDI projects.

## Overview

This system provides a complete suite of tools for working with soundfont (SF2) files, including:

- **Automatic extraction** of technical metadata directly from SF2 files
- **Acoustic analysis** for automated timbre classification
- **Efficient indexing system** for searching and filtering
- **Advanced API** for soundfont selection and management
- **Integrated music generation** with MIDI and soundfonts
- **Interactive annotator** for soundfont categorization with manual data entry support
- **Robust compatibility** with different SF2 formats and versions

## System Components

### 1. `soundfont_utils.py`
Utilities for soundfont processing and analysis:

- Automatic metadata extraction using `sf2utils`
- Acoustic analysis with `librosa` for timbre classification
- Robust handling of different sf2utils implementations
- Proper escaping of paths with special characters
- Automatic suggestion of tags, genres, and quality ratings

### 2. `soundfont_manager.py`
Core API for managing your soundfont library:

- Efficient storage and indexing
- Advanced search system (text, tags, type, quality)
- Similar soundfont recommendations
- Collection statistics
- CSV export/import

### 3. `sf_annotator.py`
Advanced soundfont annotator with command-line interface:

- Automatic technical metadata extraction
- Timbre analysis with test playback
- Multiple operation modes (basic, full, interactive)
- Support for manual data entry with `--insert-data`
- Recursive directory scanning
- English interface and robust error handling
- Defensive attribute checking for compatibility with all sf2utils versions
- Debug mode with detailed error information
- Periodic saving for large collections

### 4. `midi_soundfont_player.py`
System for music generation and playback:

- Compositions in different styles (pop, rock, jazz, classical)
- Creation of chord progressions, melodies, bass lines, and drum patterns
- Integration with FluidSynth for playback
- Intelligent soundfont selection

### 5. `sound_test.py`
Utility for testing soundfonts:

- Generation of test MIDI patterns
- Rendering of audio with FluidSynth
- Cross-platform audio playback

### 6. `fluidsynth_helper.py`
Helper module for FluidSynth integration:

- Auto-detection of available audio drivers
- Cross-platform compatibility
- Simplified interface for playback and rendering

## System Requirements

### General Requirements
- **Python**: 3.8 or higher
- **FluidSynth**: 2.0 or higher (required for audio playback)
- **Operating System**: Linux, macOS, or Windows

### Python Packages
Install the dependencies:

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install sf2utils>=1.0.0
pip install pretty_midi>=0.2.9
pip install librosa>=0.9.2
pip install colorama>=0.4.4
pip install numpy>=1.20.0
pip install typing_extensions>=4.0.0
```

### FluidSynth Installation

- **Linux**:
  ```bash
  sudo apt-get install fluidsynth
  ```

- **macOS**:
  ```bash
  brew install fluidsynth
  ```

- **Windows**:
  - Download the installer from the [official website](https://www.fluidsynth.org/)
  - Or use Chocolatey: `choco install fluidsynth`
  - Add to system PATH

## Basic Usage

### Soundfont Annotator

```bash
# Basic usage
python sf_annotator.py --directory soundfonts --output library.json

# Interactive mode with manual data entry
python sf_annotator.py --directory soundfonts --output library.json --mode interactive



# Batch processing with manual entry for each soundfont
python sf_annotator.py --directory soundfonts --output library.json --insert-data

# Recursive scanning with forced reanalysis
python sf_annotator.py --directory soundfonts --output library.json --recursive --force

# For the most accurate (but resource-intensive) detection of note ranges, use the `--test-note-range` parameter
python sf_annotator.py --directory soundfonts --output library.json --recursive --test-note-range

# Test playback during annotation
python sf_annotator.py --directory soundfonts --output library.json --play

# Debug mode for detailed error information
python sf_annotator.py --directory soundfonts --output library.json --debug

# Faster processing (without timbre analysis)
python sf_annotator.py --directory soundfonts --output library.json --no-timbre-analysis

# Processing large collections with periodic saving
python sf_annotator.py --directory soundfonts --output library.json --recursive --batch-size 20

# Complete set of options for detailed annotation
python sf_annotator.py --directory soundfonts --output library.json --mode interactive --recursive --insert-data --play --test-note-range
```

### Soundfont Management via API

```python
from soundfont_manager import SoundfontManager

# Initialize the manager
manager = SoundfontManager("soundfonts.json", "path/to/soundfonts")

# Scan a directory for soundfonts
added = manager.scan_directory("soundfonts", recursive=True)
print(f"Added {len(added)} soundfonts")

# Text search
results = manager.search("piano jazz")

# Filtering by tags
piano_soundfonts = manager.get_soundfonts_by_tags(["piano", "acoustic"])

# Advanced filtering
high_quality = manager.filter_soundfonts(quality="high", 
                                        instrument_type="piano")

# Random soundfont with filter
random_sf = manager.get_random_soundfont(
    lambda sf: sf.quality == "high" and "orchestra" in sf.tags
)

# Collection statistics
stats = manager.get_statistics()
print(f"Total soundfonts: {stats['total_soundfonts']}")
print(f"Total size: {stats['total_size_mb']:.2f} MB")
```

### Music Generation

```python
from soundfont_manager import SoundfontManager
from midi_soundfont_player import MusicGenerator, ScaleType

# Initialize the manager and generator
manager = SoundfontManager("soundfonts.json", "path/to/soundfonts")
generator = MusicGenerator(manager)

# Generate a composition
midi_file = generator.generate_composition(
    key="C",
    scale_type=ScaleType.MINOR,
    tempo=120.0,
    num_measures=8,
    style="jazz",
    output_file="composition.mid"
)

# Play with specific soundfont
generator.play_composition_with_soundfont(
    midi_file=midi_file,
    soundfont_id=5
)

# Play with filtered soundfont selection
generator.play_composition_with_soundfont(
    midi_file=midi_file,
    instrument_type="piano",
    quality="high",
    tags=["acoustic", "bright"]
)
```

### Command-line Music Generation and Playback

```bash
# List all available soundfonts
python midi_soundfont_player.py --db soundfonts.json --sf-dir soundfonts --list-soundfonts

# Generate a jazz composition in F minor
python midi_soundfont_player.py --db soundfonts.json --sf-dir soundfonts --key F --scale minor --style jazz --output jazz_composition.mid

# Generate and play with a specific soundfont
python midi_soundfont_player.py --db soundfonts.json --sf-dir soundfonts --sf-id 3 --style rock

# Generate and play with filtered soundfonts
python midi_soundfont_player.py --db soundfonts.json --sf-dir soundfonts --instrument-type piano --quality high --tags "bright,acoustic"
```

## Example Usage

The `soundfont_usage_example.py` script provides example usage of the system:

```bash
# Run all examples
python soundfont_usage_example.py

# Run a specific example
python soundfont_usage_example.py 1  # Adding soundfonts
python soundfont_usage_example.py 2  # Searching and filtering
python soundfont_usage_example.py 3  # Generating music
python soundfont_usage_example.py 4  # Playing with soundfonts
python soundfont_usage_example.py 5  # Exporting and importing data
```

## Advanced Features

### Timbre Analysis

The system analyzes soundfonts using digital signal processing to extract characteristics such as:

- Brightness (spectral centroid)
- Richness (spectral bandwidth)
- Attack quality (zero-crossing rate)
- Harmonic quality (harmony/percussiveness ratio)

This enables intelligent soundfont categorization and selection.

### Note Mapping Analysis

The system automatically analyzes the note mapping in soundfonts, including:

- Minimum and maximum playable notes
- Missing notes in the range
- Appropriate instrument range detection

### Similarity Recommendation

The `get_similar_soundfonts()` method provides recommendations based on:

- Instrument type similarity
- Timbre characteristics
- Tag and genre overlap
- Quality metrics

### Quality Assessment

Soundfonts are automatically assessed for quality based on:

- File size (larger files often have better samples)
- Sample rate and bit depth
- Note coverage completeness
- Timbre characteristics

## Contributions

Contributions are welcome! Please open an issue to discuss significant changes.

## License

This project is available under the MIT License.
