#!/usr/bin/env python3
"""
Module for checking crontab syntax and system requirements
"""

import logging
import os
import platform
import re
import stat
import subprocess
import traceback
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Constants for validation
RANGE_PARTS_COUNT = 2
CRONTAB_PERMISSIONS = 0o644
CRONTAB_OWNER_UID = int(os.getenv("CRONTAB_OWNER_UID", "0"))
USER_CRONTAB_MIN_FIELDS = 6
SYSTEM_CRONTAB_MIN_FIELDS = 7
SYSTEM_CRONTAB_MAX_FIELDS = 7
SPECIAL_KEYWORD_MIN_FIELDS = 2
USER_SPECIAL_MIN_FIELDS = 2
SYSTEM_SPECIAL_MIN_FIELDS = 3
WINDOWS_MAJOR_VERSION = 10
WINDOWS_BUILD_VERSION = 10586
MACOS_CRON_LABELS = ("com.vix.cron", "com.apple.cron")
LAUNCHCTL_LIST_COLUMNS = 3
WINDOWS_CRON_SERVICES = ("cron", "CronDaemon", "cygcron")
WINDOWS_BUILTIN_USERS = {"system", "local service", "network service", "localsystem", "administrator", "administrators"}
_ACL_INHERIT_TOKENS = {"I", "OI", "CI", "IO", "NP", "ID"}
_ACL_WRITE_RIGHTS = {"F", "M", "W", "D", "WDAC", "DC", "WD", "WEA", "WA", "GW"}
_WINDOWS_TRUSTED_OWNERS = {"system", "administrators", "administrator", "trustedinstaller", "localsystem"}

# Regex patterns for time fields
MINUTE_PATTERN = r"^(\*|([0-5]?[0-9])(-([0-5]?[0-9]))?(/([0-9]+))?(,([0-5]?[0-9])(-([0-5]?[0-9]))?(/([0-9]+))?)*|\*/([0-9]+))$"
HOUR_PATTERN = r"^(\*|([0-9]|1[0-9]|2[0-3])(-([0-9]|1[0-9]|2[0-3]))?(/([0-9]|1[0-9]|2[0-3]))?(,([0-9]|1[0-9]|2[0-3])(-([0-9]|1[0-9]|2[0-3]))?(/([0-9]|1[0-9]|2[0-3]))?)*|\*/([0-9]|1[0-9]|2[0-3]))$"
DAY_PATTERN = r"^(\*|([1-9]|[12][0-9]|3[01])(-([1-9]|[12][0-9]|3[01]))?(/([1-9]|[12][0-9]|3[01]))?(,([1-9]|[12][0-9]|3[01])(-([1-9]|[12][0-9]|3[01]))?(/([1-9]|[12][0-9]|3[01]))?)*|\*/([1-9]|[12][0-9]|3[01]))$"
MONTH_PATTERN = r"^(\*|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/([1-9]|1[0-2]))?(,([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/([1-9]|1[0-2]))?)*|\*/([1-9]|1[0-2]))$"
WEEKDAY_PATTERN = r"^(\*|([0-7])(-([0-7]))?(/([0-7]))?(,([0-7])(-([0-7]))?)*|\*/([0-7]))$"
MONTH_NAMES: Dict[str, str] = {
    "jan": "1",
    "feb": "2",
    "mar": "3",
    "apr": "4",
    "may": "5",
    "jun": "6",
    "jul": "7",
    "aug": "8",
    "sep": "9",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}
WEEKDAY_NAMES: Dict[str, str] = {
    "sun": "0",
    "mon": "1",
    "tue": "2",
    "wed": "3",
    "thu": "4",
    "fri": "5",
    "sat": "6",
}
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
USERNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,31}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CRON_NOT_RUNNING = "Cron daemon: is not running"
INVALID_NAME_ALLOWED_RE = r"^[A-Za-z0-9_-]+$"


def check_filename(file_path: str) -> str:
    """
    Validate cron filename (use basename). Return a list of error strings.
    Rules per man 8 cron / man 5 crontab:
      - ignore: names containing '.'; ending with '~'; containing '#', ',';
      - starting with '.' (hidden);
      - only [A-Za-z0-9_-] are allowed (everything else is invalid).
    """
    name = os.path.basename(file_path or "")
    if not name:
        return f"{file_path} empty name filename"
    if name.startswith("."):
        return f"{name} wrong filename: starts with '.'"
    if name.endswith("~"):
        return f"{name} wrong filename: ends with '~'"
    if "." in name:
        return f"{name} wrong filename contains '.'"
    if "#" in name:
        return f"{name} wrong filename contains '#'"
    if "," in name:
        return f"{name} wrong filename contains ','"
    regexp = re.compile(INVALID_NAME_ALLOWED_RE)
    if not regexp.match(name):
        return f"invalid filename '{name}': contains characters outside [A-Za-z0-9_-]"
    return ""


