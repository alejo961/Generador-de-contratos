# Generador de matriz de requisitos de importación (Access2Markets)

Script para extraer, por subpartida UE, los requisitos de importación desde un origen (por defecto Colombia `CO`) a un destino (por defecto Francia `FR`) usando los endpoints públicos de Access2Markets.

## Archivos

- `scrape_requisitos_ue.py`: scraping y generación de matriz/detalle en CSV.
- `subpartidas_ue.csv`: listado de 34 subpartidas UE (columna `subpartida_ue`).

## Requisitos

```bash
pip install playwright
playwright install chromium
```

## Uso

### 1) Matriz resumida (rápida)

```bash
python scrape_requisitos_ue.py \
  --input subpartidas_ue.csv \
  --output matriz_requisitos.csv \
  --details requisitos_detalle.csv
```

### 2) Incluyendo detalle textual de cada requisito (más lento)

```bash
python scrape_requisitos_ue.py \
  --input subpartidas_ue.csv \
  --output matriz_requisitos.csv \
  --details requisitos_detalle.csv \
  --include-content
```

## Estructura de salida

### `matriz_requisitos.csv`

- `subpartida_ue`
- `origen`
- `destino`
- `requisitos_generales_count`
- `requisitos_especificos_count`
- `requisitos_generales` (concatenado con ` | `)
- `requisitos_especificos` (concatenado con ` | `)

### `requisitos_detalle.csv`

Una fila por requisito detectado:

- `subpartida_ue`, `origen`, `destino`
- `tipo` (`general`/`especifico`)
- `codigo_requisito`
- `etiqueta`
- `titulo`
- `detalle_texto` (si usas `--include-content`)

## Notas

- Fuente: `https://trade.ec.europa.eu/access-to-markets/`
- Endpoint principal usado por subpartida:
  - `/api/v2/document/list?destinationCountry=FR&originCountry=CO&product=<subpartida>&lang=EN`
