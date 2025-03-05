#!/usr/bin/env python3
"""
Example of using the soundfont management system.
This script demonstrates the main functionalities of the system.
"""

import os
import sys
from colorama import Fore, Style, init

# Import system modules
from soundfont_utils import extract_sf2_metadata, analyze_timbre, generate_tag_suggestions
from soundfont_manager import SoundfontManager
from midi_soundfont_player import MusicGenerator, ScaleType, Chord

# Initialize Colorama
init(autoreset=True)

def print_header(text):
    """Prints a formatted header."""
    print("\n" + Fore.YELLOW + "=" * 60)
    print(Fore.YELLOW + f" {text}")
    print(Fore.YELLOW + "=" * 60 + Style.RESET_ALL)

def print_section(text):
    """Prints a formatted section title."""
    print("\n" + Fore.CYAN + "-" * 40)
    print(Fore.CYAN + f" {text}")
    print(Fore.CYAN + "-" * 40 + Style.RESET_ALL)

def example_add_soundfonts():
    """Demonstrates how to add soundfonts to the database."""
    print_header("Example 1: Adding Soundfonts")
    
    # Create a temporary directory for the example
    os.makedirs("exemplo_db", exist_ok=True)
    
    # Initialize the manager
    manager = SoundfontManager("exemplo_db/soundfonts.json", "soundfonts")
    
    print_section("Scanning directory for soundfonts")
    
    # Check if there is an example directory with soundfonts
    if os.path.exists("soundfonts"):
        # Scan the directory
        print(f"Scanning directory 'soundfonts'...")
        added = manager.scan_directory("soundfonts", recursive=True)
        
        if added:
            print(Fore.GREEN + f"Added {len(added)} soundfonts to the database!")
            
            # Show statistics
            stats = manager.get_statistics()
            print("\nCollection statistics:")
            print(f"Total soundfonts: {stats['total_soundfonts']}")
            print(f"Total size: {stats['total_size_mb']:.2f} MB")
            
            # Show instrument types found
            print("\nInstrument types:")
            for inst_type, count in list(stats['instrument_types'].items())[:5]:
                print(f"  {inst_type}: {count}")
        else:
            print(Fore.YELLOW + "No soundfonts found in the directory.")
            
            # Create an example manually
            print_section("Creating example soundfont manually")
            
            # Add an example soundfont
            from soundfont_utils import SoundfontMetadata, MappedNotes
            
            sf = SoundfontMetadata(
                id=1,
                name="Example Piano",
                path="piano_example.sf2",
                timbre="bright and rich",
                tags=["piano", "acoustic", "bright"],
                instrument_type="piano",
                quality="high",
                genre=["classical", "jazz"],
                mapped_notes=MappedNotes(min_note="A0", max_note="C8", missing_notes=[]),
                polyphony=128,
                sample_rate=44100,
                bit_depth=16,
                size_mb=25.4,
                license="Creative Commons",
                author="Example Author",
                description="An example piano for demonstration."
            )
            
            manager.soundfonts.append(sf)
            manager._build_indices()
            manager.save_soundfonts()
            
            print(Fore.GREEN + "Example soundfont added successfully!")
    else:
        print(Fore.YELLOW + "Directory 'soundfonts' not found. Creating example soundfont manually.")
        
        # Add an example soundfont
        from soundfont_utils import SoundfontMetadata, MappedNotes
        
        sf = SoundfontMetadata(
            id=1,
            name="Example Piano",
            path="piano_example.sf2",
            timbre="bright and rich",
            tags=["piano", "acoustic", "bright"],
            instrument_type="piano",
            quality="high",
            genre=["classical", "jazz"],
            mapped_notes=MappedNotes(min_note="A0", max_note="C8", missing_notes=[]),
            polyphony=128,
            sample_rate=44100,
            bit_depth=16,
            size_mb=25.4,
            license="Creative Commons",
            author="Example Author",
            description="An example piano for demonstration."
        )
        
        manager.soundfonts.append(sf)
        manager._build_indices()
        manager.save_soundfonts()
        
        print(Fore.GREEN + "Example soundfont added successfully!")