def _tool_errors(exc: Exception, tool: str, prefix: str) -> List[str]:
    """Map a service-manager failure to a stable error string."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return [f"{prefix}: timeout"]
    if isinstance(exc, FileNotFoundError):
        return [f"{prefix}: {tool} not found"]
    return [f"{prefix}: {type(exc).__name__}"]


def _run_command(cmd: List[str], timeout: int = 5) -> "subprocess.CompletedProcess[str]":
    """Run a command and capture text output."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def system_crontab_paths() -> List[str]:
    """Platform locations of the system crontab, including CRONTAB_SYSTEM_PATH."""
    paths: List[str] = []
    override = os.getenv("CRONTAB_SYSTEM_PATH")
    if override:
        paths.append(override)
    system = platform.system().lower()
    if system == "windows":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        paths.extend(
            [
                os.path.join(program_data, "crontab"),
                os.path.join(program_data, "cron", "crontab"),
                os.path.join(system_root, "System32", "crontab"),
                r"C:\etc\crontab",
                r"C:\cygwin64\etc\crontab",
                r"C:\cygwin\etc\crontab",
                r"C:\msys64\etc\crontab",
            ]
        )
    else:
        paths.append("/etc/crontab")
        if system == "darwin":
            paths.append("/private/etc/crontab")
    unique: List[str] = []
    seen: Set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.normpath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_system_crontab() -> Optional[str]:
    """Return the first system crontab that exists on this machine."""
    for path in system_crontab_paths():
        if os.path.isfile(path):
            return path
    return None


def _system_cron_directories() -> List[str]:
    """Directories whose files use the system crontab field layout."""
    directories = ["/etc/cron.d", "/private/etc/cron.d"]
    if platform.system().lower() == "windows":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        directories.extend(
            [
                os.path.join(program_data, "cron", "cron.d"),
                os.path.join(program_data, "cron.d"),
                r"C:\etc\cron.d",
                r"C:\cygwin64\etc\cron.d",
                r"C:\cygwin\etc\cron.d",
                r"C:\msys64\etc\cron.d",
            ]
        )
    return directories


def is_installed_system_crontab(file_path: str) -> bool:
    """True for an installed system crontab, where owner and mode are enforced."""
    if not file_path:
        return False
    normalized = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))
    for candidate in system_crontab_paths():
        candidate_norm = os.path.normcase(os.path.normpath(os.path.abspath(candidate)))
        if normalized == candidate_norm:
            return True
    posix = file_path.replace("\\", "/")
    if posix in ("/etc/crontab", "/private/etc/crontab"):
        return True
    parent = os.path.normcase(os.path.normpath(os.path.dirname(normalized)))
    for directory in _system_cron_directories():
        directory_norm = os.path.normcase(os.path.normpath(os.path.abspath(directory)))
        if parent == directory_norm:
            return True
    return False


def is_system_crontab_path(file_path: str) -> bool:
    """True when the path uses the system crontab field layout."""
    if not file_path:
        return False
    if "system" in os.path.basename(file_path).lower():
        return True
    return is_installed_system_crontab(file_path)


def user_crontab_paths(username: str) -> List[str]:
    """Filesystem locations checked before `crontab -l -u`."""
    paths = [
        f"/usr/lib/cron/tabs/{username}",
        f"/var/spool/cron/crontabs/{username}",
        f"/var/spool/cron/{username}",
        f"/tmp/crontab.{username}",
    ]
    if platform.system().lower() != "windows":
        return paths
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    local_app = os.environ.get("LOCALAPPDATA", "")
    paths.extend(
        [
            os.path.join(program_data, "cron", "crontabs", username),
            os.path.join(program_data, "crontab", username),
            os.path.join(r"C:\var\spool\cron\crontabs", username),
            os.path.join(r"C:\var\spool\cron", username),
            os.path.join(r"C:\cygwin64\var\spool\cron\crontabs", username),
            os.path.join(r"C:\msys64\var\spool\cron\crontabs", username),
        ]
    )
    if local_app:
        paths.append(os.path.join(local_app, "cron", username))
    return paths


