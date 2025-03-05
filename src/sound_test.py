import os
import tempfile
import subprocess
import platform
from typing import Optional, Tuple, List

def test_audio_drivers() -> List[str]:
    """
    Testa quais drivers de áudio estão realmente funcionando no sistema.
    
    Returns:
        Lista de drivers de áudio testados e funcionais
    """
    working_drivers = []
    possible_drivers = []
    
    system = platform.system().lower()
    
    # Lista de drivers potenciais por sistema
    if system == 'linux':
        possible_drivers = ['alsa', 'pulseaudio', 'jack', 'oss']
    elif system == 'darwin':  # macOS
        possible_drivers = ['coreaudio', 'jack']
    elif system == 'windows':
        possible_drivers = ['dsound', 'wasapi', 'wdmks', 'winmidi']
    else:
        possible_drivers = ['alsa', 'oss']
    
    # Teste cada driver
    null_device = 'NUL' if system == 'windows' else '/dev/null'
    
    for driver in possible_drivers:
        cmd = ['fluidsynth', '-a', driver, '-n', '-q', '-i', '--check']
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1  # Limite de tempo para teste
            )
            
            # Se o código de retorno for 0 ou conter certas indicações de sucesso
            if result.returncode == 0 or "audio driver" in result.stdout.lower() or "audio driver" in result.stderr.lower():
                if "error" not in result.stderr.lower() or "failed" not in result.stderr.lower():
                    working_drivers.append(driver)
        except:
            # Ignora erros de timeout ou outros
            continue
    
    # Se nenhum driver específico funcionar, adicione 'default'
    if not working_drivers:
        working_drivers.append('default')
    
    return working_drivers

def simplified_midi_for_test(output_file: str) -> bool:
    """
    Cria um arquivo MIDI simples com apenas três notas centrais para teste.
    
    Args:
        output_file: Caminho para o arquivo MIDI de saída
        
    Returns:
        True se criado com sucesso, False caso contrário
    """
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
        
        # Adicionar notas ao instrumento
        for note_info in notes:
            note = pretty_midi.Note(
                velocity=note_info["velocity"],
                pitch=note_info["note"],
                start=note_info["start"],
                end=note_info["end"]
            )
            instrument.notes.append(note)
        
        # Adicionar o instrumento ao MIDI
        midi.instruments.append(instrument)
        
        # Salvar o arquivo MIDI
        midi.write(output_file)
        
        return os.path.exists(output_file)
    except Exception as e:
        print(f"Error while creating a simplified MIDI: {e}")
        return False

