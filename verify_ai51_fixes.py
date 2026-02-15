#!/usr/bin/env python3
"""Verification script for AI-51 re-implementation with blocking issues fixed.

This script verifies that all blocking issues from PR #22 have been addressed:
1. FIXED: Import statements moved to top of file (no longer inside functions)
2. FIXED: 'started_at' variable removed (was unused)
3. FIXED: TODO comments added for token tracking
4. FIXED: TODO comments added for model detection
5. FIXED: Files organized - docs/ and tests/ folders created
6. FIXED: pytest added to requirements.txt
"""

import re
import sys
from pathlib import Path


def check_orchestrator_fixes():
    """Check that orchestrator.py has all fixes applied."""
    print("=" * 70)
    print("VERIFYING AI-51 BLOCKING ISSUES FIXED")
    print("=" * 70)

    orchestrator_path = Path(__file__).parent / "agents" / "orchestrator.py"
    content = orchestrator_path.read_text()
    lines = content.split('\n')

    issues_fixed = []
    issues_remaining = []

    # Check 1: Import statements at top
    print("\n1. Checking imports are at top of file...")
    import_section = '\n'.join(lines[:30])
    if 'import re' in import_section and 'from datetime import datetime' in import_section:
        print("   ✓ FIXED: 're' and 'datetime' imports at top of file")
        issues_fixed.append("Imports moved to top")
    else:
        print("   ✗ FAIL: Imports not found at top")
        issues_remaining.append("Imports at top")

    # Check for imports inside functions (should not exist)
    function_section = '\n'.join(lines[60:])
    if 'import re' in function_section or 'from datetime import' in function_section:
        print("   ✗ FAIL: Found imports inside functions")
        issues_remaining.append("Remove imports from functions")
    else:
        print("   ✓ FIXED: No imports inside functions")

    # Check 2: started_at variable removed
    print("\n2. Checking 'started_at' variable usage...")
    if 'started_at = ' in content:
        print("   ✗ FAIL: 'started_at' variable still exists")
        issues_remaining.append("Remove started_at variable")
    else:
        print("   ✓ FIXED: 'started_at' variable removed")
        issues_fixed.append("Removed unused started_at variable")

    # Check 3: TODO comments for token tracking
    print("\n3. Checking TODO comments for token tracking...")
    if 'TODO' in content and 'token' in content.lower() and 'SDK metadata' in content:
        print("   ✓ FIXED: TODO comments added for token tracking")
        issues_fixed.append("TODO for token tracking")
    else:
        print("   ✗ FAIL: Missing TODO for token tracking")
        issues_remaining.append("Add TODO for token tracking")

    # Check 4: TODO comments for model detection
    print("\n4. Checking TODO comments for model detection...")
    if 'TODO' in content and 'model' in content.lower() and 'SDK' in content:
        print("   ✓ FIXED: TODO comments added for model detection")
        issues_fixed.append("TODO for model detection")
    else:
        print("   ✗ FAIL: Missing TODO for model detection")
        issues_remaining.append("Add TODO for model detection")

    # Check 5: File organization
    print("\n5. Checking file organization...")
    docs_dir = Path(__file__).parent / "docs"
    tests_dir = Path(__file__).parent / "tests"

    if docs_dir.exists() and (docs_dir / "AI-51-FINAL-REPORT.md").exists():
        print("   ✓ FIXED: docs/ folder created with documentation")
        issues_fixed.append("Created docs/ folder")
    else:
        print("   ✗ FAIL: docs/ folder missing or empty")
        issues_remaining.append("Create docs/ folder")

    if tests_dir.exists() and (tests_dir / "test_orchestrator_delegation.py").exists():
        print("   ✓ FIXED: tests/ folder created with test files")
        issues_fixed.append("Created tests/ folder")
    else:
        print("   ✗ FAIL: tests/ folder missing or empty")
        issues_remaining.append("Create tests/ folder")

    # Check 6: pytest in requirements.txt
    print("\n6. Checking pytest in requirements.txt...")
    req_path = Path(__file__).parent / "requirements.txt"
    req_content = req_path.read_text()
    if 'pytest' in req_content:
        print("   ✓ FIXED: pytest added to requirements.txt")
        issues_fixed.append("Added pytest to requirements.txt")
    else:
        print("   ✗ FAIL: pytest not in requirements.txt")
        issues_remaining.append("Add pytest to requirements.txt")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nIssues Fixed: {len(issues_fixed)}/6")
    for issue in issues_fixed:
        print(f"  ✓ {issue}")

    if issues_remaining:
        print(f"\nIssues Remaining: {len(issues_remaining)}")
        for issue in issues_remaining:
            print(f"  ✗ {issue}")
        return False
    else:
        print("\n✓ ALL BLOCKING ISSUES FIXED!")
        return True


def check_type_annotations():
    """Check that type annotations are correct."""
    print("\n" + "=" * 70)
    print("CHECKING TYPE ANNOTATIONS")
    print("=" * 70)

    orchestrator_path = Path(__file__).parent / "agents" / "orchestrator.py"
    content = orchestrator_path.read_text()

    # Check that active_delegations type is updated
    if 'active_delegations: dict[str, tuple[str, str]]' in content:
        print("✓ Type annotation updated for active_delegations (removed timestamp)")
        return True
    else:
        print("✗ Type annotation not updated")
        return False


def main():
    """Run all verification checks."""
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║         AI-51 RE-IMPLEMENTATION VERIFICATION                       ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")

    all_fixed = check_orchestrator_fixes()
    types_ok = check_type_annotations()

    print("\n" + "═" * 70)
    if all_fixed and types_ok:
        print("✓ ALL CHECKS PASSED - READY FOR PR!")
        print("═" * 70)
        return 0
    else:
        print("✗ SOME CHECKS FAILED - PLEASE REVIEW")
        print("═" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
