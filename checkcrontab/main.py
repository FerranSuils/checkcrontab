#!/usr/bin/env python3
"""
Main entry point for checkcrontab
"""

import argparse
import glob
import json
import logging
import os
import platform
import re
import sys
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    # Use as python3 -m checkcrontab  # type: ignore
    from . import __description__ as DESCRIPTION  # type: ignore
    from . import __url__ as REPO_URL  # type: ignore
    from . import __version__ as VERSION  # type: ignore
    from . import checker  # type: ignore
    from . import logger as log
except ImportError:
    # Use as python3 checkcrontab/main.py
    try:
        from checkcrontab import __description__ as DESCRIPTION
        from checkcrontab import __url__ as REPO_URL
        from checkcrontab import __version__ as VERSION
        from checkcrontab import (
            checker,  # type: ignore[import-not-found,no-redef]
        )
        from checkcrontab import (
            logger as log,  # type: ignore[import-not-found,no-redef]
        )
    except Exception as e:
        logging.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        sys.exit(2)

logger = logging.getLogger(__name__)

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"


def _line_numbers(messages: List[str]) -> Set[int]:
    """Line numbers mentioned in checker messages, ignoring the newline rule."""
    numbers: Set[int] = set()
    for message in messages:
        if "File should end with newline" in message:
            continue
        match = re.search(r"Line (\d+)", message)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def inspect_files(
    files_list: List[Tuple[str, bool]],
    files_temp: List[str],
    permission_paths: Set[str],
    output_format: str,
    scheduler_warnings: List[str],
) -> Tuple[int, int, int, int, List[str], List[str], List[Dict[str, Any]]]:
    """Check each requested file and return totals plus per-file records."""
    total_rows = 0
    total_rows_errors = 0
    total_errors = 0
    total_warnings = len(scheduler_warnings)
    all_errors: List[str] = []
    all_warnings: List[str] = list(scheduler_warnings)
    records: List[Dict[str, Any]] = []

    for path, is_system_crontab in files_list:
        if not os.path.exists(path):
            missing = [f"File {path} does not exist"]
            records.append(
                {
                    "file": path,
                    "is_system_crontab": is_system_crontab,
                    "rows": 0,
                    "rows_warnings": 0,
                    "warnings_count": 0,
                    "rows_errors": 0,
                    "errors_count": 1,
                    "errors": missing,
                    "success": False,
                }
            )
            total_errors += 1
            all_errors.extend(missing)
            if output_format == "text":
                logger.error(missing[0])
            continue

        if path not in files_temp:
            filename_error = checker.check_filename(os.path.basename(path))
            if filename_error:
                formatted = f"{os.path.basename(path)} (Line 0): {filename_error}"
                records.append(
                    {
                        "file": path,
                        "is_system_crontab": is_system_crontab,
                        "rows": 0,
                        "rows_warnings": 0,
                        "warnings_count": 0,
                        "rows_errors": 1,
                        "errors_count": 1,
                        "errors": [formatted],
                        "success": False,
                    }
                )
                all_errors.append(formatted)
                total_errors += 1
                if output_format == "text":
                    logger.error(filename_error)
                continue

        file_level_errors: List[str] = []
        enforce_permissions = os.path.abspath(path) in permission_paths or checker.is_installed_system_crontab(path)
        if is_system_crontab and enforce_permissions:
            for err in checker.check_owner_and_permissions(path):
                err_msg = f"{os.path.basename(path)} (Line 0): {err}"
                logger.error(err_msg)
                file_level_errors.append(err_msg)

        rows_checked, file_errors, file_warnings = check_file(path, is_system_crontab=is_system_crontab)
        if file_level_errors:
            file_errors = file_errors + file_level_errors

        total_rows += rows_checked
        total_errors += len(file_errors)
        total_warnings += len(file_warnings)
        all_errors.extend(file_errors)
        all_warnings.extend(file_warnings)
        rows_errors = len(_line_numbers(file_errors))
        total_rows_errors += rows_errors
        records.append(
            {
                "file": path,
                "is_system_crontab": is_system_crontab,
                "rows": rows_checked,
                "rows_warnings": len(_line_numbers(file_warnings)),
                "warnings_count": len(file_warnings),
                "warnings": file_warnings,
                "rows_errors": rows_errors,
                "errors_count": len(file_errors),
                "errors": file_errors,
                "success": len(file_errors) == 0,
            }
        )
        if output_format == "text" and file_errors:
            logger.error(f"{path}: {rows_errors}/{rows_checked} lines with errors. Total {len(file_errors)} errors.")
        elif output_format == "text":
            logger.info(f"{path}: 0/{rows_checked} lines without errors. No errors.")

    return total_rows, total_rows_errors, total_errors, total_warnings, all_errors, all_warnings, records


