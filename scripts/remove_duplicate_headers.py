#!/usr/bin/env python3
"""Remove linhas que começam com 'timestamp_ms,' exceto a primeira.
Cria backup antes de sobrescrever o arquivo original.
"""
import shutil
from pathlib import Path
import time

LOG = Path('build/logs/logs_caminhao_detailed.csv')
if not LOG.exists():
    LOG = Path(__file__).parent.parent / 'build' / 'logs' / 'logs_caminhao_detailed.csv'

if not LOG.exists():
    print('Arquivo não encontrado:', LOG)
    raise SystemExit(1)

bak = LOG.with_suffix(LOG.suffix + f'.hdrbak.{int(time.time())}')
shutil.copy2(LOG, bak)
print('Backup criado em', bak)

tmp = LOG.with_suffix('.tmp')
with LOG.open('r', encoding='utf-8', errors='replace') as fin, tmp.open('w', encoding='utf-8') as fout:
    first = True
    removed = 0
    for line in fin:
        if first:
            fout.write(line)
            first = False
            continue
        if line.startswith('timestamp_ms,'):
            removed += 1
            continue
        fout.write(line)

print(f'Removidas {removed} linhas de cabeçalho duplicadas')
tmp.replace(LOG)
print('Arquivo atualizado:', LOG)