def test_soundfont(soundfont_path: str, verbose: bool = False, wav_output: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Testa um soundfont tentando várias abordagens, incluindo renderização para WAV.
    
    Args:
        soundfont_path: Caminho para o arquivo .sf2
        verbose: Se True, exibe saídas detalhadas
        wav_output: Caminho para salvar o WAV gerado (opcional)
        
    Returns:
        Tupla (sucesso, caminho_wav) onde caminho_wav é o WAV gerado (se houver)
    """
    if not os.path.exists(soundfont_path):
        if verbose:
            print(f"Error: Soundfont file not found: {soundfont_path}")
        return False, None
    
    # Verificar se o FluidSynth está disponível
    fluidsynth_available = False
    try:
        result = subprocess.run(['fluidsynth', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        fluidsynth_available = (result.returncode == 0)
    except:
        if verbose:
            print("Error: FluidSynth not available.")
        return False, None
    
    if not fluidsynth_available:
        return False, None
    
    # Criar arquivo MIDI simplificado
    temp_files = []
    
    try:
        # Criar arquivo MIDI temporário
        fd, midi_file = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        temp_files.append(midi_file)
        
        if not simplified_midi_for_test(midi_file):
            if verbose:
                print("Error while creating a MIDI file for testing.")
            return False, None
        
        # Determinar o caminho do WAV
        temp_wav = None
        if wav_output:
            temp_wav = wav_output
        else:
            fd, temp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            temp_files.append(temp_wav)
        
        # Tentar renderizar para WAV (a opção mais confiável)
        if verbose:
            print(f"Rendering WAV test file using {soundfont_path}...")
        
        # Obter drivers de áudio funcionais
        working_drivers = test_audio_drivers()
        
        # Tentar cada driver para renderizar WAV
        success = False
        
        for driver in working_drivers:
            cmd = [
                'fluidsynth',
                '-ni',                # No shell interface
                '-g', '0.7',          # Gain (volume mais baixo para evitar clipping)
                '-F', temp_wav,       # Arquivo WAV de saída
                '-a', driver,         # Driver de áudio
                soundfont_path,       # Soundfont
                midi_file             # Arquivo MIDI
            ]
            
            try:
                if verbose:
                    print(f"Trying with driver: {driver}")
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5  # Limite de tempo
                )
                
                if result.returncode == 0 and os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 0:
                    success = True
                    break
                elif verbose:
                    print(f"Error with driver {driver}: {result.stderr}")
            
            except subprocess.TimeoutExpired:
                if verbose:
                    print(f"Timeout while rendering with driver {driver}")
                # Continuar com o próximo driver
            except Exception as e:
                if verbose:
                    print(f"Error while rendering: {e}")
        
        # Se conseguimos gerar o WAV
        if success:
            if verbose:
                print(f"Soundfont WAV test rendered with succes: {temp_wav}")
            
            # Tentar reproduzir o WAV se for parte do teste
            if verbose:
                try:
                    system = platform.system().lower()
                    if system == 'linux':
                        subprocess.run(['aplay', temp_wav], timeout=3)
                    elif system == 'darwin':
                        subprocess.run(['afplay', temp_wav], timeout=3)
                    elif system == 'windows':
                        import winsound
                        winsound.PlaySound(temp_wav, winsound.SND_FILENAME)
                except:
                    # Se a reprodução falhar, pelo menos temos o WAV
                    pass
            
            # Se criamos um WAV temporário e o usuário não especificou um, remova-o da lista de temp_files
            if wav_output and temp_wav in temp_files:
                temp_files.remove(temp_wav)
            
            return True, temp_wav
    
    except Exception as e:
        if verbose:
            print(f"Error while testing soundfont: {e}")
    
    finally:
        # Limpar arquivos temporários
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
    
    return False, None

def play_wav_simple(wav_file: str, debug: bool = False) -> bool:
    """Tenta reproduzir um arquivo WAV usando pygame."""
    if not os.path.exists(wav_file):
        if debug:
            print(f"WAV file not found: {wav_file}")
        return False
    
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(wav_file)
        pygame.mixer.music.play()
        import time
        time.sleep(2)  # Reproduzir por 2 segundos pelo menos
        pygame.mixer.music.fadeout(500)
        return True
    except Exception as e:
        if debug:
            print(f"Error while playing with pygame: {e}")
        return False

def create_single_note_midi(output_file: str, note: int) -> bool:
    """Create a simple MIDI file with a single note."""
    try:
        import pretty_midi
        
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)  # Piano
        
        # Create a 1-second note
        midi_note = pretty_midi.Note(
            velocity=100,
            pitch=note,
            start=0.0,
            end=1.0
        )
        
        instrument.notes.append(midi_note)
        midi.instruments.append(instrument)
        midi.write(output_file)
        
        return os.path.exists(output_file)
    except Exception as e:
        print(f"Error creating MIDI: {e}")
        return False

def is_silent_wav(wav_file: str, threshold: float = 0.01) -> bool:
    """Check if a WAV file is silent or contains audio."""
    try:
        import librosa
        import numpy as np
        
        # Load the audio file
        y, sr = librosa.load(wav_file, sr=None, mono=True)
        
        # Check if the audio is silent (RMS below threshold)
        rms = np.sqrt(np.mean(y**2))
        return rms < threshold
    except Exception as e:
        print(f"Error analyzing WAV: {e}")
        return True  # Assume silent on error

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test soundfonts")
    parser.add_argument("soundfont", help="Path to .sf2 file")
    parser.add_argument("--wav", help="Save test as WAV")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    
    args = parser.parse_args()
    
    success, wav_path = test_soundfont(args.soundfont, args.verbose, args.wav)
    
    if success:
        print(f"Soundfont test successful.")
        if wav_path:
            print(f"Generated WAV file: {wav_path}")
    else:
        print("Soundfont test failure.")
