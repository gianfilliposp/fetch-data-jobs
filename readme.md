# Script para Scraper de Candidatos

Script para buscar e processar dados de candidatos do Catho, organizando por unidades e faixas etárias.

## Unidades

- `01050-030`: escritorio (Escritorio)
- `02989-110`: parada_taipas (ParadaTaipas)
- `02801-000`: elisio (Elisio)
- `02932-080`: edgar_faco (EdgarFaco)
- `02815-040`: ct_taipas (CT)
- `02917-100`: paula_ferreira (PaulaFerreira)

## Uso

### Exemplo de Comando Completo

```bash
python3 runner.py \
  --cep 02989-110 \
  --total-pages 100 \
  --num-exec 5 \
  --instancia gian-parada-taipas \
  --max-distance 5 \
  --min-max-age-list '[{"min":1,"max":20},{"min":20,"max":22},{"min":22,"max":24},{"min":24,"max":26},{"min":26,"max":28},{"min":28,"max":31},{"min":31,"max":35},{"min":35,"max":40},{"min":40,"max":47},{"min":47,"max":99}]'
```

### Parâmetros

#### Obrigatórios

- `--cep`: CEP da unidade (ex: `02989-110`)
- `--total-pages`: Número total de páginas a processar
- `--num-exec`: Número de execuções paralelas (também define o paralelismo)
- `--instancia`: Identificador da execução

#### Opcionais

- `--max-distance`: Distância máxima para busca (padrão: `1`)
- `--initial-page`: Página inicial (padrão: `-1`)
- `--min-max-age-list`: Lista JSON de faixas etárias para processar sequencialmente
- `--age-min`: Idade mínima (opcional, use com `--age-max`)
- `--age-max`: Idade máxima (opcional, use com `--age-min`)
- `--script`: Caminho para o script Python (padrão: `script.py`)
- `--python`: Executável Python a usar (padrão: Python atual)
- `--logs-dir`: Diretório para armazenar logs (padrão: `logs`)

### Exemplos de Uso

#### Processamento com múltiplas faixas etárias (sequencial)

```bash
python3 runner.py \
  --cep 02989-110 \
  --total-pages 100 \
  --num-exec 5 \
  --instancia exemplo \
  --max-distance 5 \
  --min-max-age-list '[{"min":1,"max":20},{"min":20,"max":30}]'
```

#### Processamento com uma única faixa etária

```bash
python3 runner.py \
  --cep 02815-040 \
  --total-pages 50 \
  --num-exec 3 \
  --instancia exemplo-ct \
  --max-distance 1 \
  --age-min 18 \
  --age-max 25
```

#### Processamento sem filtro de idade

```bash
python3 runner.py \
  --cep 02801-000 \
  --total-pages 75 \
  --num-exec 4 \
  --instancia exemplo-elisio \
  --max-distance 3
```

## Estrutura de Logs

Os logs são organizados em diretórios com timestamp de execução:

```
logs/
  └── 2025-12-29_11-45-17/          # Timestamp da execução
      ├── age_range_01_min1_max20/   # Primeira faixa etária
      │   ├── job_001_1-20.log
      │   ├── job_002_21-40.log
      │   └── ...
      ├── age_range_02_min20_max30/  # Segunda faixa etária
      │   ├── job_001_1-20.log
      │   └── ...
      └── ...
```

Quando não há faixas etárias, os logs ficam diretamente no diretório de timestamp:

```
logs/
  └── 2025-12-29_11-45-17/
      ├── job_001_1-20.log
      ├── job_002_21-40.log
      └── ...
```

## Notas

- Quando `--min-max-age-list` é usado, cada faixa etária é processada **sequencialmente** (uma após a outra)
- Dentro de cada faixa etária, as páginas são processadas em **paralelo** conforme `--num-exec`
- O formato JSON para `--min-max-age-list` deve usar aspas simples no shell para evitar problemas de escape
- Cada execução cria um novo diretório com timestamp único