def check_file(file_path: str, is_system_crontab: bool = False) -> Tuple[int, List[str], List[str]]:
    """
    Check crontab file line by line
    Returns: (rows_checked_count, errors_list, warnings_list)
    """
    errors: List[str] = []
    warnings: List[str] = []
    rows_checked = 0

    try:
        with open(file_path) as f:
            lines = f.readlines()
    except Exception as e:
        logging.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 0, [f"Error reading file: {e}"], []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        line_number = i + 1

        # Handle multi-line commands
        if line.endswith("\\"):
            # Collect continuation lines
            full_line = line[:-1]  # Remove trailing backslash
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")):
                continuation = lines[i].rstrip("\n")
                if continuation.endswith("\\"):
                    full_line += "\n" + continuation[:-1]
                    i += 1
                else:
                    full_line += "\n" + continuation
                    i += 1
                    break
            line = full_line
        else:
            i += 1

        # Skip continuation lines that were already processed
        if line.startswith((" ", "\t")) and not line.strip():
            continue

        # Skip empty lines and comments
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if stripped_line.startswith("#"):
            continue

        # This is a line to check
        rows_checked += 1

        # Check line using unified function with system crontab flag
        line_errors, line_warnings = checker.check_line(line, line_number, os.path.basename(file_path), file_path, is_system_crontab=is_system_crontab)

        # Output result immediately in order of processing
        line_content = checker.get_line_content(file_path, line_number) if file_path else line
        line_content = checker.clean_line_for_output(line_content)

        if line_errors:
            # Output all errors for this line
            for error in line_errors:
                logger.error(error)
            errors.extend(line_errors)

        if line_warnings:
            for warning in line_warnings:
                logger.warning(warning)
            warnings.extend(line_warnings)
        if logger.isEnabledFor(logging.DEBUG) and not line_errors and not line_warnings:
            # Output valid lines in debug mode
            logger.debug(f"{os.path.basename(file_path)} (Line {line_number}): {line_content} # valid")

    # Check if file ends with newline (RFC compliance)
    if lines and not lines[-1].endswith("\n"):
        error_msg = f"{os.path.basename(file_path)} (Line {len(lines) + 1}): File should end with newline"
        errors.append(error_msg)
        logger.error(error_msg)

    return rows_checked, errors, warnings


def find_user_crontab(username: str) -> Optional[str]:
    """Find user crontab file path or get content via crontab command"""
    for path in checker.user_crontab_paths(username):
        if os.path.exists(path):
            return path

    # If no file found, try to get via crontab command
    crontab_content = checker.get_crontab(username)
    if crontab_content:
        # Create temporary file with crontab content (context manager per SIM115)
        with tempfile.NamedTemporaryFile(mode="w", suffix=f".{username}", delete=False) as tmp:
            tmp.write(crontab_content)
            temp_path = tmp.name
        return temp_path
    return None


def gen_sarif_output(files_data: List[Dict[str, Any]], total_errors: int, total_warnings: int = 0) -> Dict[str, Any]:
    """Generate SARIF format output"""
    results = []

    for file_data in files_data:
        file_path = file_data["file"]
        errors = file_data.get("errors", [])

        for error in errors:
            # Parse error message to extract line number and message
            line_match = re.search(r"Line (\d+):", error)
            line_number = int(line_match.group(1)) if line_match else 1

            # Extract the actual error message
            message_match = re.search(r"# (.+)$", error)
            message = message_match.group(1) if message_match else error

            result = {
                "ruleId": "crontab-syntax-error",
                "level": "error",
                "message": {"text": message},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": file_path}, "region": {"startLine": line_number, "startColumn": 1}}}],
            }
            results.append(result)

    sarif_output = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "checkcrontab",
                        "version": VERSION,
                        "informationUri": REPO_URL,
                    }
                },
                "results": results,
            }
        ],
    }

    return sarif_output


def get_files(path: str) -> Tuple[List[str], List[str]]:
    """Get list of files from path (file or directory)"""
    files = []
    errors = []
    if not os.path.exists(path):
        # Path does not exist; no files to add.
        pass
    elif os.path.isfile(path):
        files.append(path)
    elif os.path.isdir(path):
        for file in glob.glob(os.path.join(path, "*")):
            if os.path.isfile(file):
                base = os.path.basename(file)
                error = checker.check_filename(base)
                if not error:
                    files.append(file)
                else:
                    errors.append(error)
    return files, errors