def _check_services_linux() -> List[str]:
    try:
        result = _run_command(["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"])
        if result.returncode != 0:
            return ["Daemon/service: systemctl could not list services"]
        logger.debug("Daemon/service: systemd is reachable")
    except Exception as exc:
        return _tool_errors(exc, "systemctl", "Daemon/service")
    return []


def _check_services_darwin() -> List[str]:
    try:
        result = _run_command(["launchctl", "list"])
        if result.returncode != 0:
            return ["Daemon/service: launchctl could not query launchd"]
        logger.debug("Daemon/service: launchd is reachable")
    except Exception as exc:
        return _tool_errors(exc, "launchctl", "Daemon/service")
    return []


def _check_services_windows() -> List[str]:
    try:
        result = _run_command(["sc", "query", "type=", "service", "state=", "all"])
        if result.returncode != 0:
            return ["Daemon/service: sc could not query the service manager"]
        logger.debug("Daemon/service: Service Control Manager is reachable")
    except Exception as exc:
        return _tool_errors(exc, "sc", "Daemon/service")
    return []


def check_services() -> List[str]:
    """Check that the platform service manager answers (systemd, launchd, or SCM)."""
    system = platform.system().lower()
    if system == "windows":
        return _check_services_windows()
    if system == "darwin":
        return _check_services_darwin()
    return _check_services_linux()


def _linux_cron_active() -> bool:
    for unit in ("cron", "crond"):
        result = _run_command(["systemctl", "is-active", unit])
        if result.returncode == 0 and result.stdout.strip() == "active":
            return True
    return False


def _daemon_status(active: bool) -> List[str]:
    if active:
        logger.debug("Cron daemon: is active")
        return []
    return [CRON_NOT_RUNNING]


def _check_daemon_linux() -> List[str]:
    try:
        return _daemon_status(_linux_cron_active())
    except Exception as exc:
        return _tool_errors(exc, "systemctl", "Cron daemon")


def _macos_cron_running(stdout: str) -> bool:
    running = False
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) < LAUNCHCTL_LIST_COLUMNS or parts[-1] not in MACOS_CRON_LABELS:
            continue
        if parts[0].isdigit() and int(parts[0]) > 0:
            running = True
    return running


def _check_daemon_darwin() -> List[str]:
    try:
        result = _run_command(["launchctl", "list"])
        active = result.returncode == 0 and _macos_cron_running(result.stdout)
        return _daemon_status(active)
    except Exception as exc:
        return _tool_errors(exc, "launchctl", "Cron daemon")


def _service_is_running(name: str) -> bool:
    result = _run_command(["sc", "query", name])
    text = result.stdout.upper()
    if re.search(r"(STATE|ESTADO|ÉTAT|STATUS)\s*:\s*\d+\s+(RUNNING|EJECUT)", text):
        return True
    return "RUNNING" in text or "EJECUTANDO" in text


def _check_daemon_windows() -> List[str]:
    try:
        schedule_running = _service_is_running("Schedule")
        cron_running = (not schedule_running) and any(_service_is_running(name) for name in WINDOWS_CRON_SERVICES)
        return _daemon_status(schedule_running or cron_running)
    except Exception as exc:
        return _tool_errors(exc, "sc", "Cron daemon")


def check_daemon() -> List[str]:
    """Check whether the platform scheduler is running."""
    system = platform.system().lower()
    if system == "windows":
        return _check_daemon_windows()
    if system == "darwin":
        return _check_daemon_darwin()
    return _check_daemon_linux()


def check_kind(path: str, follow_symlink: bool = True) -> str:
    """Determine the kind of file at the given path"""
    # is_link = os.path.islink(path)
    st = os.stat(path) if follow_symlink else os.lstat(path)
    m = st.st_mode
    # Check if regular file
    if stat.S_ISREG(m):
        return "regular_file"
    if stat.S_ISDIR(m):
        return "directory"
    if stat.S_ISLNK(m):
        return "symlink"
    if stat.S_ISCHR(m):
        return "char_device"
    if stat.S_ISBLK(m):
        return "block_device"
    if stat.S_ISSOCK(m):
        return "socket"
    if stat.S_ISFIFO(m):
        return "fifo"
    return "unknown"


def _ace_allows_write(ace: str) -> bool:
    tokens = [token.upper() for token in re.findall(r"[A-Za-z]+", ace)]
    rights = [token for token in tokens if token not in _ACL_INHERIT_TOKENS]
    return any(right in _ACL_WRITE_RIGHTS for right in rights)


