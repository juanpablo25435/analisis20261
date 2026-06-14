from __future__ import annotations

import csv
import subprocess
import sys
import time
from pathlib import Path

METHOD2_ROOT = Path('/home/crack/analisis20261/GeoMIP/src/Method2_Dynamic_Programming_Reformulation')
RESULTS_DIR = Path('/home/crack/analisis20261/GeoMIP/results')
LOG_PATH = RESULTS_DIR / 'exec_pipeline.log'
MEMORY_PATH = RESULTS_DIR / 'memory_exec.log'
SUMMARY_PATH = RESULTS_DIR / 'memory_exec_summary.txt'


def _process_rows() -> list[tuple[int, int, int, str]]:
    ps = subprocess.run(
        ['ps', '-eo', 'pid=,ppid=,rss=,args='],
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[tuple[int, int, int, str]] = []
    for line in ps.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), int(parts[2]), parts[3]))
        except ValueError:
            continue
    return rows


def _descendants(root_pid: int, rows: list[tuple[int, int, int, str]]) -> set[int]:
    children_by_parent: dict[int, list[int]] = {}
    for pid, ppid, _rss, _args in rows:
        children_by_parent.setdefault(ppid, []).append(pid)

    seen = {root_pid}
    stack = [root_pid]
    while stack:
        parent = stack.pop()
        for child in children_by_parent.get(parent, []):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('w', encoding='utf-8') as log_file, MEMORY_PATH.open(
        'w', encoding='utf-8', newline=''
    ) as memory_file:
        writer = csv.writer(memory_file)
        writer.writerow(['elapsed_seconds', 'total_rss_mb', 'process_count', 'max_single_rss_mb'])
        memory_file.flush()

        process = subprocess.Popen(
            ['uv', 'run', 'exec.py'],
            cwd=METHOD2_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        start = time.monotonic()
        max_total = 0.0
        max_single = 0.0
        samples = 0

        while process.poll() is None:
            rows = _process_rows()
            tree = _descendants(process.pid, rows)
            rss_values = [rss / 1024 for pid, _ppid, rss, _args in rows if pid in tree]
            total = sum(rss_values)
            single = max(rss_values, default=0.0)
            max_total = max(max_total, total)
            max_single = max(max_single, single)
            samples += 1
            writer.writerow([f'{time.monotonic() - start:.2f}', f'{total:.2f}', len(rss_values), f'{single:.2f}'])
            memory_file.flush()
            time.sleep(2)

        exit_code = process.wait()
        SUMMARY_PATH.write_text(
            '\n'.join(
                [
                    f'exit_code={exit_code}',
                    f'samples={samples}',
                    f'max_total_rss_mb={max_total:.2f}',
                    f'max_single_rss_mb={max_single:.2f}',
                    f'log_path={LOG_PATH}',
                    f'memory_log_path={MEMORY_PATH}',
                ]
            )
            + '\n',
            encoding='utf-8',
        )
        return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