def main() -> int:
    """Main function"""
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
    %(prog)s                                  # Check system crontab
    %(prog)s filename                         # Check system and file crontab
    %(prog)s username                         # Check system and user crontab
    %(prog)s file1 file2 username             # Check multiple files and user crontab
    %(prog)s -S file1 -U file2 -u username    # Check crontab with type flags
    %(prog)s -u username1 -u username2        # Check specific usernames
    %(prog)s filename -j | jq '.total_errors' # Check crontab and return JSON
        """,
    )

    parser.add_argument("arguments", nargs="*", help="Paths to crontab files or usernames")
    parser.add_argument("-S", "--system", action="append", metavar="FILENAME", help="System crontab files")
    parser.add_argument("-U", "--user", action="append", metavar="FILENAME", help="User crontab files")
    parser.add_argument("-u", "--username", action="append", metavar="USERNAME", help="Usernames to check")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + VERSION)
    parser.add_argument("-d", "--debug", action="store_true", help="Debug output")
    parser.add_argument("-n", "--no-colors", action="store_true", help="Disable colored output")
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format (default: text)")
    parser.add_argument("-j", dest="format", action="store_const", const="json", help="Shortcut for JSON output (same as --format json)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--exit-zero", action="store_true", help="Always exit with code 0")

    args = parser.parse_args()

    # Setup logging
    log.setup_logging(args.debug, args.no_colors, args.format in ["json", "sarif"])

    # Prepare list of files to check with their types
    files_list: List[Tuple[str, bool]] = []  # (file_path, is_system_crontab)
    files_temp: List[str] = []  # Track temporary files for cleanup
    permission_paths: Set[str] = set()

    # Add files with explicit flags
    if args.system:
        for path in args.system:
            if os.path.isdir(path):
                files, warnings = get_files(path)
                for warning in warnings:
                    logger.warning(warning)
                for file in files:
                    files_list.append((file, True))
                    permission_paths.add(os.path.abspath(file))
            else:
                files_list.append((path, True))
                permission_paths.add(os.path.abspath(path))

    if args.user:
        for path in args.user:
            files_list.append((path, False))

    # Add usernames with explicit flag
    if args.username:
        for username in args.username:
            crontab_path = find_user_crontab(username)
            if crontab_path:
                files_temp.append(crontab_path)
                files_list.append((crontab_path, False))  # User crontab
                logger.info(f"Found user crontab for {username}: {crontab_path}")
            else:
                logger.warning(f"User crontab not found for: {username}")

    # Add arguments with smart detection
    for path in args.arguments:
        if os.path.isfile(path):
            # First check if it's an existing file
            full_path = os.path.abspath(path)
            is_system_crontab = checker.is_system_crontab_path(full_path)
            files_list.append((full_path, is_system_crontab))
        elif os.path.isdir(path):
            # If directory, add all files inside as system crontabs
            files, warnings = get_files(path)
            for warning in warnings:
                logger.warning(warning)
            for file in files:
                full_path = os.path.abspath(file)
                is_system_crontab = checker.is_system_crontab_path(full_path)
                files_list.append((full_path, is_system_crontab))
        elif re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$").match(path):
            # If not a file, treat as username
            crontab_path = find_user_crontab(path)
            if crontab_path:
                files_temp.append(crontab_path)
                files_list.append((crontab_path, False))  # User crontab
                logger.info(f"{path} user found: {crontab_path}")
            else:
                logger.warning(f"{path} user not found or has no crontab")
        else:
            logger.warning(f"{path} File not found and is not a valid username")

    # Service manager and scheduler status on Linux, macOS, and Windows.
    # Skipped in GitHub Actions, where those managers are not the thing under test.
    logger.debug(f"Platform: {platform.system()}")
    scheduler_warnings: List[str] = []
    if os.getenv("GITHUB_ACTIONS") != "true":
        for warning in checker.check_services() + checker.check_daemon():
            logger.warning(warning)
            scheduler_warnings.append(warning)

    no_targets = not args.system and not args.user and not args.username and not args.arguments
    if no_targets and not files_list:
        system_path = checker.find_system_crontab()
        if system_path:
            files_list.append((system_path, True))
            logger.info(f"Using system crontab: {system_path}")

    if len(files_list) == 0:
        logger.warning("No files to check.")

    # Remove duplicates while preserving order
    seen = set()
    unique_file_list: List[Tuple[str, bool]] = []
    for path, is_system in files_list:
        if path not in seen:
            seen.add(path)
            unique_file_list.append((path, is_system))
    files_list = unique_file_list

    total_rows, total_rows_errors, total_errors, total_warnings, all_errors, all_warnings, records = inspect_files(
        files_list, files_temp, permission_paths, args.format, scheduler_warnings
    )
    strict_failed = args.strict and total_warnings > 0
    output_data: Dict[str, Any] = {
        "success": total_errors == 0 and not strict_failed,
        "total_files": len(files_list),
        "total_rows": total_rows,
        "total_rows_errors": total_rows_errors,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "warnings": all_warnings,
        "rows_errors": len(_line_numbers(all_errors)),
        "files": records,
    }

    # Generate output based on format
    if args.format == "json":
        print(json.dumps(output_data, indent=2))
    elif args.format == "sarif":
        sarif_output = gen_sarif_output(output_data["files"], total_errors)
        print(json.dumps(sarif_output, indent=2))
    # Standard output
    elif total_errors == 0 and not strict_failed:
        if total_warnings:
            logger.info(f"All checks passed with {total_warnings} warnings.")
        else:
            logger.info("All checks passed successfully!")
    elif total_errors == 0:
        logger.error(f"Total: {total_warnings} warnings treated as errors")
    else:
        logger.error(f"Total: {len(_line_numbers(all_errors))} lines with errors found in {total_rows} checked lines")

    # Clean up temporary files
    for temp_file in files_temp:
        try:
            os.unlink(temp_file)
        except Exception as e:
            logger.debug(f"Failed to remove temporary file {temp_file}: {e}")

    # Determine exit code based on flags and results
    if args.exit_zero:
        return 0

    # Count warnings if in strict mode
    total_issues = total_errors + total_warnings if args.strict else total_errors

    if total_issues == 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
