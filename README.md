# Sistema Avançado de Gerenciamento de Soundfonts

Um sistema completo para gerenciamento, anotação e utilização de soundfonts em projetos MIDI desenvolvido em Python.

## Visão Geral

Este sistema fornece um conjunto abrangente de ferramentas para trabalhar com arquivos soundfont (SF2), incluindo:

- **Extração automática** de metadados técnicos diretamente dos arquivos SF2
- **Análise acústica** para classificação automática de timbre
- **Sistema de indexação** eficiente para pesquisa e filtragem
- **API avançada** para seleção e gerenciamento de soundfonts
- **Geração de música** integrada com MIDI e soundfonts
- **Anotador interativo** para categorização de soundfonts com suporte para entrada manual de dados
- **Robustez** para compatibilidade com diferentes formatos e versões de SF2

## Componentes do Sistema

### 1. `soundfont_utils.py`
Utilitários para processamento e análise de soundfonts:

- Extração automática de metadados usando `sf2utils`
- Análise acústica com `librosa` para classificação de timbre
- Tratamento robusto de diferentes implementações de sf2utils
- Escape apropriado de caminhos com caracteres especiais
- Sugestão automática de tags, gêneros e qualidade

### 2. `soundfont_manager.py`
API principal para gerenciamento da biblioteca de soundfonts:

- Armazenamento e indexação eficiente
- Sistema de busca avançada (texto, tags, tipo, qualidade)
- Recomendação de soundfonts similares
- Estatísticas da coleção
- Exportação/importação para CSV

### 3. `sf_annotator.py`
Anotador avançado de soundfonts com interface de linha de comando:

- Extração automática de metadados técnicos
- Análise de timbre com reprodução de testes
- Múltiplos modos de operação (básico, completo, interativo)
- Suporte para entrada manual de dados com `--insert-data`
- Escaneamento recursivo de diretórios
- Interface em inglês e tratamento robusto de erros
- Verificação defensiva de atributos para compatibilidade com todas as versões de sf2utils
- Modo de depuração com detalhamento de erros
- Salvamento periódico para grandes coleções

### 4. `midi_soundfont_player.py`
Sistema para geração e reprodução de música:

- Composições em diferentes estilos (pop, rock, jazz, clássico)
- Criação de progressões de acordes, melodias, baixo e bateria
- Integração com FluidSynth para reprodução
- Seleção inteligente de soundfonts

## Requisitos do Sistema

### Requisitos Gerais
- **Python**: 3.8 ou superior
- **FluidSynth**: 2.0 ou superior (necessário para reprodução de áudio)
- **Sistema Operacional**: Linux, macOS ou Windows

### Pacotes Python
Instale as dependências:

```bash
pip install -r requirements.txt
```

Ou instale individualmente:

```bash
pip install sf2utils>=1.0.0
pip install pretty_midi>=0.2.9
pip install librosa>=0.9.2
pip install colorama>=0.4.4
pip install numpy>=1.20.0
pip install typing_extensions>=4.0.0
```

### Instalação do FluidSynth

- **Linux**:
  ```bash
  sudo apt-get install fluidsynth
  ```

- **macOS**:
  ```bash
  brew install fluidsynth
  ```

- **Windows**:
  - Baixe o instalador do [site oficial](https://www.fluidsynth.org/)
  - Ou use Chocolatey: `choco install fluidsynth`
  - Adicione ao PATH do sistema

## Uso Básico

### Anotador de Soundfonts

```bash
# Uso básico
python sf_annotator.py --directory soundfonts --output library.json

# Modo interativo com entrada manual de dados
python sf_annotator.py --directory soundfonts --output library.json --mode interactive

# Processamento em lote com entrada manual para cada soundfont
python sf_annotator.py --directory soundfonts --output library.json --insert-data

# Escaneamento recursivo com reanálise forçada
python sf_annotator.py --directory soundfonts --output library.json --recursive --force

# Reprodução de teste durante anotação
python sf_annotator.py --directory soundfonts --output library.json --play

# Modo de depuração para informações detalhadas de erro
python sf_annotator.py --directory soundfonts --output library.json --debug

# Processamento mais rápido (sem análise de timbre)
python sf_annotator.py --directory soundfonts --output library.json --no-timbre-analysis

# Processamento de grandes coleções com salvamento periódico
python sf_annotator.py --directory soundfonts --output library.json --recursive --batch-size 20

# Conjunto completo de opções para anotação detalhada
python sf_annotator.py --directory soundfonts --output library.json --mode interactive --recursive --insert-data --play
```

### Gerenciamento de Soundfonts via API

```python
from soundfont_manager import SoundfontManager

# Inicializa o gerenciador
manager = SoundfontManager("soundfonts.json", "path/to/soundfonts")

# Escaneia um diretório por soundfonts
added = manager.scan_directory("soundfonts", recursive=True)
print(f"Adicionados {len(added)} soundfonts")

# Pesquisa por texto
results = manager.search("piano jazz")

# Filtragem por tags
piano_soundfonts = manager.get_soundfonts_by_tags(["piano", "acoustic"])

# Filtragem avançada
high_quality = manager.filter_soundfonts(quality="high", 
                                        instrument_type="piano")

# Soundfont aleatório com filtro
random_sf = manager.get_random_soundfont(
    lambda sf: sf.quality == "high" and "orchestra" in sf.tags
)

# Estatísticas da coleção
stats = manager.get_statistics()
print(f"Total de soundfonts: {stats['total_soundfonts']}")
print(f"Tamanho total: {stats['total_size_mb']:.2f} MB")
```

### Geração de Música

```python
from midi_soundfont_player import MusicGenerator, ScaleType

# Inicializa o gerador
generator = MusicGenerator(manager)

# Gera uma composição
midi_file = generator.generate_composition(
    key="C",
    scale_type=ScaleType.MINOR,
    tempo=120.0,
    num_measures=8,
    style="jazz",
    output_file="composition.mid"
)

# Reproduz com soundfont específico
generator.play_composition_with_soundfont(
    midi_file=midi_file,
    soundfont_id=5
)
```

## Contribuições

Contribuições são bem-vindas! Por favor, abra uma issue para discutir mudanças significativas.

## Licença

Este projeto é disponibilizado sob a licença MIT.