def example_search_soundfonts():
    """Demonstrates how to search and filter soundfonts."""
    print_header("Example 2: Searching and Filtering Soundfonts")
    
    # Initialize the manager
    manager = SoundfontManager("exemplo_db/soundfonts.json", "soundfonts")
    
    # Check how many soundfonts we have
    all_soundfonts = manager.get_all_soundfonts()
    print(f"Database contains {len(all_soundfonts)} soundfonts.")
    
    if not all_soundfonts:
        print(Fore.YELLOW + "No soundfonts found. Run example 1 first.")
        return
    
    print_section("Text Search")
    
    # Text search
    search_term = "piano"
    results = manager.search(search_term)
    print(f"Search for '{search_term}' found {len(results)} results:")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id})")
    
    print_section("Filter by Instrument Type")
    
    # Filter by instrument type
    instrument_type = "piano"
    results = manager.get_soundfonts_by_instrument_type(instrument_type)
    print(f"Soundfonts of type '{instrument_type}': {len(results)}")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id}, Quality: {sf.quality})")
    
    print_section("Filter by Quality")
    
    # Filter by quality
    quality = "high"
    results = manager.get_soundfonts_by_quality(quality)
    print(f"Soundfonts with quality '{quality}': {len(results)}")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id}, Type: {sf.instrument_type})")
    
    print_section("Filter by Tags")
    
    # Filter by tags
    tags = ["acoustic"]
    results = manager.get_soundfonts_by_tags(tags)
    print(f"Soundfonts with tag '{tags[0]}': {len(results)}")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id}, Tags: {', '.join(sf.tags)})")
    
    print_section("Filter by Genre")
    
    # Filter by genre
    genre = "classical"
    results = manager.get_soundfonts_by_genre(genre)
    print(f"Soundfonts associated with genre '{genre}': {len(results)}")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id}, Genres: {', '.join(sf.genre)})")
    
    print_section("Advanced Filter")
    
    # Advanced filter
    filters = {
        "quality": "high",
        "mapped_notes.min_note": "A0"
    }
    results = manager.filter_soundfonts(**filters)
    print(f"Soundfonts with advanced filters: {len(results)}")
    for sf in results:
        print(f"  - {sf.name} (ID: {sf.id}, Min: {sf.mapped_notes.min_note}, Max: {sf.mapped_notes.max_note})")
    
    print_section("Random Soundfont")
    
    # Get a random soundfont
    random_sf = manager.get_random_soundfont()
    if random_sf:
        print(f"Random soundfont: {random_sf.name} (ID: {random_sf.id})")
        print(f"  Type: {random_sf.instrument_type}")
        print(f"  Quality: {random_sf.quality}")
        print(f"  Tags: {', '.join(random_sf.tags)}")
        print(f"  Genres: {', '.join(random_sf.genre)}")

def example_generate_music():
    """Demonstrates how to generate music using soundfonts."""
    print_header("Example 3: Generating Music with Soundfonts")
    
    # Initialize the manager
    manager = SoundfontManager("exemplo_db/soundfonts.json", "soundfonts")
    
    # Initialize the music generator
    generator = MusicGenerator(manager)
    
    # Parameters for the composition
    key = "C"
    scale_type = ScaleType.MAJOR
    tempo = 100
    measures = 4
    style = "pop"
    output_file = "example_composition.mid"
    
    print_section("Generating Composition")
    
    print(f"Key: {key}")
    print(f"Scale: {scale_type.value}")
    print(f"Tempo: {tempo} BPM")
    print(f"Measures: {measures}")
    print(f"Style: {style}")
    
    try:
        # Generate the composition
        midi_file = generator.generate_composition(
            key=key,
            scale_type=scale_type,
            tempo=tempo,
            num_measures=measures,
            style=style,
            output_file=output_file
        )
        
        print(Fore.GREEN + f"\nComposition generated successfully: {midi_file}")
        
        print_section("Composition Details")
        
        print("The composition contains:")
        print("- Melody generated from the scale")
        print("- Chord progression typical of the chosen style")
        print("- Bass line following the chords")
        print("- Drum pattern suitable for the style")
        
        print("\nYou can play the MIDI file using:")
        print(f"  - A common MIDI player")
        print(f"  - FluidSynth with a soundfont: fluidsynth -a alsa path/to/soundfont.sf2 {output_file}")
        print(f"  - The system itself: python midi_soundfont_player.py -d exemplo_db/soundfonts.json --sf-dir soundfonts -o {output_file}")
        
    except Exception as e:
        print(Fore.RED + f"Error generating composition: {e}")

