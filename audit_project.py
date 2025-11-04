#!/usr/bin/env python3
"""
Project Audit Script for Trove Fetcher
Checks code quality, security, dependencies, testing, and documentation.
"""
import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# Colors for output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


# Audit Results
results = {"passed": [], "warnings": [], "errors": [], "info": []}


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    exists = Path(filepath).exists()
    if exists:
        print_success(f"{description}: {filepath}")
        results["passed"].append(f"{description} exists")
    else:
        print_warning(f"{description} missing: {filepath}")
        results["warnings"].append(f"{description} missing")
    return exists


def check_python_files() -> dict[str, Any]:
    """Check Python files for common issues."""
    print_header("Python Code Quality Audit")

    issues = defaultdict(list)
    python_files = []

    # Find all Python files
    for root, dirs, files in os.walk("."):
        # Skip virtual environments and cache
        if any(skip in root for skip in [".venv", "__pycache__", ".git", "node_modules"]):
            continue
        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)

    print_info(f"Found {len(python_files)} Python files")

    for py_file in python_files:
        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(py_file))

            # Check for common issues
            for node in ast.walk(tree):
                # Check for hardcoded API keys
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if (
                                "key" in target.id.lower()
                                or "secret" in target.id.lower()
                                or "token" in target.id.lower()
                            ):
                                if isinstance(node.value, ast.Str) or (
                                    isinstance(node.value, ast.Constant)
                                    and isinstance(node.value.value, str)
                                ):
                                    if (
                                        len(
                                            node.value.value
                                            if isinstance(node.value, ast.Constant)
                                            else node.value.s
                                        )
                                        > 10
                                    ):
                                        issues["hardcoded_secrets"].append(
                                            f"{py_file}:{node.lineno}"
                                        )

            # Check for missing docstrings in functions/classes
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node) and not node.name.startswith("_"):
                        if "test" not in py_file.name.lower():
                            issues["missing_docstrings"].append(f"{py_file}:{node.name}")

            # Check for bare except
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        issues["bare_except"].append(f"{py_file}:{node.lineno}")

        except SyntaxError as e:
            issues["syntax_errors"].append(f"{py_file}: {e}")
        except Exception as e:
            issues["parse_errors"].append(f"{py_file}: {e}")

    # Report issues
    if not issues:
        print_success("No code quality issues found")
        results["passed"].append("Code quality checks passed")
    else:
        for issue_type, items in issues.items():
            if issue_type == "hardcoded_secrets":
                print_error(f"Potential hardcoded secrets found ({len(items)}):")
                for item in items[:5]:  # Show first 5
                    print(f"  - {item}")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")
                results["errors"].append(f"Hardcoded secrets: {len(items)} found")

            elif issue_type == "missing_docstrings":
                print_warning(f"Missing docstrings ({len(items)}):")
                for item in items[:5]:
                    print(f"  - {item}")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")
                results["warnings"].append(f"Missing docstrings: {len(items)} found")

            elif issue_type == "bare_except":
                print_warning(f"Bare except clauses ({len(items)}):")
                for item in items[:5]:
                    print(f"  - {item}")
                results["warnings"].append(f"Bare except: {len(items)} found")

            elif issue_type in ["syntax_errors", "parse_errors"]:
                print_error(f"{issue_type.replace('_', ' ').title()} ({len(items)}):")
                for item in items:
                    print(f"  - {item}")
                results["errors"].extend(items)

    return issues


