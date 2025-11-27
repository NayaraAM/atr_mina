#!/usr/bin/env python3
"""Repara build/logs/logs_caminhao_detailed.csv de forma segura.

- Faz backup do arquivo original para `<file>.bak.<timestamp>`
- Garante que o header seja:
  timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp
- Remove headers duplicados no meio do arquivo
- Para linhas de dados com menos colunas, adiciona ",0" para completar as colunas faltantes

Imprime um resumo no final (linhas lidas, linhas reparadas, backup criado).
"""
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / 'build' / 'logs'
CSV = LOGS / 'logs_caminhao_detailed.csv'

EXPECTED_HEADER = 'timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp\n'
EXPECTED_COMMAS = EXPECTED_HEADER.count(',')

def main():
    if not CSV.exists():
        print(f'Arquivo não encontrado: {CSV}')
        return 2

    ts = int(time.time())
    bak = CSV.with_suffix(CSV.suffix + f'.bak.{ts}')
    shutil.copy2(CSV, bak)
    print(f'Backup criado: {bak}')

    lines = CSV.read_text().splitlines()
    out_lines = []
    header_written = False
    repaired = 0
    skipped_headers = 0
    processed = 0

    for idx, raw in enumerate(lines):
        if not raw or raw.strip() == '':
            continue

        # Normalize line endings handled by splitlines
        if not header_written:
            # If this line already contains the new header, write it once
            if 'e_alerta_temp' in raw:
                out_lines.append(EXPECTED_HEADER.rstrip('\n'))
                header_written = True
                continue
            # If this line is an old header (has timestamp_ms but lacks e_alerta_temp)
            if 'timestamp_ms' in raw and 'e_alerta_temp' not in raw:
                out_lines.append(EXPECTED_HEADER.rstrip('\n'))
                header_written = True
                skipped_headers += 1
                continue
            # Otherwise, first non-header line -> write header then process this as data
            out_lines.append(EXPECTED_HEADER.rstrip('\n'))
            header_written = True

        # Skip accidental additional header lines that appear later
        if 'timestamp_ms' in raw and 'e_alerta_temp' in raw:
            skipped_headers += 1
            continue

        # Now raw is data
        processed += 1
        commas = raw.count(',')
        if commas < EXPECTED_COMMAS:
            missing = EXPECTED_COMMAS - commas
            # Append ,0 for each missing field
            raw = raw.rstrip('\n') + (',0' * missing)
            repaired += 1
        out_lines.append(raw)

    # Write to temp file then atomically replace
    tmp = CSV.with_suffix('.tmp')
    tmp.write_text('\n'.join(out_lines) + '\n')
    os.replace(str(tmp), str(CSV))

    print(f'Linhas lidas: {len(lines)}, processadas: {processed}, reparadas: {repaired}, headers removidos: {skipped_headers}')
    print('Arquivo normalizado com sucesso.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
