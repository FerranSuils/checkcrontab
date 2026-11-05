#!/usr/bin/env python3
# mypy: ignore-errors
"""
Tests for checker module helper functions
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the checker module
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "checkcrontab"
package_spec = importlib.util.spec_from_file_location(
    "checkcrontab", PACKAGE_ROOT / "__init__.py", submodule_search_locations=[str(PACKAGE_ROOT)]
)
checkcrontab_pkg = importlib.util.module_from_spec(package_spec)
sys.modules["checkcrontab"] = checkcrontab_pkg
package_spec.loader.exec_module(checkcrontab_pkg)

checker = importlib.import_module("checkcrontab.checker")


# ============================================================================
# check_filename tests
# ============================================================================


def test_check_filename_valid():
    """Test check_filename with valid filenames"""
    assert checker.check_filename("valid-filename_123") == ""
    assert checker.check_filename("backup-job") == ""
    assert checker.check_filename("test_cron") == ""
    assert checker.check_filename("JOB123") == ""


def test_check_filename_invalid_starts_with_dot():
    """Test check_filename with hidden files"""
    error = checker.check_filename(".hidden")
    assert "starts with '.'" in error


def test_check_filename_invalid_ends_with_tilde():
    """Test check_filename with backup files"""
    error = checker.check_filename("backup~")
    assert "ends with '~'" in error


def test_check_filename_invalid_contains_dot():
    """Test check_filename with files containing dots"""
    error = checker.check_filename("file.txt")
    assert "contains '.'" in error


def test_check_filename_invalid_contains_hash():
    """Test check_filename with files containing #"""
    error = checker.check_filename("file#name")
    assert "contains '#'" in error


def test_check_filename_invalid_contains_comma():
    """Test check_filename with files containing comma"""
    error = checker.check_filename("file,name")
    assert "contains ','" in error


def test_check_filename_invalid_characters():
    """Test check_filename with invalid characters"""
    error = checker.check_filename("file name")  # space
    assert "contains characters outside" in error
    error = checker.check_filename("file@name")
    assert "contains characters outside" in error


def test_check_filename_empty():
    """Test check_filename with empty name"""
    error = checker.check_filename("")
    assert "empty name" in error


# ============================================================================
# check_kind tests
# ============================================================================


def test_check_kind_regular_file(tmp_path):
    """Test check_kind with regular file"""
    f = tmp_path / "regular_file"
    f.write_text("test")
    assert checker.check_kind(str(f)) == "regular_file"


def test_check_kind_directory(tmp_path):
    """Test check_kind with directory"""
    d = tmp_path / "test_dir"
    d.mkdir()
    assert checker.check_kind(str(d)) == "directory"


def test_check_kind_symlink(tmp_path):
    """Test check_kind with symlink"""
    f = tmp_path / "target"
    f.write_text("test")
    link = tmp_path / "link"
    link.symlink_to(f)
    # With follow_symlink=True (default), should return regular_file
    assert checker.check_kind(str(link)) == "regular_file"
    # With follow_symlink=False, should return symlink
    assert checker.check_kind(str(link), follow_symlink=False) == "symlink"


# ============================================================================
# check_daemon tests
# ============================================================================


@patch("checkcrontab.checker.subprocess.run")
def test_check_daemon_timeout(mock_run):
    """Test check_daemon with timeout"""
    mock_run.side_effect = __import__('subprocess').TimeoutExpired(cmd="test", timeout=5)
    errors = checker.check_daemon()
    assert len(errors) == 1
    assert "timeout" in errors[0]


@patch("checkcrontab.checker.subprocess.run")
def test_check_daemon_systemctl_not_found(mock_run):
    """Test check_daemon when systemctl not found"""
    mock_run.side_effect = FileNotFoundError()
    errors = checker.check_daemon()
    assert len(errors) == 1
    assert "systemctl not found" in errors[0]


@patch("checkcrontab.checker.subprocess.run")
def test_check_daemon_subprocess_error(mock_run):
    """Test check_daemon with subprocess error"""
    mock_run.side_effect = __import__('subprocess').SubprocessError("test error")
    errors = checker.check_daemon()
    assert len(errors) == 1
    assert "SubprocessError" in errors[0]