def _is_world_principal(line: str) -> bool:
    lowered = line.lower()
    markers = ("everyone:", "authenticated users:", "usuarios autentificados:", "builtin\\users:", "\\users:")
    return any(marker in lowered for marker in markers)


def _windows_owner_ok(owner: str) -> bool:
    leaf = owner.lower().replace("/", "\\").split("\\")[-1].strip()
    return leaf in _WINDOWS_TRUSTED_OWNERS


def _windows_owner(file_path: str) -> str:
    safe = file_path.replace("'", "''")
    script = f"(Get-Acl -LiteralPath '{safe}').Owner"
    try:
        result = _run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=8)
    except (subprocess.SubprocessError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _check_windows_permissions(file_path: str) -> List[str]:
    """Validate a crontab ACL: not world-writable, owned by Administrators or SYSTEM."""
    errors: List[str] = []
    try:
        if os.path.islink(file_path):
            target_path = os.path.realpath(file_path)
            if not os.path.exists(target_path):
                errors.append(f"broken symlink ({target_path} does not exist)")
                return errors
        else:
            target_path = file_path
        file_kind = check_kind(target_path)
        if file_kind != "regular_file":
            errors.append(f"{target_path}({file_kind}): not a regular_file.")
            return errors
        result = _run_command(["icacls", target_path])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "icacls failed").strip()
            errors.append(f"failed to read permissions: {detail}")
            return errors
        for line in result.stdout.splitlines():
            aces = re.findall(r"\(([^)]*)\)", line)
            if _is_world_principal(line) and any(_ace_allows_write(ace) for ace in aces):
                errors.append(f"wrong permissions (world-writable ACL): icacls {target_path}")
                break
        owner = _windows_owner(target_path)
        if owner and not _windows_owner_ok(owner):
            errors.append(f"crontab wrong owner: icacls {target_path} /setowner Administrators")
    except Exception as exc:
        errors.extend(_tool_errors(exc, "icacls", "File permissions"))
    return errors


def check_owner_and_permissions(file_path: str, owner_uid: int = CRONTAB_OWNER_UID) -> List[str]:
    """Check owner and file permissions"""
    errors: List[str] = []
    if not os.path.lexists(file_path):
        errors.append(f"{file_path}: file does not exist")
        return errors
    if platform.system().lower() == "windows":
        return _check_windows_permissions(file_path)
    try:
        if os.path.islink(file_path):
            try:
                link_stat = os.lstat(file_path)  # symlink inode (do not follow)
                if link_stat.st_uid != owner_uid:
                    errors.append(f"wrong symlink owner: sudo chown -h root:root {file_path}")
                else:
                    logger.debug("symlink correct owner")
            except Exception as e:
                errors.append(f"failed to stat symlink: {e}")
                # If we can't lstat the link, further checks don't make sense
                return errors
            target_path = os.path.realpath(file_path)
            if not os.path.exists(target_path):
                errors.append(f"broken symlink ({target_path} does not exist)")
                return errors
        else:
            target_path = file_path
        file_kind = check_kind(target_path)
        if file_kind != "regular_file":
            errors.append(f"{target_path}({file_kind}): not a regular_file.")
        stat_info = os.stat(target_path)
        mode = stat_info.st_mode & 0o777
        if mode != CRONTAB_PERMISSIONS:
            errors.append(f"wrong permissions ({oct(mode)}): sudo chmod 644 {target_path}")
        else:
            logger.debug(f"correct permissions: {oct(mode)}")
        if stat_info.st_uid != owner_uid:
            errors.append(f"crontab wrong owner: sudo chown root:root {target_path}")
        else:
            logger.debug("crontab correct owner:")
    except Exception as e:
        errors.append(f"{e}")
    return errors


def get_line_content(file_path: str, line_number: int) -> str:
    """Get line content from file"""
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1].rstrip("\n")
        return ""
    except Exception as e:
        logging.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return ""


def clean_line_for_output(line: str) -> str:
    """Clean line for output: replace tabs and multiple spaces with single spaces"""
    # Replace tabs with spaces
    line = line.replace("\t", " ")
    # Replace multiple spaces with single space
    line = re.sub(r" +", " ", line)
    return line