def check_dependencies() -> dict[str, Any]:
    """Check dependencies and requirements."""
    print_header("Dependencies Audit")

    deps_info = {}

    # Check requirements.txt
    req_file = Path("requirements.txt")
    if req_file.exists():
        print_success("requirements.txt found")
        with open(req_file) as f:
            deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print_info(f"Found {len(deps)} dependencies")

        # Check for security vulnerabilities (basic check)
        deps_without_version = []
        for dep in deps:
            if ">=" not in dep and "==" not in dep and "~=" not in dep:
                deps_without_version.append(dep)

        if deps_without_version:
            print_warning(f"Dependencies without version pins: {len(deps_without_version)}")
            for dep in deps_without_version:
                print(f"  - {dep}")
            results["warnings"].append(f"Unpinned dependencies: {len(deps_without_version)}")
        else:
            print_success("All dependencies have version pins")
            results["passed"].append("Dependencies properly pinned")

        deps_info["count"] = len(deps)
        deps_info["unpinned"] = len(deps_without_version)
    else:
        print_error("requirements.txt not found")
        results["errors"].append("requirements.txt missing")

    # Check for .env.example
    env_example = Path(".env.example")
    if env_example.exists():
        print_success(".env.example found")
        results["passed"].append(".env.example exists")
    else:
        print_warning(".env.example not found (recommended for documentation)")
        results["warnings"].append(".env.example missing")

    return deps_info


def check_testing() -> dict[str, Any]:
    """Check testing setup."""
    print_header("Testing Audit")

    test_info = {}

    # Check for test files
    test_files = list(Path(".").glob("test_*.py")) + list(Path(".").rglob("tests/**/*.py"))
    test_files = [f for f in test_files if "__pycache__" not in str(f)]

    if test_files:
        print_success(f"Found {len(test_files)} test file(s)")
        for tf in test_files:
            print(f"  - {tf}")
        results["passed"].append(f"Test files found: {len(test_files)}")
    else:
        print_warning("No test files found")
        results["warnings"].append("No test files found")

    # Check for pytest
    try:
        import pytest

        print_success("pytest is available")
        results["passed"].append("pytest available")
        test_info["pytest_available"] = True
    except ImportError:
        print_warning("pytest not installed (recommended for testing)")
        results["warnings"].append("pytest not installed")
        test_info["pytest_available"] = False

    # Check for test directory
    test_dir = Path("tests")
    if test_dir.exists():
        print_success("tests/ directory exists")
        results["passed"].append("tests/ directory exists")
    else:
        print_info("tests/ directory not found (consider creating for organized tests)")
        results["info"].append("tests/ directory missing")

    return test_info


def check_security() -> dict[str, Any]:
    """Security audit."""
    print_header("Security Audit")

    security_info = {}

    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        # Check if .env is in .gitignore
        gitignore = Path(".gitignore")
        if gitignore.exists():
            with open(gitignore) as f:
                gitignore_content = f.read()
                if ".env" in gitignore_content:
                    print_success(".env is in .gitignore")
                    results["passed"].append(".env properly ignored")
                else:
                    print_error(".env is NOT in .gitignore (security risk!)")
                    results["errors"].append(".env not in .gitignore")
        else:
            print_warning(".gitignore not found")
            results["warnings"].append(".gitignore missing")
    else:
        print_info(".env file not found (may be expected)")

    # Check for .cursorignore (should ignore .env)
    cursorignore = Path(".cursorignore")
    if cursorignore.exists():
        with open(cursorignore) as f:
            if ".env" in f.read():
                print_success(".env is in .cursorignore")
                results["passed"].append(".env in .cursorignore")
    else:
        print_info(".cursorignore not found")

    # Check for common security issues in code
    security_issues = []

    # Check main.py and other files for security headers, etc.
    main_py = Path("app/main.py")
    if main_py.exists():
        with open(main_py) as f:
            content = f.read()
            if "CORS" in content:
                print_success("CORS configuration found")
                results["passed"].append("CORS configured")
            else:
                print_info("CORS configuration not found (may be intentional)")

    security_info["issues"] = len(security_issues)
    return security_info


