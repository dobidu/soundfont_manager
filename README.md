# Sistema Avançado de Gerenciamento de Soundfonts

Um sistema completo para gerenciamento, anotação e utilização de soundfonts em projetos MIDI desenvolvido em Python.

## Visão Geral

Este sistema fornece um conjunto abrangente de ferramentas para trabalhar com arquivos soundfont (SF2), incluindo:

- **Extração automática** de metadados técnicos diretamente dos arquivos SF2
- **Análise acústica** para classificação automática de timbre
- **Sistema de indexação** eficiente para pesquisa e filtragem
- **API avançada** para seleção e gerenciamento de soundfonts
- **Geração de música** integrada com MIDI e soundfonts
- **Anotador interativo** para categorização de soundfonts

## Componentes do Sistema

### 1. `soundfont_utils.py`
Módulo de utilitários que fornece funções para extração e análise de soundfonts:

- Extração de metadados de arquivos SF2 usando `sf2utils`
- Análise de mapeamento de notas
- Análise automática de timbre usando técnicas de MIR
- Sugestão de tags e metadados

### 2. `soundfont_manager.py`
API principal para gerenciamento da coleção de soundfonts:

- Armazenamento e indexação eficiente
- Buscas por múltiplos critérios (texto, tags, tipo de instrumento, etc.)
- Recomendação de soundfonts similares
- Exportação e importação de dados
- Gestão eficiente de arquivos

### 3. `sf_annotator.py`
Ferramenta interativa para anotação de soundfonts:

- Interface de linha de comando com colorama
- Extração automática de metadados
- Análise de timbre e características sonoras
- Modo interativo com reprodução de testes
- Anotação em lote

### 4. `midi_soundfont_player.py`
Sistema para geração e reprodução de música com soundfonts:

- Geração de composições MIDI em diferentes estilos
- Uso inteligente de soundfonts para reprodução
- Criação de progressões de acordes, melodias, linhas de baixo e bateria
- Integração com FluidSynth para reprodução

## Dependências

### Requisitos do Sistema
- **Python**: 3.8 ou superior
- **FluidSynth**: 2.0 ou superior (necessário para reprodução de áudio)
- **Sistema Operacional**: Linux, macOS ou Windows

### Pacotes Python
Instale as dependências principais:

```bash
pip install -r requirements.txt
```

Ou instale individualmente:

```bash
pip install sf2utils==1.3.0
pip install pretty_midi==0.2.10
pip install librosa==0.10.1
pip install colorama==0.4.6
pip install numpy==1.24.0
pip install dataclasses==0.8     # Somente para Python 3.6
pip install typing_extensions==4.7.1
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
  - Adicione o diretório de instalação ao PATH do sistema

### Dependências Opcionais

Para visualização de áudio (opcional):
```bash
pip install matplotlib==3.7.2
```

Para processamento paralelo em análise de grandes coleções:
```bash
pip install joblib==1.3.2
```

## Uso Básico

### Inicialização do Gerenciador

```python
from soundfont_manager import SoundfontManager

# Inicializa o gerenciador
manager = SoundfontManager("soundfonts.json", "path/to/soundfonts")

# Escaneia um diretório por soundfonts
added = manager.scan_directory("soundfonts", recursive=True)
print(f"Adicionados {len(added)} soundfonts")
```

### Pesquisa e Filtragem

```python
# Pesquisa por texto
results = manager.search("piano jazz")

# Filtragem por tags
piano_soundfonts = manager.get_soundfonts_by_tags(["piano", "acústico"])

# Filtragem avançada
high_quality = manager.filter_soundfonts(quality="alta", 
                                        instrument_type="piano")

# Soundfont aleatório com filtro
random_sf = manager.get_random_soundfont(
    lambda sf: sf.quality == "alta" and "orquestra" in sf.tags
)
```

### Geração de Música

```python
from midi_soundfont_player import MusicGenerator, ScaleType, Chord

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

# Reproduz com um soundfont específico
generator.play_composition_with_soundfont(
    midi_file=midi_file,
    soundfont_id=5,  # ID do soundfont
)
```

## Características Avançadas

### Análise de Timbre

O sistema analisa automaticamente o timbre dos soundfonts, extraindo as seguintes características:

- **Brilho**: escuro, médio, brilhante, muito brilhante
- **Riqueza**: simples, médio, rico, muito rico
- **Ataque**: suave, médio, duro, agressivo
- **Qualidade Harmônica**: percussivo, balanceado, harmônico, muito harmônico

### Mapeamento de Notas

Identifica automaticamente:

- Nota mais grave disponível
- Nota mais aguda disponível
- Notas faltantes no intervalo

### Recomendação Inteligente

```python
# Encontra soundfonts similares
similar_soundfonts = manager.get_similar_soundfonts(sf_id=10, limit=5)
```

### Exportação/Importação

```python
# Exporta para CSV
manager.export_csv("soundfonts_export.csv")

# Importa de CSV
manager.import_csv("soundfonts_export.csv")
```

## Exemplos

Consulte o arquivo `example_usage.py` para exemplos detalhados de uso do sistema.

Para executar um exemplo específico:

```bash
python example_usage.py 1  # Executa o exemplo 1
```

## Linha de Comando

### Anotador de Soundfonts

```bash
python sf_annotator.py --directory soundfonts --output library.json --mode full --recursive
```

### Gerador de Música

```bash
python midi_soundfont_player.py --key D --tempo 110 --style rock --sf-id 3
```

## Licença

Este projeto é disponibilizado sob a licença MIT.

## Contribuições

Contribuições são bem-vindas! Por favor, abra uma issue para discutir mudanças significativas.