@patch("checkcrontab.checker.subprocess.run")
def test_check_daemon_generic_exception(mock_run):
    """Test check_daemon with generic exception"""
    mock_run.side_effect = RuntimeError("test error")
    errors = checker.check_daemon()
    assert len(errors) == 1
    assert "RuntimeError" in errors[0]


# ============================================================================
# check_owner_and_permissions tests
# ============================================================================


def test_check_owner_and_permissions_file_not_exists():
    """Test check_owner_and_permissions with non-existent file"""
    errors = checker.check_owner_and_permissions("/nonexistent/file")
    assert len(errors) == 1
    assert "does not exist" in errors[0]


def test_check_owner_and_permissions_broken_symlink(tmp_path):
    """Test check_owner_and_permissions with broken symlink"""
    target = tmp_path / "target"
    link = tmp_path / "link"
    link.symlink_to(target)  # Create symlink to non-existent target
    errors = checker.check_owner_and_permissions(str(link))
    # Should detect broken symlink
    assert any("broken symlink" in e for e in errors)


def test_check_owner_and_permissions_directory(tmp_path):
    """Test check_owner_and_permissions with directory (not regular file)"""
    d = tmp_path / "test_dir"
    d.mkdir()
    errors = checker.check_owner_and_permissions(str(d))
    # Should report not a regular file
    assert any("not a regular_file" in e for e in errors)


