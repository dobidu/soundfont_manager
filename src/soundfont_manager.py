import os
import json
import random
import shlex
from typing import List, Dict, Optional, Union, Callable, Any, Set, Tuple
from dataclasses import asdict
import pretty_midi
from functools import lru_cache
from collections import defaultdict
import numpy as np

# Importa o módulo de utilidades
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

class SoundfontManager:
    """
    Advanced soundfont manager with support for indexing, search,
    filtering and classification.
    """
    
    def __init__(self, json_path: str, sf2_directory: Optional[str] = None):
        """
        Initialize the soundfont manager.
        
        Args:
            json_path: Path to the JSON file with soundfonts.
            sf2_directory: Base directory where .sf2 files are stored.
                          If not provided, paths in JSON are assumed to be absolute.
        """
        self.json_path = json_path
        self.sf2_directory = sf2_directory
        self.soundfonts = []
        self.next_id = 1
        self.indices = {
            "id": {},
            "name": defaultdict(list),
            "tags": defaultdict(list),
            "instrument_type": defaultdict(list),
            "quality": defaultdict(list),
            "genre": defaultdict(list),
            "author": defaultdict(list),
            "timbre_brightness": defaultdict(list),
            "timbre_richness": defaultdict(list),
            "timbre_attack": defaultdict(list),
            "timbre_harmonic": defaultdict(list)
        }
        
        # Load soundfonts
        self.load_soundfonts()
    
    def load_soundfonts(self) -> None:
        """
        Load soundfonts from the JSON file and build indices.
        """
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Convert to SoundfontMetadata objects
                self.soundfonts = []
                for item in data:
                    # Check for mapped_notes information
                    mapped_notes = item.get("mapped_notes", {})
                    if mapped_notes:
                        mapped_notes_obj = MappedNotes(
                            min_note=mapped_notes.get("min_note", "C0"),
                            max_note=mapped_notes.get("max_note", "C8"),
                            missing_notes=mapped_notes.get("missing_notes", [])
                        )
                    else:
                        mapped_notes_obj = MappedNotes()
                    
                    # Create SoundfontMetadata object
                    sf = SoundfontMetadata(
                        id=item.get("id", 0),
                        name=item.get("name", ""),
                        path=item.get("path", ""),
                        timbre=item.get("timbre", ""),
                        tags=item.get("tags", []),
                        instrument_type=item.get("instrument_type", ""),
                        quality=item.get("quality", "medium"),
                        genre=item.get("genre", []),
                        mapped_notes=mapped_notes_obj,
                        polyphony=item.get("polyphony", 0),
                        sample_rate=item.get("sample_rate", 44100),
                        bit_depth=item.get("bit_depth", 16),
                        size_mb=item.get("size_mb", 0.0),
                        license=item.get("license", ""),
                        author=item.get("author", ""),
                        description=item.get("description", ""),
                        hash=item.get("hash", ""),
                        last_modified=item.get("last_modified", 0.0)
                    )
                    
                    self.soundfonts.append(sf)
                    
                    # Update next available ID
                    if sf.id >= self.next_id:
                        self.next_id = sf.id + 1
                
                # Build indices for quick search
                self._build_indices()
                
            except Exception as e:
                print(f"Error loading JSON file: {e}")
                self.soundfonts = []
        else:
            print(f"JSON file not found: {self.json_path}. Starting with empty database.")
            self.soundfonts = []
    
    def _build_indices(self) -> None:
        """
        Build indices for quick search.
        """
        # Clear indices
        self.indices = {
            "id": {},
            "name": defaultdict(list),
            "tags": defaultdict(list),
            "instrument_type": defaultdict(list),
            "quality": defaultdict(list),
            "genre": defaultdict(list),
            "author": defaultdict(list),
            "timbre_brightness": defaultdict(list),
            "timbre_richness": defaultdict(list),
            "timbre_attack": defaultdict(list),
            "timbre_harmonic": defaultdict(list)
        }
        
        # Populate indices
        for sf in self.soundfonts:
            # Index by ID
            self.indices["id"][sf.id] = sf
            
            # Index by name (keywords)
            if sf.name:
                for word in sf.name.lower().split():
                    if len(word) > 2:  # Ignore very short words
                        self.indices["name"][word].append(sf)
            
            # Index by tags
            for tag in sf.tags:
                self.indices["tags"][tag.lower()].append(sf)
            
            # Index by instrument type
            if sf.instrument_type:
                self.indices["instrument_type"][sf.instrument_type.lower()].append(sf)
            
            # Index by quality
            if sf.quality:
                self.indices["quality"][sf.quality.lower()].append(sf)
            
            # Index by genre
            for genre in sf.genre:
                self.indices["genre"][genre.lower()].append(sf)
            
            # Index by author
            if sf.author:
                self.indices["author"][sf.author.lower()].append(sf)
            
            # Indices by timbre characteristics
            if isinstance(sf.timbre, dict):
                # If timbre is a dictionary of characteristics
                brightness = sf.timbre.get("brightness", "")
                if brightness:
                    self.indices["timbre_brightness"][brightness].append(sf)
                
                richness = sf.timbre.get("richness", "")
                if richness:
                    self.indices["timbre_richness"][richness].append(sf)
                
                attack = sf.timbre.get("attack", "")
                if attack:
                    self.indices["timbre_attack"][attack].append(sf)
                
                harmonic = sf.timbre.get("harmonic_quality", "")
                if harmonic:
                    self.indices["timbre_harmonic"][harmonic].append(sf)
    
    def save_soundfonts(self) -> None:
        """
        Save soundfonts to the JSON file.
        """
        try:
            # Convert objects to dictionaries
            data = [sf.to_dict() for sf in self.soundfonts]
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.json_path)), exist_ok=True)
            
            # Save to JSON file
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error saving soundfonts: {e}")
            raise
    
    def add_soundfont(self, sf2_path: str, auto_analyze: bool = True, save: bool = True) -> SoundfontMetadata:
        """
        Add a new soundfont to the database.
        
        Args:
            sf2_path: Path to the .sf2 file
            auto_analyze: If True, automatically extract metadata and analyze timbre
            save: If True, save the database after adding
            
        Returns:
            SoundfontMetadata object of the added soundfont
        """
        # Check if file exists
        if not os.path.exists(sf2_path):
            raise FileNotFoundError(f"File not found: {sf2_path}")
        
        # Check if soundfont already exists by path
        rel_path = self._get_relative_path(sf2_path)
        for sf in self.soundfonts:
            if sf.path == rel_path:
                print(f"Soundfont already exists: {rel_path}")
                return sf
        
        # Extract technical metadata automatically
        metadata = {}
        if auto_analyze:
            try:
                # Extract metadata from SF2 file
                metadata = extract_sf2_metadata(sf2_path)
                
                # Analyze timbre
                timbre_info = analyze_timbre(sf2_path)
                metadata["timbre"] = timbre_info
                
                # Suggest tags
                if "tags" not in metadata or not metadata["tags"]:
                    metadata["tags"] = generate_tag_suggestions(metadata)
                
                # Suggest genres
                if "genre" not in metadata or not metadata["genre"]:
                    metadata["genre"] = suggest_genres(timbre_info)
                
                # Suggest quality
                if "quality" not in metadata or not metadata["quality"]:
                    metadata["quality"] = suggest_quality(metadata)
            
            except Exception as e:
                print(f"Error in automatic analysis: {e}")
        
        # Create SoundfontMetadata object
        mapped_notes = metadata.get("mapped_notes", {})
        if mapped_notes:
            mapped_notes_obj = MappedNotes(
                min_note=mapped_notes.get("min_note", "C0"),
                max_note=mapped_notes.get("max_note", "C8"),
                missing_notes=mapped_notes.get("missing_notes", [])
            )
        else:
            mapped_notes_obj = MappedNotes()
        
        # Check for size explicitly
        if "size_mb" not in metadata or metadata["size_mb"] <= 0:
            try:
                size_mb = os.path.getsize(sf2_path) / (1024 * 1024)
                metadata["size_mb"] = round(size_mb, 2)
            except:
                metadata["size_mb"] = 0.0
        
        sf = SoundfontMetadata(
            id=self.next_id,
            name=metadata.get("name", os.path.basename(sf2_path).replace('.sf2', '')),
            path=rel_path,
            timbre=metadata.get("timbre", ""),
            tags=metadata.get("tags", []),
            instrument_type=metadata.get("instrument_type", ""),
            quality=metadata.get("quality", "medium"),
            genre=metadata.get("genre", []),
            mapped_notes=mapped_notes_obj,
            polyphony=metadata.get("polyphony", 32),
            sample_rate=metadata.get("sample_rate", 44100),
            bit_depth=metadata.get("bit_depth", 16),
            size_mb=metadata.get("size_mb", 0.0),
            license=metadata.get("license", ""),
            author=metadata.get("author", ""),
            description=metadata.get("description", ""),
            hash=metadata.get("hash", ""),
            last_modified=metadata.get("last_modified", 0.0)
        )
        
        # Add to database
        self.soundfonts.append(sf)
        self.next_id += 1
        
        # Update indices
        self._build_indices()
        
        # Save database
        if save:
            self.save_soundfonts()
        
        return sf
    
    def _get_relative_path(self, sf2_path: str) -> str:
        """
        Convert an absolute path to a path relative to the base directory.
        
        Args:
            sf2_path: Absolute path to the .sf2 file
            
        Returns:
            Path relative to the base directory
        """
        if not self.sf2_directory:
            return sf2_path
        
        # Normalize paths
        sf2_path = os.path.normpath(os.path.abspath(sf2_path))
        base_dir = os.path.normpath(os.path.abspath(self.sf2_directory))
        
        # Check if path is within base directory
        if sf2_path.startswith(base_dir):
            return os.path.relpath(sf2_path, base_dir)
        else:
            return sf2_path
    
    def get_absolute_path(self, sf: Union[SoundfontMetadata, str, int]) -> str:
        """
        Get the absolute path of a soundfont.
        
        Args:
            sf: SoundfontMetadata object, ID, or relative path
            
        Returns:
            Absolute path to the .sf2 file
        """
        # If it's a SoundfontMetadata object
        if isinstance(sf, SoundfontMetadata):
            rel_path = sf.path
        # If it's an ID
        elif isinstance(sf, int):
            sf_obj = self.get_soundfont_by_id(sf)
            if not sf_obj:
                raise ValueError(f"Soundfont not found with ID: {sf}")
            rel_path = sf_obj.path
        # If it's a path
        else:
            rel_path = sf
        
        # If no base directory, assume path is already absolute
        if not self.sf2_directory:
            return rel_path
        
        # Combine base directory with relative path
        return os.path.normpath(os.path.join(self.sf2_directory, rel_path))
    
    def update_soundfont(self, sf_id: int, **kwargs) -> Optional[SoundfontMetadata]:
        """
        Update an existing soundfont.
        
        Args:
            sf_id: ID of the soundfont to update
            **kwargs: Attributes to update
            
        Returns:
            Updated SoundfontMetadata object or None if not found
        """
        sf = self.get_soundfont_by_id(sf_id)
        if not sf:
            print(f"Soundfont not found with ID: {sf_id}")
            return None
        
        # Update attributes
        for key, value in kwargs.items():
            if hasattr(sf, key):
                setattr(sf, key, value)
        
        # Update indices
        self._build_indices()
        
        # Save database
        self.save_soundfonts()
        
        return sf
    
    def remove_soundfont(self, sf_id: int) -> bool:
        """
        Remove a soundfont from the database.
        
        Args:
            sf_id: ID of the soundfont to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        sf = self.get_soundfont_by_id(sf_id)
        if not sf:
            print(f"Soundfont not found with ID: {sf_id}")
            return False
        
        # Remove the soundfont
        self.soundfonts = [s for s in self.soundfonts if s.id != sf_id]
        
        # Update indices
        self._build_indices()
        
        # Save database
        self.save_soundfonts()
        
        return True
    
    def get_soundfont_by_id(self, sf_id: int) -> Optional[SoundfontMetadata]:
        """
        Get a soundfont by ID.
        
        Args:
            sf_id: ID of the soundfont
            
        Returns:
            SoundfontMetadata object or None if not found
        """
        return self.indices["id"].get(sf_id)
    
    def get_all_soundfonts(self) -> List[SoundfontMetadata]:
        """
        Get all soundfonts.
        
        Returns:
            List of SoundfontMetadata objects
        """
        return list(self.soundfonts)
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[SoundfontMetadata]:
        """
        Search soundfonts by keywords in multiple fields.
        
        Args:
            query: Search terms
            fields: List of fields to search (if None, search all fields)
            
        Returns:
            List of matching soundfonts
        """
        if not query:
            return self.get_all_soundfonts()
        
        # Default fields to search
        default_fields = ["name", "tags", "instrument_type", "genre", "author", "description"]
        
        # Use specified fields or default
        fields_to_search = fields if fields else default_fields
        
        # Normalize query
        query_terms = query.lower().split()
        
        # Set to store unique results
        results_set = set()
        
        for term in query_terms:
            for field in fields_to_search:
                if field == "name" and "name" in self.indices:
                    for key, items in self.indices["name"].items():
                        if term in key:
                            results_set.update(items)
                
                elif field == "tags" and "tags" in self.indices:
                    for key, items in self.indices["tags"].items():
                        if term in key:
                            results_set.update(items)
                
                elif field == "instrument_type" and "instrument_type" in self.indices:
                    for key, items in self.indices["instrument_type"].items():
                        if term in key:
                            results_set.update(items)
                
                elif field == "genre" and "genre" in self.indices:
                    for key, items in self.indices["genre"].items():
                        if term in key:
                            results_set.update(items)
                
                elif field == "author" and "author" in self.indices:
                    for key, items in self.indices["author"].items():
                        if term in key:
                            results_set.update(items)
                
                elif field == "description":
                    # Direct search in description field
                    for sf in self.soundfonts:
                        if term in sf.description.lower():
                            results_set.add(sf)
        
        # Convert set to list
        return list(results_set)
    
    def filter_soundfonts(self, **filters) -> List[SoundfontMetadata]:
        """
        Filter soundfonts based on specific criteria.
        
        Args:
            **filters: Filters in the format field=value or field__operator=value
                      Supported operators: eq, ne, lt, lte, gt, gte, in, contains
            
        Returns:
            List of filtered soundfonts
        """
        results = self.soundfonts.copy()
        
        for key, value in filters.items():
            # Check if there's an operator
            if "__" in key:
                field, operator = key.split("__", 1)
            else:
                field, operator = key, "eq"
            
            # Filter results
            results = self._apply_filter(results, field, operator, value)
        
        return results
    
    def _apply_filter(self, soundfonts: List[SoundfontMetadata], field: str, operator: str, value: Any) -> List[SoundfontMetadata]:
        """
        Apply a filter to a list of soundfonts.
        
        Args:
            soundfonts: List of soundfonts
            field: Field to filter
            operator: Comparison operator
            value: Value to compare
            
        Returns:
            Filtered list of soundfonts
        """
        filtered = []
        
        for sf in soundfonts:
            # Get field value
            if field == "mapped_notes.min_note":
                field_value = sf.mapped_notes.min_note
            elif field == "mapped_notes.max_note":
                field_value = sf.mapped_notes.max_note
            elif field == "mapped_notes.missing_notes":
                field_value = sf.mapped_notes.missing_notes
            elif field.startswith("timbre.") and isinstance(sf.timbre, dict):
                subfield = field.split(".", 1)[1]
                field_value = sf.timbre.get(subfield, None)
            else:
                field_value = getattr(sf, field, None)
            
            # Apply operator
            if operator == "eq" and field_value == value:
                filtered.append(sf)
            elif operator == "ne" and field_value != value:
                filtered.append(sf)
            elif operator == "lt" and field_value < value:
                filtered.append(sf)
            elif operator == "lte" and field_value <= value:
                filtered.append(sf)
            elif operator == "gt" and field_value > value:
                filtered.append(sf)
            elif operator == "gte" and field_value >= value:
                filtered.append(sf)
            elif operator == "in" and field_value in value:
                filtered.append(sf)
            elif operator == "contains" and value in field_value:
                filtered.append(sf)
            elif operator == "startswith" and isinstance(field_value, str) and field_value.startswith(value):
                filtered.append(sf)
            elif operator == "endswith" and isinstance(field_value, str) and field_value.endswith(value):
                filtered.append(sf)
            elif operator == "has_tag" and value.lower() in [tag.lower() for tag in sf.tags]:
                filtered.append(sf)
            elif operator == "has_genre" and value.lower() in [genre.lower() for genre in sf.genre]:
                filtered.append(sf)
        
        return filtered
    
    def get_soundfonts_by_tags(self, tags: List[str], match_all: bool = False) -> List[SoundfontMetadata]:
        """
        Get soundfonts that match a list of tags.
        
        Args:
            tags: List of tags
            match_all: If True, return soundfonts that have all tags;
                      if False, return soundfonts that have at least one tag
            
        Returns:
            List of matching soundfonts
        """
        if not tags:
            return []
        
        # Normalize tags
        norm_tags = [tag.lower() for tag in tags]
        
        results = set()
        tag_matches = {}
        
        # Count how many tags each soundfont has
        for tag in norm_tags:
            for sf in self.indices["tags"].get(tag, []):
                if sf not in tag_matches:
                    tag_matches[sf] = 0
                tag_matches[sf] += 1
        
        # Filter based on match_all criterion
        for sf, count in tag_matches.items():
            if match_all and count == len(norm_tags):
                results.add(sf)
            elif not match_all and count > 0:
                results.add(sf)
        
        return list(results)
    
    def get_soundfonts_by_instrument_type(self, instrument_type: str) -> List[SoundfontMetadata]:
        """
        Get soundfonts of a specific instrument type.
        
        Args:
            instrument_type: Instrument type
            
        Returns:
            List of matching soundfonts
        """
        norm_type = instrument_type.lower()
        return self.indices["instrument_type"].get(norm_type, [])
    
    def get_soundfonts_by_genre(self, genre: str) -> List[SoundfontMetadata]:
        """
        Get soundfonts associated with a musical genre.
        
        Args:
            genre: Musical genre
            
        Returns:
            List of matching soundfonts
        """
        norm_genre = genre.lower()
        return self.indices["genre"].get(norm_genre, [])
    
    def get_soundfonts_by_quality(self, quality: str) -> List[SoundfontMetadata]:
        """
        Get soundfonts of a specific quality.
        
        Args:
            quality: Quality (high, medium, low)
            
        Returns:
            List of matching soundfonts
        """
        norm_quality = quality.lower()
        return self.indices["quality"].get(norm_quality, [])
    
    def get_soundfonts_by_timbre(self, timbre_attribute: str, value: str) -> List[SoundfontMetadata]:
        """
        Get soundfonts with a specific timbre characteristic.
        
        Args:
            timbre_attribute: Timbre attribute (brightness, richness, attack, harmonic_quality)
            value: Attribute value
            
        Returns:
            List of matching soundfonts
        """
        index_key = f"timbre_{timbre_attribute}"
        if index_key not in self.indices:
            print(f"Timbre attribute not indexed: {timbre_attribute}")
            return []
        
        return self.indices[index_key].get(value.lower(), [])
    
    def get_random_soundfont(self, filter_func: Optional[Callable[[SoundfontMetadata], bool]] = None) -> Optional[SoundfontMetadata]:
        """
        Get a random soundfont.
        
        Args:
            filter_func: Optional function to filter soundfonts
            
        Returns:
            A random SoundfontMetadata object or None if no soundfonts
        """
        if not self.soundfonts:
            return None
        
        if filter_func:
            filtered = [sf for sf in self.soundfonts if filter_func(sf)]
            if not filtered:
                return None
            return random.choice(filtered)
        else:
            return random.choice(self.soundfonts)
    
    def get_similar_soundfonts(self, sf_id: int, limit: int = 5) -> List[SoundfontMetadata]:
        """
        Find soundfonts similar to a specific soundfont.
        
        Args:
            sf_id: ID of the reference soundfont
            limit: Maximum number of results
            
        Returns:
            List of similar soundfonts
        """
        sf = self.get_soundfont_by_id(sf_id)
        if not sf:
            print(f"Soundfont not found with ID: {sf_id}")
            return []
        
        # Calculate similarity score for each soundfont
        similarity_scores = []
        
        for other_sf in self.soundfonts:
            if other_sf.id == sf_id:
                continue
            
            score = self._calculate_similarity(sf, other_sf)
            similarity_scores.append((other_sf, score))
        
        # Sort by score and return top N
        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        return [sf for sf, score in similarity_scores[:limit]]
    
    def _calculate_similarity(self, sf1: SoundfontMetadata, sf2: SoundfontMetadata) -> float:
        """
        Calculate similarity between two soundfonts.
        
        Args:
            sf1: First soundfont
            sf2: Second soundfont
            
        Returns:
            Similarity score (0-1)
        """
        score = 0.0
        
        # Similarity by instrument type
        if sf1.instrument_type == sf2.instrument_type:
            score += 0.3
        
        # Similarity by tags
        common_tags = set(sf1.tags).intersection(set(sf2.tags))
        score += 0.2 * (len(common_tags) / max(len(sf1.tags) + len(sf2.tags), 1))
        
        # Similarity by genre
        common_genres = set(sf1.genre).intersection(set(sf2.genre))
        score += 0.2 * (len(common_genres) / max(len(sf1.genre) + len(sf2.genre), 1))
        
        # Similarity by timbre
        if isinstance(sf1.timbre, dict) and isinstance(sf2.timbre, dict):
            # Compare categorical timbre characteristics
            timbre_attrs = ["brightness", "richness", "attack", "harmonic_quality"]
            matching_attrs = 0
            
            for attr in timbre_attrs:
                if attr in sf1.timbre and attr in sf2.timbre and sf1.timbre[attr] == sf2.timbre[attr]:
                    matching_attrs += 1
            
            score += 0.3 * (matching_attrs / len(timbre_attrs))
        
        return score
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[SoundfontMetadata]:
        """
        Scan a directory for .sf2 files and add them to the database.
        
        Args:
            directory: Directory to scan
            recursive: If True, scan subdirectories too
            
        Returns:
            List of added soundfonts
        """
        added_soundfonts = []
        
        # Function to traverse directory
        def scan_dir(dir_path):
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file() and entry.name.lower().endswith('.sf2'):
                        try:
                            sf = self.add_soundfont(entry.path, auto_analyze=True, save=False)
                            added_soundfonts.append(sf)
                            print(f"Added: {sf.name}")
                        except Exception as e:
                            print(f"Error adding {entry.path}: {e}")
                    
                    elif recursive and entry.is_dir():
                        scan_dir(entry.path)
            
            except Exception as e:
                print(f"Error scanning directory {dir_path}: {e}")
        
        # Start scanning
        scan_dir(directory)
        
        # Save database
        if added_soundfonts:
            self.save_soundfonts()
        
        return added_soundfonts
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the soundfont collection.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_soundfonts": len(self.soundfonts),
            "instrument_types": {},
            "quality_distribution": {},
            "genres": {},
            "tags": {},
            "authors": {},
            "avg_size_mb": 0.0,
            "total_size_mb": 0.0
        }
        
        # Calculate statistics
        total_size = 0.0
        
        for sf in self.soundfonts:
            # Instrument type
            if sf.instrument_type:
                if sf.instrument_type not in stats["instrument_types"]:
                    stats["instrument_types"][sf.instrument_type] = 0
                stats["instrument_types"][sf.instrument_type] += 1
            
            # Quality
            if sf.quality:
                if sf.quality not in stats["quality_distribution"]:
                    stats["quality_distribution"][sf.quality] = 0
                stats["quality_distribution"][sf.quality] += 1
            
            # Genres
            for genre in sf.genre:
                if genre not in stats["genres"]:
                    stats["genres"][genre] = 0
                stats["genres"][genre] += 1
            
            # Tags
            for tag in sf.tags:
                if tag not in stats["tags"]:
                    stats["tags"][tag] = 0
                stats["tags"][tag] += 1
            
            # Authors
            if sf.author:
                if sf.author not in stats["authors"]:
                    stats["authors"][sf.author] = 0
                stats["authors"][sf.author] += 1
            
            # Size - ensure it's a number
            size = float(sf.size_mb) if sf.size_mb and sf.size_mb > 0 else 0.0
            total_size += size
        
        # Calculate average size
        stats["total_size_mb"] = total_size
        if stats["total_soundfonts"] > 0:
            stats["avg_size_mb"] = total_size / stats["total_soundfonts"]
        
        # Sort counts
        stats["instrument_types"] = dict(sorted(stats["instrument_types"].items(), key=lambda x: x[1], reverse=True))
        stats["quality_distribution"] = dict(sorted(stats["quality_distribution"].items(), key=lambda x: x[1], reverse=True))
        stats["genres"] = dict(sorted(stats["genres"].items(), key=lambda x: x[1], reverse=True))
        stats["tags"] = dict(sorted(stats["tags"].items(), key=lambda x: x[1], reverse=True))
        stats["authors"] = dict(sorted(stats["authors"].items(), key=lambda x: x[1], reverse=True))
        
        return stats
    
    def play_soundfont(self, sf: Union[SoundfontMetadata, int], midi_file: Optional[str] = None) -> None:
        """
        Play a soundfont using a MIDI file.
        
        Args:
            sf: SoundfontMetadata object or ID
            midi_file: Path to the MIDI file (if None, create a test file)
        """
        # Get absolute path to soundfont
        sf_path = self.get_absolute_path(sf)
        
        # If no MIDI file provided, create one
        temp_midi = False
        if not midi_file:
            midi_file = create_test_midi()
            temp_midi = True
        
        try:
            # Escape paths for shell
            escaped_sf_path = shlex.quote(sf_path)
            escaped_midi_file = shlex.quote(midi_file)
            
            # Play MIDI using FluidSynth
            os.system(f"fluidsynth -a alsa -g 1.0 {escaped_sf_path} {escaped_midi_file}")
        
        finally:
            # Remove temporary MIDI file
            if temp_midi and os.path.exists(midi_file):
                os.remove(midi_file)
    
    def analyze_soundfont(self, sf_id: int, update_db: bool = True) -> Dict:
        """
        Analyze a soundfont and extract its characteristics.
        
        Args:
            sf_id: ID of the soundfont
            update_db: If True, update the database with extracted information
            
        Returns:
            Dictionary with metadata and characteristics
        """
        sf = self.get_soundfont_by_id(sf_id)
        if not sf:
            raise ValueError(f"Soundfont not found with ID: {sf_id}")
        
        # Get absolute path
        sf_path = self.get_absolute_path(sf)
        
        # Extract metadata and characteristics
        metadata = extract_sf2_metadata(sf_path)
        timbre_info = analyze_timbre(sf_path)
        
        # Combine information
        result = {**metadata, "timbre": timbre_info}
        
        # Update database
        if update_db:
            # Update automatically extracted fields
            mapped_notes = metadata.get("mapped_notes", {})
            if mapped_notes:
                sf.mapped_notes = MappedNotes(
                    min_note=mapped_notes.get("min_note", "C0"),
                    max_note=mapped_notes.get("max_note", "C8"),
                    missing_notes=mapped_notes.get("missing_notes", [])
                )
            
            sf.name = metadata.get("name", sf.name)
            sf.author = metadata.get("author", sf.author)
            sf.description = metadata.get("description", sf.description)
            sf.instrument_type = metadata.get("instrument_type", sf.instrument_type)
            sf.polyphony = metadata.get("polyphony", sf.polyphony)
            sf.sample_rate = metadata.get("sample_rate", sf.sample_rate)
            sf.bit_depth = metadata.get("bit_depth", sf.bit_depth)
            sf.size_mb = metadata.get("size_mb", sf.size_mb)
            sf.timbre = timbre_info
            sf.hash = metadata.get("hash", sf.hash)
            sf.last_modified = metadata.get("last_modified", sf.last_modified)
            
            # Update indices
            self._build_indices()
            
            # Save changes
            self.save_soundfonts()
        
        return result
    
    def export_csv(self, output_file: str) -> None:
        """
        Export soundfont metadata to a CSV file.
        
        Args:
            output_file: Path to the output CSV file
        """
        import csv
        
        # Define columns
        columns = [
            "id", "name", "path", "instrument_type", "quality", "author",
            "size_mb", "sample_rate", "bit_depth", "polyphony", "license",
            "min_note", "max_note", "tags", "genre", "description"
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(columns)
                
                # Write data
                for sf in self.soundfonts:
                    row = [
                        sf.id,
                        sf.name,
                        sf.path,
                        sf.instrument_type,
                        sf.quality,
                        sf.author,
                        sf.size_mb,
                        sf.sample_rate,
                        sf.bit_depth,
                        sf.polyphony,
                        sf.license,
                        sf.mapped_notes.min_note,
                        sf.mapped_notes.max_note,
                        ",".join(sf.tags),
                        ",".join(sf.genre),
                        sf.description
                    ]
                    writer.writerow(row)
            
            print(f"CSV export completed: {output_file}")
        
        except Exception as e:
            print(f"Error exporting CSV: {e}")
    
    def import_csv(self, input_file: str, update_existing: bool = True) -> int:
        """
        Import soundfonts from a CSV file.
        
        Args:
            input_file: Path to the CSV file
            update_existing: If True, update existing soundfonts; if False, skip
            
        Returns:
            Number of imported/updated soundfonts
        """
        import csv
        
        count = 0
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Check if soundfont already exists
                    sf_id = int(row.get("id", 0))
                    existing_sf = self.get_soundfont_by_id(sf_id) if sf_id else None
                    
                    if existing_sf and not update_existing:
                        print(f"Skipping existing soundfont: {row.get('name')}")
                        continue
                    
                    # Prepare SoundfontMetadata object
                    mapped_notes = MappedNotes(
                        min_note=row.get("min_note", "C0"),
                        max_note=row.get("max_note", "C8"),
                        missing_notes=row.get("missing_notes", "").split(",") if row.get("missing_notes") else []
                    )
                    
                    tags = row.get("tags", "").split(",") if row.get("tags") else []
                    genre = row.get("genre", "").split(",") if row.get("genre") else []
                    
                    # Convert size_mb to float or default to 0
                    try:
                        size_mb = float(row.get("size_mb", 0.0))
                    except:
                        size_mb = 0.0
                    
                    sf = SoundfontMetadata(
                        id=sf_id if sf_id else self.next_id,
                        name=row.get("name", ""),
                        path=row.get("path", ""),
                        timbre=row.get("timbre", ""),
                        tags=[tag.strip() for tag in tags if tag.strip()],
                        instrument_type=row.get("instrument_type", ""),
                        quality=row.get("quality", "medium"),
                        genre=[g.strip() for g in genre if g.strip()],
                        mapped_notes=mapped_notes,
                        polyphony=int(row.get("polyphony", 0)),
                        sample_rate=int(row.get("sample_rate", 44100)),
                        bit_depth=int(row.get("bit_depth", 16)),
                        size_mb=size_mb,
                        license=row.get("license", ""),
                        author=row.get("author", ""),
                        description=row.get("description", "")
                    )
                    
                    # Add or update soundfont
                    if existing_sf:
                        # Update fields
                        for key, value in asdict(sf).items():
                            setattr(existing_sf, key, value)
                        print(f"Updated: {sf.name}")
                    else:
                        # Add new
                        self.soundfonts.append(sf)
                        self.next_id = max(self.next_id, sf.id + 1)
                        print(f"Added: {sf.name}")
                    
                    count += 1
            
            # Update indices and save
            if count > 0:
                self._build_indices()
                self.save_soundfonts()
            
            return count
        
        except Exception as e:
            print(f"Error importing CSV: {e}")
            return count