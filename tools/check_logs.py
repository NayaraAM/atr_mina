#!/usr/bin/env python3
"""tools/check_logs.py

Valida o formato dos logs gerados pelo ColetorDeDados_thread.

Exemplo de uso:
  python3 tools/check_logs.py --file build/logs/logs_caminhao.txt
"""
import argparse
import sys
from pathlib import Path


def check_tabela3(path, max_examples=20):
    path = Path(path)
    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        return 2

    total = 0
    malformed = 0
    first_valid = None
    last_valid = None
    bad_examples = []

    def is_int(s):
        try:
            int(s)
            return True
        except Exception:
            return False

    with path.open('r', encoding='utf-8', errors='replace') as f:
        for line in f:
            total += 1
            s = line.rstrip('\n')
            if not s:
                continue
            parts = [p.strip() for p in s.split(',')]

            valid = False

            # tentativa estrita: timestamp,truck,estado,px,py,descricao
            if len(parts) >= 6:
                ts = parts[0]
                truck = parts[1]
                estado = parts[2]
                px = parts[3]
                py = parts[4]
                if is_int(ts) and is_int(truck) and is_int(px) and is_int(py) and (estado in ("MANUAL", "AUTOMATICO")):
                    valid = True

            # tentativa flexível: aceitar linhas onde há timestamp no início e
            # dois inteiros consecutivos (px, py) em qualquer posição, além do estado
            if not valid:
                if len(parts) >= 3 and is_int(parts[0]):
                    # encontrar dois inteiros consecutivos que parecem ser pos_x,pos_y
                    idx = None
                    for i in range(len(parts) - 1):
                        if is_int(parts[i]) and is_int(parts[i+1]):
                            # ignore if this is timestamp+truck (indices 0 and 1)
                            if i == 0: continue
                            # plausibilidade: valores de posição razoáveis
                            try:
                                vx = int(parts[i])
                                vy = int(parts[i+1])
                                if -10000 <= vx <= 10000 and -10000 <= vy <= 10000:
                                    idx = i
                                    break
                            except Exception:
                                continue

                    has_estado = any(p in ("MANUAL", "AUTOMATICO") for p in parts)
                    if idx is not None and has_estado:
                        valid = True

            if valid:
                if first_valid is None:
                    first_valid = s
                last_valid = s
            else:
                malformed += 1
                if len(bad_examples) < max_examples:
                    bad_examples.append((total, s))

    print(f"Arquivo: {path}")
    print(f"Total de linhas: {total}")
    print(f"Linhas malformadas: {malformed}")
    if first_valid:
        print("Primeira linha válida:")
        print("  ", first_valid)
    if last_valid:
        print("Última linha válida:")
        print("  ", last_valid)
    if bad_examples:
        print("Exemplos de linhas malformadas:")
        for ln, s in bad_examples:
            print(f"  [{ln}] {s}")

    return 0 if malformed == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', '-f', default='build/logs/logs_caminhao.txt', help='Caminho para o arquivo de logs (Tabela 3)')
    ap.add_argument('--detailed', '-d', default='build/logs/logs_caminhao_detailed.csv', help='CSV detalhado (opcional)')
    args = ap.parse_args()

    rc = check_tabela3(args.file)
    # opcional: checar CSV detalhado (conteúdo básico)
    pathd = Path(args.detailed)
    if pathd.exists():
        print('\nArquivo CSV detalhado encontrado. Mostrando 3 primeiras linhas:')
        with pathd.open('r', encoding='utf-8', errors='replace') as f:
            for i, l in enumerate(f):
                print(l.rstrip('\n'))
                if i >= 2: break
    else:
        print(f"\nCSV detalhado não encontrado em: {pathd}")

    sys.exit(rc)


if __name__ == '__main__':
    main()