def check_dangerous_commands(command: str) -> List[str]:
    """Check for dangerous commands in crontab"""
    errors = []
    dangerous_patterns = [
        (r"\brm\s+-rf\s+/", "dangerous command: 'rm -rf /'"),
        (r"\bmkfs(?:\.[a-z0-9]+)?\s+/dev/", "dangerous command: 'mkfs'"),
        (r"\bdd\b[^\n]*\bif=/dev/(?:zero|urandom|random)\b", "dangerous command: 'dd' from a device source"),
        (r":\(\)\s*\{\s*:\|:&\s*\};:", "dangerous command: fork bomb"),
        (r"\bchmod\s+-R\s+777\s+/", "dangerous command: 'chmod -R 777 /'"),
    ]

    for pattern, message in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            errors.append(message)
            break  # Only report one error per dangerous command

    return errors


def check_minutes(minute: str, is_system_crontab: bool = False) -> List[str]:
    """Check minutes field validation"""
    errors = []

    # Handle dash prefix in minutes field (suppress syslog logging) - only for system crontab
    original_minute = minute
    if is_system_crontab and minute.startswith("-"):
        minute = minute[1:]  # Remove the dash prefix

    logic_errors = validate_time_field_logic(minute, "minutes", 0, 59)
    if logic_errors:
        errors.extend(logic_errors)
    elif not re.match(MINUTE_PATTERN, minute):
        errors.append(f"invalid minute format: '{original_minute}'")

    return errors


def check_hours(hour: str) -> List[str]:
    """Check hours field validation"""
    errors = []

    logic_errors = validate_time_field_logic(hour, "hours", 0, 23)
    if logic_errors:
        errors.extend(logic_errors)
    elif not re.match(HOUR_PATTERN, hour):
        errors.append(f"invalid hour format: '{hour}'")

    return errors


def check_day_of_month(day: str) -> List[str]:
    """Check day of month field validation"""
    errors = []

    logic_errors = validate_time_field_logic(day, "day of month", 1, 31)
    if logic_errors:
        errors.extend(logic_errors)
    elif not re.match(DAY_PATTERN, day):
        errors.append(f"invalid day of month format: '{day}'")

    return errors


def canonicalize_names(value: str, names: Dict[str, str]) -> str:
    """Replace cron month or weekday names with their numbers."""
    if not re.search(r"[A-Za-z]", value):
        return value
    words = re.findall(r"[A-Za-z]+", value)
    if any(word.lower() not in names for word in words):
        return value

    def replace(match: "re.Match[str]") -> str:
        return names[match.group(0).lower()]

    return re.sub(r"[A-Za-z]+", replace, value)


def check_month(month: str) -> List[str]:
    """Check month field validation"""
    errors = []
    original = month
    month = canonicalize_names(month, MONTH_NAMES)

    logic_errors = validate_time_field_logic(month, "month", 1, 12)
    if logic_errors:
        errors.extend(logic_errors)
    elif not re.match(MONTH_PATTERN, month):
        errors.append(f"invalid month format: '{original}'")

    return errors


def check_day_of_week(weekday: str) -> List[str]:
    """Check day of week field validation"""
    errors = []
    original = weekday
    weekday = canonicalize_names(weekday, WEEKDAY_NAMES)

    logic_errors = validate_time_field_logic(weekday, "day of week", 0, 7)
    if logic_errors:
        errors.extend(logic_errors)
    elif not re.match(WEEKDAY_PATTERN, weekday):
        errors.append(f"invalid day of week format: '{original}'")

    return errors


def _windows_user_exists(username: str) -> bool:
    if username.lower() in WINDOWS_BUILTIN_USERS:
        return True
    result = _run_command(["net", "user", username])
    return result.returncode == 0


def check_user_exists(username: str) -> bool:
    """Check if user exists in the system"""
    if username in ("root", "pytest_user"):  # users always exists for tests
        return True
    try:
        if platform.system().lower() == "windows":
            return _windows_user_exists(username)
        result = subprocess.run(["id", username], capture_output=True, text=True, timeout=5, check=False)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return True
    except Exception as e:
        logging.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return True


def check_user(username: str) -> Tuple[List[str], List[str]]:
    """Check user field validation"""
    errors: List[str] = []
    warnings: List[str] = []
    if not username or username.startswith("#") or '"' in username or "@" in username or " " in username or not re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$").match(username):
        errors.append(f"invalid user format: '{username}'")
    elif not check_user_exists(username):
        warnings.append(f"user does not exist: '{username}'")
    return errors, warnings