def example_play_with_soundfont():
    """Demonstrates how to play music with soundfonts."""
    print_header("Example 4: Playing Music with Soundfonts")
    
    # Initialize the manager
    manager = SoundfontManager("exemplo_db/soundfonts.json", "soundfonts")
    
    # Initialize the music generator
    generator = MusicGenerator(manager)
    
    # Get a random soundfont
    sf = manager.get_random_soundfont()
    
    if not sf:
        print(Fore.YELLOW + "No soundfonts found. Run example 1 first.")
        return
    
    print_section("Soundfont Information")
    
    print(f"Name: {sf.name}")
    print(f"ID: {sf.id}")
    print(f"Type: {sf.instrument_type}")
    print(f"Quality: {sf.quality}")
    print(f"Tags: {', '.join(sf.tags)}")
    print(f"Genres: {', '.join(sf.genre)}")
    
    print_section("Playback with Soundfont")
    
    print("To play a composition with this soundfont, use:")
    print(f"  python midi_soundfont_player.py -d exemplo_db/soundfonts.json --sf-dir soundfonts --sf-id {sf.id}")
    
    print("\nTo filter soundfonts by characteristics:")
    print(f"  python midi_soundfont_player.py -d exemplo_db/soundfonts.json --sf-dir soundfonts --quality high --instrument-type piano")
    
    print("\nTo generate a composition with a specific style:")
    print(f"  python midi_soundfont_player.py -d exemplo_db/soundfonts.json --sf-dir soundfonts --style jazz --key F")

def example_export_import():
    """Demonstrates how to export and import soundfonts."""
    print_header("Example 5: Exporting and Importing Data")
    
    # Initialize the manager
    manager = SoundfontManager("exemplo_db/soundfonts.json", "soundfonts")
    
    # Check how many soundfonts we have
    all_soundfonts = manager.get_all_soundfonts()
    
    if not all_soundfonts:
        print(Fore.YELLOW + "No soundfonts found. Run example 1 first.")
        return
    
    print_section("Exporting to CSV")
    
    # Export to CSV
    csv_file = "exemplo_db/soundfonts_export.csv"
    manager.export_csv(csv_file)
    print(Fore.GREEN + f"Data exported to {csv_file}")
    
    print_section("Collection Statistics")
    
    # Get statistics
    stats = manager.get_statistics()
    print(f"Total soundfonts: {stats['total_soundfonts']}")
    print(f"Total size: {stats['total_size_mb']:.2f} MB")
    print(f"Average size: {stats['avg_size_mb']:.2f} MB")
    
    # Show quality distribution
    print("\nQuality distribution:")
    for quality, count in stats['quality_distribution'].items():
        print(f"  {quality}: {count}")
    
    # Show top tags
    print("\nMost common tags:")
    for tag, count in list(stats['tags'].items())[:5]:
        print(f"  {tag}: {count}")
    
    print_section("Importing from CSV")
    
    # Demonstrate how to import
    print("To import back from CSV, you would use:")
    print(f"  imported_soundfonts = manager.import_csv('{csv_file}')")
    print("  print(f'Imported {imported_soundfonts} soundfonts.')")
    
    # Do not execute the actual import to avoid duplicates    
    print(Fore.YELLOW + "\nImport not executed to avoid data duplication.")

def main():
    """Main function that runs the examples."""
    print(Fore.GREEN + """
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │   Soundfont Management System                   │
    │   Usage Examples                                │
    │                                                 │
    └─────────────────────────────────────────────────┘
    """)
    
    # Check if the user wants to run a specific example
    if len(sys.argv) > 1:
        try:
            example_num = int(sys.argv[1])
            if example_num == 1:
                example_add_soundfonts()
            elif example_num == 2:
                example_search_soundfonts()
            elif example_num == 3:
                example_generate_music()
            elif example_num == 4:
                example_play_with_soundfont()
            elif example_num == 5:
                example_export_import()
            else:
                print(Fore.RED + f"Example {example_num} not found.")
        except ValueError:
            print(Fore.RED + "Invalid argument. Use a number from 1 to 5.")
    else:
        # Run all examples
        example_add_soundfonts()
        example_search_soundfonts()
        example_generate_music()
        example_play_with_soundfont()
        example_export_import()
    
    print(Fore.GREEN + "\nExamples completed!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nExamples interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"Error during example execution: {e}")
        sys.exit(1)
