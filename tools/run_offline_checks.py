"""Explicit offline suite; never discover live tools/test_pipe.py or diag_pipe.py.

Use --transport only with a freshly built standalone DLL. That test forces and
checks a UUID test pipe before loading the DLL; no production server is imported.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ['test_protocol_catalog.py', 'test_persistence_contract.py',
         'test_reads_attributes.py', 'test_integration_contract.py',
         'test_groups_waypoints.py']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', action='store_true', help='Also run the isolated Windows DLL lifecycle tests')
    args = parser.parse_args()
    suites = TESTS + (['test_bridge_lifecycle.py'] if args.transport else [])
    failures = []
    for name in suites:
        print(f'Running {name}', flush=True)
        # Separate processes prevent fake modules and cached pipe names leaking
        # between suites. No production server or unrelated test is discovered.
        result = subprocess.run([sys.executable, str(ROOT / 'tools' / name)], cwd=ROOT)
        if result.returncode:
            failures.append(name)
    if failures:
        print('FAILED: ' + ', '.join(failures), file=sys.stderr)
        raise SystemExit(1)
    print(f'All {len(suites)} explicitly selected suites passed.')