def check_command(command: str) -> List[str]:
    """Check command field validation"""
    errors = []

    if not command:
        errors.append("missing command")
    else:
        # Check for dangerous commands
        dangerous_errors = check_dangerous_commands(command)
        errors.extend(dangerous_errors)

    return errors


def parse_environment(line: str) -> Optional[Tuple[str, str]]:
    """Return (name, value) when the line is an environment assignment."""
    if "=" not in line:
        return None
    name, value = line.split("=", 1)
    if not name or any(char.isspace() for char in name):
        return None
    if any(char.isdigit() or char in "*@" for char in name):
        return None
    return name, value


def check_environment_assignment(name: str, value: str) -> List[str]:
    """Validate a crontab environment assignment."""
    errors: List[str] = []
    if not ENV_NAME_RE.match(name):
        errors.append(f"invalid environment variable name: '{name}'")
        return errors
    if any(char.isspace() for char in value):
        errors.append(f"invalid environment variable value for {name}: '{value}'")
        return errors
    upper = name.upper()
    if upper in {"SHELL", "PATH", "HOME"} and not value:
        errors.append(f"invalid environment variable value for {name}: empty")
    elif upper in {"SHELL", "HOME"} and not os.path.isabs(value):
        errors.append(f"invalid environment variable value for {name}: '{value}'")
    elif upper == "MAILTO" and value and EMAIL_RE.match(value) is None and USERNAME_RE.match(value) is None:
        errors.append(f"invalid environment variable value for MAILTO: '{value}'")
    elif upper in {"LOGNAME", "USER"} and USERNAME_RE.match(value) is None:
        errors.append(f"invalid environment variable value for {name}: '{value}'")
    return errors


def check_special(keyword: str, parts: List[str], is_system_crontab: bool = False) -> Tuple[List[str], List[str]]:
    """Check special keyword validation"""
    errors: List[str] = []
    warnings: List[str] = []

    # Validate special keyword
    valid_keywords = ["@reboot", "@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly"]
    if keyword not in valid_keywords:
        errors.append(f"{keyword} {' '.join(parts)} # invalid special keyword '{keyword}'")
        return errors, warnings

    if is_system_crontab:
        # System crontab format: @keyword user command
        if len(parts) < SYSTEM_SPECIAL_MIN_FIELDS:
            errors.append(f"{keyword} {' '.join(parts)} # (minimum {SYSTEM_SPECIAL_MIN_FIELDS} required for system crontab)")
        else:
            user = parts[1]
            command = " ".join(parts[2:])

            # Validate user field for system crontab
            user_errors, user_warnings = check_user(user)
            errors.extend(user_errors)
            warnings.extend(user_warnings)

            # Validate command
            command_errors = check_command(command)
            errors.extend(command_errors)
    # User crontab format: @keyword command
    elif len(parts) > 1:
        command = " ".join(parts[1:])
        # Validate command
        command_errors = check_command(command)
        errors.extend(command_errors)
    else:
        errors.append(f"{keyword} {' '.join(parts)} # (minimum 2 required for user crontab)")

    return errors, warnings


