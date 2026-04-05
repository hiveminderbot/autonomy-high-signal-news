#!/usr/bin/env python3
"""Run validation checks for high-signal-news lab"""
import sys
sys.path.insert(0, '/home/exedev/autonomy/labs/infrastructure/labtools')
from validation_checks.runner import CheckRunner
import json

runner = CheckRunner('.')
runner.load_config('validation.json')
report = runner.run()

passed = 0
failed = 0
warned = 0

for r in report.results:
    status_icon = '✅' if r.status.name == 'PASS' else '⚠️' if r.status.name == 'WARN' else '❌'
    print(f'{status_icon} {r.name}: {r.status.name}')
    if r.message:
        print(f'   {r.message}')
    
    if r.status.name == 'PASS':
        passed += 1
    elif r.status.name == 'WARN':
        warned += 1
    else:
        failed += 1

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {warned} warnings, {failed} failed")
print(f"Overall: {'PASS' if report.success else 'FAIL'}")
print(f"{'='*50}")

sys.exit(0 if report.success else 1)