def check_documentation() -> dict[str, Any]:
    """Check documentation."""
    print_header("Documentation Audit")

    doc_info = {}

    # Check README
    readme = Path("README.md")
    if readme.exists():
        with open(readme) as f:
            readme_content = f.read()
            if len(readme_content) > 500:
                print_success("README.md exists and is substantial")
                results["passed"].append("README exists")
            else:
                print_warning("README.md is quite short")
                results["warnings"].append("README is short")
    else:
        print_error("README.md not found")
        results["errors"].append("README.md missing")

    # Check for docstrings in main modules
    main_files = [
        Path("app/main.py"),
        Path("app/trove_client.py"),
        Path("app/services.py"),
    ]

    docstring_count = 0
    for mf in main_files:
        if mf.exists():
            with open(mf) as f:
                content = f.read()
                if '"""' in content or "'''" in content:
                    docstring_count += 1

    if docstring_count == len([f for f in main_files if f.exists()]):
        print_success("Main modules have docstrings")
        results["passed"].append("Main modules documented")
    else:
        print_warning(
            f"Some main modules may be missing docstrings ({docstring_count}/{len([f for f in main_files if f.exists()])})"
        )
        results["warnings"].append("Some modules missing docstrings")

    doc_info["readme_exists"] = readme.exists()
    doc_info["docstring_coverage"] = docstring_count

    return doc_info


def check_project_structure() -> dict[str, Any]:
    """Check project structure."""
    print_header("Project Structure Audit")

    structure_info = {}

    # Check key directories
    key_dirs = ["app", "templates", "static"]
    for dir_name in key_dirs:
        if Path(dir_name).exists():
            print_success(f"{dir_name}/ directory exists")
            results["passed"].append(f"{dir_name}/ exists")
        else:
            print_warning(f"{dir_name}/ directory missing")
            results["warnings"].append(f"{dir_name}/ missing")

    # Check key files
    key_files = {
        "app/main.py": "Main application file",
        "requirements.txt": "Dependencies file",
        "README.md": "Documentation",
    }

    for file_path, description in key_files.items():
        check_file_exists(file_path, description)

    return structure_info


def generate_summary():
    """Generate audit summary."""
    print_header("Audit Summary")

    total_passed = len(results["passed"])
    total_warnings = len(results["warnings"])
    total_errors = len(results["errors"])
    total_info = len(results["info"])

    print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
    print(f"{Colors.GREEN}✅ Passed: {total_passed}{Colors.RESET}")
    print(f"{Colors.YELLOW}⚠️  Warnings: {total_warnings}{Colors.RESET}")
    print(f"{Colors.RED}❌ Errors: {total_errors}{Colors.RESET}")
    print(f"{Colors.BLUE}ℹ️  Info: {total_info}{Colors.RESET}")

    if total_errors == 0 and total_warnings == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✨ Excellent! No issues found.{Colors.RESET}")
    elif total_errors == 0:
        print(
            f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some warnings to address, but no critical errors.{Colors.RESET}"
        )
    else:
        print(
            f"\n{Colors.RED}{Colors.BOLD}❌ Critical issues found. Please address errors first.{Colors.RESET}"
        )

    # Recommendations
    if total_warnings > 0 or total_errors > 0:
        print(f"\n{Colors.BOLD}Recommendations:{Colors.RESET}")

        if any("test" in w.lower() for w in results["warnings"]):
            print("  - Consider adding pytest and writing unit tests")

        if any("docstring" in w.lower() for w in results["warnings"]):
            print("  - Add docstrings to functions and classes for better documentation")

        if any("secret" in e.lower() for e in results["errors"]):
            print("  - Remove any hardcoded secrets from code")

        if any(".env" in e.lower() for e in results["errors"]):
            print("  - Ensure .env is in .gitignore to prevent committing secrets")


def main():
    """Run all audits."""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 60)
    print("  TROVE FETCHER PROJECT AUDIT")
    print("=" * 60)
    print(f"{Colors.RESET}")

    # Run all audits
    check_project_structure()
    check_dependencies()
    check_python_files()
    check_testing()
    check_security()
    check_documentation()

    # Generate summary
    generate_summary()

    # Exit code
    if len(results["errors"]) > 0:
        sys.exit(1)
    elif len(results["warnings"]) > 0:
        sys.exit(0)  # Warnings are OK, but inform user
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