def check_line(line: str, line_number: int, file_name: str, file_path: Optional[str] = None, is_system_crontab: bool = False) -> Tuple[List[str], List[str]]:
    """
    Check a single crontab line (user or system)
    Returns: tuple of (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    assignment = parse_environment(line)
    if assignment is not None:
        env_name, env_value = assignment
        env_errors = check_environment_assignment(env_name, env_value)
        content = clean_line_for_output(get_line_content(file_path, line_number) if file_path else line)
        formatted = [f"{file_name} (Line {line_number}): {content} # {error}" for error in env_errors]
        return formatted, warnings

    # Check for special keywords
    if line.startswith("@"):
        parts = line.split()
        if len(parts) < SPECIAL_KEYWORD_MIN_FIELDS:
            errors.append(f"insufficient fields for special keyword (minimum {SPECIAL_KEYWORD_MIN_FIELDS} required)")
            # Return errors with line number and content
            formatted_errors = []
            formatted_warnings = []
            line_content = get_line_content(file_path, line_number) if file_path else line
            line_content = clean_line_for_output(line_content)
            for error in errors:
                formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
            for warning in warnings:
                formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
            return formatted_errors, formatted_warnings

        keyword = parts[0]
        special_errors, special_warnings = check_special(keyword, parts, is_system_crontab)
        errors.extend(special_errors)
        warnings.extend(special_warnings)

        # Return errors with line number and content
        formatted_errors = []
        formatted_warnings = []
        line_content = get_line_content(file_path, line_number) if file_path else line
        line_content = clean_line_for_output(line_content)
        for error in errors:
            formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
        for warning in warnings:
            formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
        return formatted_errors, formatted_warnings

    # Parse regular crontab line
    parts = line.split()
    min_fields = SYSTEM_CRONTAB_MIN_FIELDS if is_system_crontab else USER_CRONTAB_MIN_FIELDS

    if len(parts) < min_fields:
        errors.append(f"insufficient fields (minimum {min_fields} required for {'system' if is_system_crontab else 'user'} crontab, found {len(parts)})")
        # Return errors with line number and content
        formatted_errors = []
        formatted_warnings = []
        line_content = get_line_content(file_path, line_number) if file_path else line
        line_content = clean_line_for_output(line_content)
        for error in errors:
            formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
        for warning in warnings:
            formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
        return formatted_errors, formatted_warnings

    # Extract time fields and command
    minute, hour, day, month, weekday = parts[:5]

    if is_system_crontab:
        # System crontab format: minute hour day month weekday user command
        if len(parts) < SYSTEM_CRONTAB_MIN_FIELDS:
            errors.append(f"insufficient fields (minimum {SYSTEM_CRONTAB_MIN_FIELDS} required for system crontab, found {len(parts)})")
            # Return errors with line number and content
            formatted_errors = []
            formatted_warnings = []
            line_content = get_line_content(file_path, line_number) if file_path else line
            line_content = clean_line_for_output(line_content)
            for error in errors:
                formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
            for warning in warnings:
                formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
            return formatted_errors, formatted_warnings

        user = parts[5]
        command = " ".join(parts[6:])

        # Check for too many fields (more than 7) - but only if command doesn't contain spaces
        if len(parts) > SYSTEM_CRONTAB_MAX_FIELDS and " " not in command:
            errors.append(f"too many fields (maximum {SYSTEM_CRONTAB_MAX_FIELDS} required for system crontab, found {len(parts)})")
            # Return errors with line number and content
            formatted_errors = []
            formatted_warnings = []
            line_content = get_line_content(file_path, line_number) if file_path else line
            line_content = clean_line_for_output(line_content)
            for error in errors:
                formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
            for warning in warnings:
                formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
            return formatted_errors, formatted_warnings

        # Check for extra fields in command (like "extra" in "root extra /usr/bin/backup.sh")
        if len(parts) > SYSTEM_CRONTAB_MAX_FIELDS:
            extra_field = parts[6]
            if extra_field == "extra":
                errors.append(f"extra field '{extra_field}' in command")
                # Return errors with line number and content
                formatted_errors = []
                formatted_warnings = []
                line_content = get_line_content(file_path, line_number) if file_path else line
                line_content = clean_line_for_output(line_content)
                for error in errors:
                    formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
                for warning in warnings:
                    formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")
                return formatted_errors, formatted_warnings

        # Validate user field
        user_errors, user_warnings = check_user(user)
        errors.extend(user_errors)
        warnings.extend(user_warnings)
    else:
        # User crontab format: minute hour day month weekday command
        command = " ".join(parts[5:])

    # Validate command
    command_errors = check_command(command)
    errors.extend(command_errors)

    # Validate time fields
    minute_errors = check_minutes(minute, is_system_crontab)
    errors.extend(minute_errors)

    hour_errors = check_hours(hour)
    errors.extend(hour_errors)

    day_errors = check_day_of_month(day)
    errors.extend(day_errors)

    month_errors = check_month(month)
    errors.extend(month_errors)

    weekday_errors = check_day_of_week(weekday)
    errors.extend(weekday_errors)

    # Return errors with line number and content
    formatted_errors = []
    formatted_warnings = []
    line_content = get_line_content(file_path, line_number) if file_path else line
    line_content = clean_line_for_output(line_content)
    for error in errors:
        formatted_errors.append(f"{file_name} (Line {line_number}): {line_content} # {error}")
    for warning in warnings:
        formatted_warnings.append(f"{file_name} (Line {line_number}): {line_content} # {warning}")

    return formatted_errors, formatted_warnings


# Legacy functions for backward compatibility
def check_line_user(line: str, line_number: int, file_name: str, file_path: Optional[str] = None) -> List[str]:
    """Legacy function for user crontab line checking"""
    errors, warnings = check_line(line, line_number, file_name, file_path, is_system_crontab=False)
    return errors


def check_line_system(line: str, line_number: int, file_name: str, file_path: Optional[str] = None) -> List[str]:
    """Legacy function for system crontab line checking"""
    errors, warnings = check_line(line, line_number, file_name, file_path, is_system_crontab=True)
    return errors


def check_line_special(line: str, line_number: int, file_name: str, file_path: Optional[str] = None) -> List[str]:
    """Legacy function for special keyword line checking"""
    # Determine if this is system crontab based on file path
    is_system_crontab = is_system_crontab_path(file_path) if file_path else "system" in file_name.lower()
    errors, warnings = check_line(line, line_number, file_name, file_path, is_system_crontab=is_system_crontab)
    return errors


def validate_time_field_logic(value: str, field_name: str, min_val: int, max_val: int) -> List[str]:
    """Validate time field logic (ranges, lists, steps)"""
    errors: List[str] = []

    # Skip special values
    if value in ["*"]:
        return errors

    # Handle lists (comma-separated values)
    if "," in value:
        parts = value.split(",")
        seen_values = set()
        for part in parts:
            part_stripped = part.strip()
            if not part_stripped:
                errors.append(f"empty value in {field_name} list: '{value}'")
                continue

            # Check for duplicates
            if part_stripped in seen_values:
                errors.append(f"duplicate value '{part_stripped}' in {field_name} list: '{value}'")
            seen_values.add(part_stripped)

            # Validate individual part
            part_errors = validate_single_time_value(part_stripped, field_name, min_val, max_val)
            errors.extend(part_errors)
    else:
        # Validate single value or range or step
        part_errors = validate_single_time_value(value, field_name, min_val, max_val)
        errors.extend(part_errors)

    return errors


def validate_single_time_value(value: str, field_name: str, min_val: int, max_val: int) -> List[str]:
    """Validate single time value, range, or step"""
    errors: List[str] = []

    # Handle steps (*/n)
    if value.startswith("*/"):
        step_part = value[2:]
        if step_part.isdigit():
            step_val = int(step_part)
            if step_val <= 0:
                errors.append(f"step value must be positive in {field_name}: '{value}'")
            # Step can be any positive number - cron will handle it correctly
            # Step should not exceed the maximum value for the field
            if step_val > max_val:
                errors.append(f"step value {step_val} exceeds maximum {max_val} for {field_name}: '{value}'")
        else:
            errors.append(f"invalid step value in {field_name}: '{value}'")
        return errors

    # Handle ranges (n-m)
    if "-" in value:
        range_parts = value.split("-")
        if len(range_parts) == RANGE_PARTS_COUNT:
            start_str, end_str = range_parts
            if start_str.isdigit() and end_str.isdigit():
                start_val = int(start_str)
                end_val = int(end_str)

                if start_val > end_val:
                    errors.append(f"invalid range {start_val}-{end_val} in {field_name}: start > end")

                if start_val < min_val or start_val > max_val:
                    errors.append(f"range start {start_val} out of bounds ({min_val}-{max_val}) for {field_name}: '{value}'")

                if end_val < min_val or end_val > max_val:
                    errors.append(f"range end {end_val} out of bounds ({min_val}-{max_val}) for {field_name}: '{value}'")
        return errors

    # Handle single numeric values
    if value.isdigit():
        num_val = int(value)
        if num_val < min_val or num_val > max_val:
            errors.append(f"value {num_val} out of bounds ({min_val}-{max_val}) for {field_name}: '{value}'")

    return errors


def get_crontab(username: str) -> Optional[str]:
    """
    Get user crontab content using 'crontab -l -u username'
    Returns the crontab content as string or None if not found/error
    """
    try:
        # Try to get user crontab using crontab command
        result = subprocess.run(["crontab", "-l", "-u", username], capture_output=True, text=True, timeout=10, check=False)

        if result.returncode == 0:
            return result.stdout
        elif result.returncode == 1 and "no crontab for" in result.stderr.lower():
            # User has no crontab
            logger.info(f"No crontab found for user: {username}")
            return None
        else:
            error_message = result.stderr
            # remove blank lines from error message
            error_message = "\n".join([line for line in error_message.splitlines() if line.strip()])
            logger.warning(f"Error getting crontab for {username}: {error_message}")
            return None

    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout getting crontab for user: {username}")
        return None
    except FileNotFoundError:
        logger.warning(f"crontab command not found for user: {username}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error getting crontab for {username}: {e}")
        return None