@patch("checkcrontab.checker.os.stat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_wrong_perms(mock_platform, mock_islink, mock_lexists, mock_exists, mock_stat, tmp_path):
    """Test check_owner_and_permissions with wrong permissions"""
    mock_lexists.return_value = True
    mock_exists.return_value = True
    mock_islink.return_value = False

    # Mock stat to return wrong permissions
    mock_stat_info = MagicMock()
    mock_stat_info.st_mode = 0o100755  # Regular file with wrong permissions
    mock_stat_info.st_uid = 0
    mock_stat.return_value = mock_stat_info

    f = tmp_path / "testfile"
    f.write_text("test")

    errors = checker.check_owner_and_permissions(str(f))
    assert any("wrong permissions" in e for e in errors)


@patch("checkcrontab.checker.os.stat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_wrong_owner(mock_platform, mock_islink, mock_lexists, mock_exists, mock_stat, tmp_path):
    """Test check_owner_and_permissions with wrong owner"""
    mock_lexists.return_value = True
    mock_exists.return_value = True
    mock_islink.return_value = False

    # Mock stat to return wrong owner
    mock_stat_info = MagicMock()
    mock_stat_info.st_mode = 0o100644  # Correct permissions
    mock_stat_info.st_uid = 1000  # Wrong owner (not root)
    mock_stat.return_value = mock_stat_info

    f = tmp_path / "testfile"
    f.write_text("test")

    errors = checker.check_owner_and_permissions(str(f), owner_uid=0)
    assert any("wrong owner" in e for e in errors)


@patch("checkcrontab.checker.os.lstat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.os.path.realpath")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_symlink_wrong_owner(mock_platform, mock_realpath, mock_islink, mock_lexists, mock_exists, mock_lstat, tmp_path):
    """Test check_owner_and_permissions with symlink having wrong owner"""
    mock_lexists.return_value = True
    mock_exists.return_value = True
    mock_islink.return_value = True

    # Mock lstat for symlink
    mock_lstat_info = MagicMock()
    mock_lstat_info.st_uid = 1000  # Wrong symlink owner
    mock_lstat.return_value = mock_lstat_info

    target = tmp_path / "target"
    target.write_text("test")
    mock_realpath.return_value = str(target)

    link = tmp_path / "link"

    errors = checker.check_owner_and_permissions(str(link), owner_uid=0)
    assert any("wrong symlink owner" in e for e in errors)


# ============================================================================
# get_crontab tests
# ============================================================================


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_success(mock_run):
    """Test get_crontab with successful result"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="0 * * * * echo test\n",
        stderr=""
    )
    result = checker.get_crontab("testuser")
    assert result == "0 * * * * echo test\n"


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_no_crontab(mock_run):
    """Test get_crontab when user has no crontab"""
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="no crontab for testuser\n"
    )
    result = checker.get_crontab("testuser")
    assert result is None


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_error(mock_run):
    """Test get_crontab with error"""
    mock_run.return_value = MagicMock(
        returncode=2,
        stdout="",
        stderr="crontab: error opening crontab\n"
    )
    result = checker.get_crontab("testuser")
    assert result is None


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_timeout(mock_run):
    """Test get_crontab with timeout"""
    mock_run.side_effect = __import__('subprocess').TimeoutExpired(cmd="test", timeout=10)
    result = checker.get_crontab("testuser")
    assert result is None


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_file_not_found(mock_run):
    """Test get_crontab when crontab command not found"""
    mock_run.side_effect = FileNotFoundError()
    result = checker.get_crontab("testuser")
    assert result is None


@patch("checkcrontab.checker.subprocess.run")
def test_get_crontab_generic_exception(mock_run):
    """Test get_crontab with generic exception"""
    mock_run.side_effect = RuntimeError("test error")
    result = checker.get_crontab("testuser")
    assert result is None


# ============================================================================
# validate_time_field_logic tests
# ============================================================================


def test_validate_time_field_logic_invalid_step_zero():
    """Test validate_time_field_logic with step value 0"""
    errors = checker.validate_time_field_logic("*/0", "minutes", 0, 59)
    assert len(errors) > 0
    assert any("must be positive" in e for e in errors)


def test_validate_time_field_logic_invalid_step_too_large():
    """Test validate_time_field_logic with step value exceeding max"""
    errors = checker.validate_time_field_logic("*/100", "minutes", 0, 59)
    assert len(errors) > 0
    assert any("exceeds maximum" in e for e in errors)


def test_validate_time_field_logic_range_out_of_bounds_start():
    """Test validate_time_field_logic with range start out of bounds"""
    errors = checker.validate_time_field_logic("25-30", "hours", 0, 23)
    assert len(errors) > 0
    assert any("range start" in e and "out of bounds" in e for e in errors)


def test_validate_time_field_logic_range_out_of_bounds_end():
    """Test validate_time_field_logic with range end out of bounds"""
    errors = checker.validate_time_field_logic("20-25", "hours", 0, 23)
    assert len(errors) > 0
    assert any("range end" in e and "out of bounds" in e for e in errors)


# ============================================================================
# check_user_exists tests
# ============================================================================


@patch("checkcrontab.checker.subprocess.run")
def test_check_user_exists_timeout(mock_run):
    """Test check_user_exists with timeout"""
    mock_run.side_effect = __import__('subprocess').TimeoutExpired(cmd="test", timeout=5)
    # Should return True (default to exists on error)
    result = checker.check_user_exists("testuser")
    assert result is True


@patch("checkcrontab.checker.subprocess.run")
def test_check_user_exists_file_not_found(mock_run):
    """Test check_user_exists when id command not found"""
    mock_run.side_effect = FileNotFoundError()
    result = checker.check_user_exists("testuser")
    assert result is True


@patch("checkcrontab.checker.subprocess.run")
def test_check_user_exists_subprocess_error(mock_run):
    """Test check_user_exists with subprocess error"""
    mock_run.side_effect = __import__('subprocess').SubprocessError("test")
    result = checker.check_user_exists("testuser")
    assert result is True


@patch("checkcrontab.checker.subprocess.run")
def test_check_user_exists_generic_exception(mock_run):
    """Test check_user_exists with generic exception"""
    mock_run.side_effect = RuntimeError("test")
    result = checker.check_user_exists("testuser")
    assert result is True


# ============================================================================
# check_user with Windows tests
# ============================================================================


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_check_user_windows(mock_platform, mock_run):
    """Test check_user on Windows uses net user"""
    mock_run.return_value = MagicMock(returncode=0, stdout="The command completed successfully", stderr="")
    errors, warnings = checker.check_user("testuser")
    assert errors == []
    assert warnings == []
    assert mock_run.call_args[0][0][:3] == ["net", "user", "testuser"]


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_check_user_windows_missing(mock_platform, mock_run):
    """Test check_user on Windows warns when the account does not exist"""
    mock_run.return_value = MagicMock(returncode=2, stdout="The user name could not be found.", stderr="")
    errors, warnings = checker.check_user("testuser")
    assert errors == []
    assert any("does not exist" in warning for warning in warnings)


# ============================================================================
# get_line_content and clean_line_for_output tests
# ============================================================================


def test_get_line_content_file_not_found():
    """Test get_line_content with non-existent file"""
    result = checker.get_line_content("/nonexistent/file", 1)
    assert result == ""


def test_get_line_content_out_of_bounds(tmp_path):
    """Test get_line_content with line number out of bounds"""
    f = tmp_path / "test.txt"
    f.write_text("line1\n")
    result = checker.get_line_content(str(f), 10)
    assert result == ""


# ============================================================================
# check_command warning path tests
# ============================================================================


def test_check_command_missing():
    """Test check_command with empty command"""
    errors = checker.check_command("")
    assert len(errors) == 1
    assert "missing command" in errors[0]


# ============================================================================
# Legacy functions tests
# ============================================================================


def test_check_line_user_legacy():
    """Test legacy check_line_user function"""
    errors = checker.check_line_user("0 2 * * * echo test", 1, "test.txt")
    assert errors == []


def test_check_line_system_legacy():
    """Test legacy check_line_system function"""
    errors = checker.check_line_system("0 2 * * * root echo test", 1, "test.txt")
    assert errors == []


def test_check_line_special_legacy():
    """Test legacy check_line_special function with system path"""
    errors = checker.check_line_special("@reboot root echo test", 1, "test.txt", "/etc/crontab")
    assert errors == []


# ============================================================================
# Additional coverage tests for edge cases
# ============================================================================


@patch("checkcrontab.checker.os.lstat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.os.path.realpath")
@patch("checkcrontab.checker.os.stat")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_symlink_correct_owner(mock_platform, mock_stat, mock_realpath, mock_islink, mock_lexists, mock_exists, mock_lstat, tmp_path):
    """Test check_owner_and_permissions with symlink having correct owner"""
    mock_lexists.return_value = True
    mock_exists.return_value = True
    mock_islink.return_value = True

    # Mock lstat for symlink with correct owner
    mock_lstat_info = MagicMock()
    mock_lstat_info.st_uid = 0  # Correct owner (root)
    mock_lstat.return_value = mock_lstat_info

    # Mock stat for target file
    mock_stat_info = MagicMock()
    mock_stat_info.st_mode = 0o100644  # Regular file with correct permissions
    mock_stat_info.st_uid = 0
    mock_stat.return_value = mock_stat_info

    target = tmp_path / "target"
    target.write_text("test")
    mock_realpath.return_value = str(target)

    link = tmp_path / "link"

    errors = checker.check_owner_and_permissions(str(link), owner_uid=0)
    # Should have no errors
    assert errors == []


@patch("checkcrontab.checker.os.lstat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_symlink_lstat_exception(mock_platform, mock_islink, mock_lexists, mock_exists, mock_lstat, tmp_path):
    """Test check_owner_and_permissions with lstat raising exception"""
    mock_lexists.return_value = True
    mock_islink.return_value = True
    mock_lstat.side_effect = OSError("Permission denied")

    link = tmp_path / "link"

    errors = checker.check_owner_and_permissions(str(link), owner_uid=0)
    assert len(errors) > 0
    assert any("failed to stat symlink" in e for e in errors)


@patch("checkcrontab.checker.os.stat")
@patch("checkcrontab.checker.os.path.exists")
@patch("checkcrontab.checker.os.path.lexists")
@patch("checkcrontab.checker.os.path.islink")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_owner_and_permissions_stat_exception(mock_platform, mock_islink, mock_lexists, mock_exists, mock_stat, tmp_path):
    """Test check_owner_and_permissions with stat raising exception"""
    mock_lexists.return_value = True
    mock_exists.return_value = True
    mock_islink.return_value = False
    mock_stat.side_effect = OSError("Permission denied")

    f = tmp_path / "testfile"

    errors = checker.check_owner_and_permissions(str(f), owner_uid=0)
    assert len(errors) > 0
    assert any("Permission denied" in e for e in errors)


def test_check_special_user_warning_nonexistent_user():
    """Test check_special with warnings for user that doesn't exist"""
    # Create a line with a user that doesn't exist
    # This should trigger the warning path in check_special (line 329)
    with patch("checkcrontab.checker.check_user_exists", return_value=False):
        with patch("checkcrontab.checker.platform.system", return_value="Linux"):
            errors = checker.check_special("@reboot", ["@reboot", "nonexistentuser123", "echo test"], is_system_crontab=True)
            # Should not have errors (warnings are logged, not returned)
            assert errors == []


def test_check_special_user_no_command():
    """Test check_special with user crontab without command"""
    # User crontab: only @keyword without command
    errors = checker.check_special("@reboot", ["@reboot"], is_system_crontab=False)
    assert len(errors) == 1
    assert "minimum 2 required" in errors[0]


def test_check_line_multiline_continuation_with_backslash():
    """Test check_line with multiline command continuation"""
    # This tests the multiline handling in check_file
    # We need to test it through check_file, not check_line
    pass  # Will test through integration tests


# ============================================================================
# Tests for special file types (char device, block device, socket, fifo)
# ============================================================================


# Note: These are difficult to test in a portable way as creating special files
# requires root privileges. We'll mock the check_kind function instead.
def test_check_owner_permissions_with_special_file_types():
    """Test check_owner_and_permissions with special file types"""
    # These would require root to create, so we test via mocking
    with patch("checkcrontab.checker.check_kind") as mock_check_kind:
        with patch("checkcrontab.checker.os.path.lexists", return_value=True):
            with patch("checkcrontab.checker.os.path.islink", return_value=False):
                with patch("checkcrontab.checker.os.stat") as mock_stat:
                    mock_stat_info = MagicMock()
                    mock_stat_info.st_mode = 0o100644
                    mock_stat_info.st_uid = 0
                    mock_stat.return_value = mock_stat_info

                    # Test each special file type
                    for file_type in ["char_device", "block_device", "socket", "fifo", "unknown"]:
                        mock_check_kind.return_value = file_type
                        errors = checker.check_owner_and_permissions("/dev/test", owner_uid=0)
                        assert any("not a regular_file" in e for e in errors)


def _completed(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Darwin")
def test_check_daemon_darwin_running(mock_platform, mock_run):
    mock_run.return_value = _completed(stdout="123 0 com.vix.cron\n- 0 com.apple.foo\n")
    assert checker.check_daemon() == []


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Darwin")
def test_check_daemon_darwin_not_running(mock_platform, mock_run):
    mock_run.return_value = _completed(stdout="- 0 com.vix.cron\n")
    assert checker.check_daemon() == []


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Darwin")
def test_check_daemon_darwin_launchctl_missing(mock_platform, mock_run):
    mock_run.side_effect = FileNotFoundError()
    errors = checker.check_daemon()
    assert errors == ["Cron daemon: launchctl not found"]


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_check_daemon_windows_schedule_running(mock_platform, mock_run):
    mock_run.return_value = _completed(stdout="STATE              : 4  RUNNING\n")
    assert checker.check_daemon() == []
    assert mock_run.call_args[0][0][:3] == ["sc", "query", "Schedule"]


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_check_daemon_windows_sc_missing(mock_platform, mock_run):
    mock_run.side_effect = FileNotFoundError()
    assert checker.check_daemon() == ["Cron daemon: sc not found"]


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Linux")
def test_check_services_linux(mock_platform, mock_run):
    mock_run.return_value = _completed(stdout="cron.service loaded active running\n")
    assert checker.check_services() == []


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Darwin")
def test_check_services_darwin_missing(mock_platform, mock_run):
    mock_run.side_effect = FileNotFoundError()
    assert checker.check_services() == ["Daemon/service: launchctl not found"]


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_check_services_windows(mock_platform, mock_run):
    mock_run.return_value = _completed(stdout="SERVICE_NAME: Schedule\n")
    assert checker.check_services() == []
    assert mock_run.call_args[0][0][0] == "sc"


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_windows_permissions_world_writable(mock_platform, mock_run, tmp_path):
    crontab = tmp_path / "crontab"
    crontab.write_text("0 1 * * * root echo ok\n")

    def side_effect(cmd, **kwargs):
        if cmd[0] == "icacls":
            return _completed(stdout=f"{crontab} Everyone:(F)\nSuccessfully processed 1 files\n")
        return _completed(stdout="NT AUTHORITY\\SYSTEM\n")

    mock_run.side_effect = side_effect
    errors = checker.check_owner_and_permissions(str(crontab))
    assert any("wrong permissions" in error for error in errors)


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_windows_permissions_ok(mock_platform, mock_run, tmp_path):
    crontab = tmp_path / "crontab"
    crontab.write_text("0 1 * * * root echo ok\n")

    def side_effect(cmd, **kwargs):
        if cmd[0] == "icacls":
            return _completed(stdout=f"{crontab} BUILTIN\\Administrators:(F)\n{crontab} BUILTIN\\Users:(RX)\nSuccessfully processed 1 files\n")
        return _completed(stdout="NT AUTHORITY\\SYSTEM\n")

    mock_run.side_effect = side_effect
    assert checker.check_owner_and_permissions(str(crontab)) == []


@patch("checkcrontab.checker.subprocess.run")
@patch("checkcrontab.checker.platform.system", return_value="Windows")
def test_windows_permissions_wrong_owner(mock_platform, mock_run, tmp_path):
    crontab = tmp_path / "crontab"
    crontab.write_text("0 1 * * * root echo ok\n")

    def side_effect(cmd, **kwargs):
        if cmd[0] == "icacls":
            return _completed(stdout=f"{crontab} BUILTIN\\Users:(RX)\nSuccessfully processed 1 files\n")
        return _completed(stdout="DESKTOP\\bob\n")

    mock_run.side_effect = side_effect
    errors = checker.check_owner_and_permissions(str(crontab))
    assert any("wrong owner" in error for error in errors)


def test_system_crontab_paths_windows(monkeypatch):
    monkeypatch.setattr(checker.platform, "system", lambda: "Windows")
    monkeypatch.setenv("PROGRAMDATA", r"C:\ProgramData")
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("CRONTAB_SYSTEM_PATH", r"D:\crontab")
    paths = checker.system_crontab_paths()
    assert paths[0] == r"D:\crontab"
    assert os.path.join(r"C:\ProgramData", "crontab") in paths
    assert r"C:\cygwin64\etc\crontab" in paths


def test_is_system_crontab_path_posix():
    assert checker.is_system_crontab_path("/etc/crontab") is True
    assert checker.is_system_crontab_path("/etc/cron.d/daily") is True
    assert checker.is_system_crontab_path("/tmp/user_cron") is False


def test_find_system_crontab_override(tmp_path, monkeypatch):
    target = tmp_path / "crontab"
    target.write_text("0 1 * * * root echo ok\n")
    monkeypatch.setenv("CRONTAB_SYSTEM_PATH", str(target))
    assert checker.find_system_crontab() == str(target)


def test_user_crontab_paths_cover_macos_and_windows(monkeypatch):
    monkeypatch.setattr(checker.platform, "system", lambda: "Darwin")
    darwin_paths = checker.user_crontab_paths("ada")
    assert "/usr/lib/cron/tabs/ada" in darwin_paths
    monkeypatch.setattr(checker.platform, "system", lambda: "Windows")
    monkeypatch.setenv("PROGRAMDATA", r"C:\ProgramData")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\ada\AppData\Local")
    windows_paths = checker.user_crontab_paths("ada")
    assert os.path.join(r"C:\ProgramData", "cron", "crontabs", "ada") in windows_paths
    assert os.path.join(r"C:\Users\ada\AppData\Local", "cron", "ada") in windows_paths
