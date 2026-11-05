# Crontab Syntax Features

## Exit Codes

The `checkcrontab` command returns the following exit codes:

- **0** - Success: No errors found in any checked files
- **1** - Errors found: One or more syntax errors detected in crontab files
- **2** - System error: File access issues, permission problems, or other system-level errors

### Examples

```bash
# Success - no errors
checkcrontab examples/user_valid.txt
echo $?  # Returns 0

# Errors found
checkcrontab examples/user_incorrect.txt
echo $?  # Returns 1

# System error (file not found)
checkcrontab nonexistent_file.txt
echo $?  # Returns 2

# JSON output
checkcrontab --format json examples/user_valid.txt
```

### JSON Output Format

When using `--format json` flag, the output is structured as follows:

```json
{
  "success": boolean,
  "total_files": number,
  "total_rows": number,
  "total_rows_errors": number,
  "total_errors": number,
  "files": [
    {
      "file": "string",
      "is_system_crontab": boolean,
      "rows": number,
      "rows_errors": number,
      "errors_count": number,
      "errors": ["string"],
      "success": boolean
    }
  ]
}
```

## Platform Support

### Linux (Full Support)
- ✅ System crontab validation (`/etc/crontab`)
- ✅ User crontab validation (via `crontab -l -u username`)
- ✅ User existence validation
- ✅ Daemon/service checks via systemctl
- ✅ All crontab syntax features
- ✅ File permissions validation
- ✅ Cron daemon status checks

### macOS (Full Support)
- ✅ System crontab validation (`/etc/crontab`)
- ✅ User crontab validation (via `crontab -l -u username`)
- ✅ User existence validation
- ✅ Daemon/service checks via launchctl
- ✅ All crontab syntax features
- ✅ File permissions validation
- ✅ Cron daemon status checks (`com.vix.cron` / `com.apple.cron`)

### Windows (Full Support)
- ✅ File-based crontab syntax validation
- ✅ User existence checks (via `net user`)
- ✅ System crontab access (`%ProgramData%\crontab`, `C:\etc\crontab`, Cygwin, MSYS2, or `CRONTAB_SYSTEM_PATH`)
- ✅ Daemon/service checks via `sc`
- ✅ All crontab syntax features supported
- ✅ File permissions validation via `icacls`
- ✅ Cron daemon status checks (Task Scheduler service `Schedule`, or an installed cron service)

### Cross-Platform Features
- ✅ Syntax validation for all time fields
- ✅ Special keyword validation
- ✅ Dangerous command detection
- ✅ Environment variable validation
- ✅ Multi-line command support
- ✅ File format validation (newline at end)
- ✅ RFC compliance checks

## Supported Crontab Syntax

### Basic Format

**User Crontab:**
```
minute hour day month weekday command
```

**System Crontab:**
```
minute hour day month weekday user command
```

### Time Fields

#### Minutes (0-59)
- Single value: `30`
- Range: `0-30`
- List: `0,15,30,45`
- Step: `*/15` (every 15 minutes)
- All: `*`

#### Hours (0-23)
- Single value: `14`
- Range: `9-17`
- List: `0,6,12,18`
- Step: `*/3` (every 3 hours)
- All: `*`

#### Day of Month (1-31)
- Single value: `15`
- Range: `1-15`
- List: `1,15,30`
- Step: `*/2` (every 2 days)
- All: `*`

#### Month (1-12, or JAN-DEC)
- Single value: `6`
- Name: `JAN`
- Range: `1-6`
- List: `1,6,12`
- Step: `*/3` (every 3 months)
- All: `*`

#### Day of Week (0-7, where 0 and 7 are Sunday, or SUN-SAT)
- Single value: `1` (Monday)
- Name: `MON`
- Range: `1-5` (Monday to Friday)
- List: `1,3,5` (Monday, Wednesday, Friday)
- Step: `*/2` (every 2 days)
- All: `*`

### Special Keywords

#### User Crontab
```
@reboot    command
@yearly    command
@annually  command
@monthly   command
@weekly    command
@daily     command
@midnight  command
@hourly    command
```

#### System Crontab
```
@reboot    user command
@yearly    user command
@annually  user command
@monthly   user command
@weekly    user command
@daily     user command
@midnight  user command
@hourly    user command
```

### Environment Variables
```
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=user@example.com
HOME=/home/user
```

`SHELL` and `HOME` must be absolute paths. `PATH` must be non-empty. `MAILTO` may be empty, a username, or an email address. Other names are accepted when they are identifiers and the value has no spaces.

### Multi-line Commands
```
0 2 * * * /usr/bin/script.sh \
    && /usr/bin/another_script.sh \
    || echo "Error occurred"
```

### System Crontab Specific Features

#### Dash Prefix (Syslog Suppression)
```
-0 2 * * * root /usr/bin/backup.sh
```
The `-` prefix before the minute field suppresses syslog logging.

#### User Field Validation
- Must be a valid system user
- Cannot contain spaces, quotes, or special characters
- The account must exist (`id` on Linux and macOS, `net user` on Windows)

## Validation Rules

### Time Field Validation
- Values must be within valid ranges
- Negative values are not allowed
- Month and weekday fields accept numbers or the names `JAN`-`DEC` and `SUN`-`SAT`
- Other non-numeric values are not allowed
- Ranges must be in ascending order (e.g., `1-5`, not `5-1`)
- Steps must be positive integers

### Command Field Validation
- Command field is required
- Dangerous commands are detected and flagged (`rm -rf /`, `mkfs` of a device, `dd` from `/dev/zero` or `/dev/urandom`, a fork bomb, `chmod -R 777 /`)
- Multi-line commands are supported with `\` continuation

### User Field Validation (System Crontab)
- User field is required
- User must be a valid username format
- User existence is verified on Linux, macOS, and Windows

### Special Keyword Validation
- Keywords are case-sensitive (must be lowercase)
- Command is required after keyword
- User field is required for system crontab
- Extra arguments are allowed as part of the command

## Error Messages

### Time Field Errors
- `Invalid minutes value: X` - Value outside 0-59 range
- `Invalid hours value: X` - Value outside 0-23 range
- `Invalid day of month value: X` - Value outside 1-31 range
- `Invalid month value: X` - Value outside 1-12 range
- `Invalid day of week value: X` - Value outside 0-7 range

### Structure Errors
- `Insufficient fields for user crontab` - Less than 6 fields
- `Insufficient fields for system crontab` - Less than 7 fields
- `Too many fields for user crontab` - More than 6 fields
- `Too many fields for system crontab` - More than 7 fields

### User Field Errors
- `Invalid user field format` - Contains invalid characters
- `User does not exist: username` - User not found

### Command Field Errors
- `Missing command field` - No command specified
- `Dangerous command detected: command` - Potentially harmful command

### Special Keyword Errors
- `Invalid special keyword: @keyword` - Unknown keyword
- `Missing command for special keyword` - No command after keyword
- `Missing user field for system crontab special keyword` - No user specified

## Examples

### Valid User Crontab Entries
```
# Basic entry
0 2 * * * /usr/bin/backup.sh

# With step values
*/15 * * * * /usr/bin/monitor.sh

# With ranges
0 8-17 * * 1-5 /usr/bin/business_hours.sh

# Special keyword
@reboot /usr/bin/startup.sh

# Environment variable
SHELL=/bin/bash
```

### Valid System Crontab Entries
```
# Basic entry
0 2 * * * root /usr/bin/backup.sh

# With dash prefix
-0 2 * * * root /usr/bin/backup.sh

# Special keyword
@reboot root /usr/bin/startup.sh

# Environment variable
SHELL=/bin/sh
```

### Invalid Entries
```
# Invalid minutes
60 * * * * /usr/bin/script.sh

# Missing command
0 2 * * *

# Invalid special keyword
@invalid /usr/bin/script.sh

# Invalid user (system crontab)
0 2 * * * invalid_user /usr/bin/script.sh
```

## Platform-Specific Behavior

### Linux (Full Support)
**System Integration:**
- ✅ Automatic system crontab detection (`/etc/crontab`)
- ✅ User crontab retrieval via `crontab -l -u username`
- ✅ User existence validation using `id` command
- ✅ Cron daemon status checks via `systemctl is-active cron`
- ✅ File permissions validation for system crontab

**Validation Features:**
- ✅ All syntax validation features
- ✅ User existence checks for system crontab entries
- ✅ Daemon status warnings if cron service is not running
- ✅ File permission warnings for insecure system crontab

### macOS (Full Support)
**System Integration:**
- ✅ Automatic system crontab detection (`/etc/crontab`)
- ✅ User crontab retrieval via `crontab -l -u username` and `/usr/lib/cron/tabs`
- ✅ User existence validation using `id` command
- ✅ Daemon/service checks via `launchctl list`
- ✅ Cron daemon status checks for `com.vix.cron` and `com.apple.cron`
- ✅ File permissions validation for system crontab

**Validation Features:**
- ✅ All syntax validation features
- ✅ User existence checks for system crontab entries
- ✅ Daemon status warnings if cron is not loaded in launchd
- ✅ File permission warnings for insecure system crontab

### Windows (Full Support)
**System Integration:**
- ✅ System crontab detection (`%ProgramData%\crontab`, `C:\etc\crontab`, Cygwin, MSYS2, or `CRONTAB_SYSTEM_PATH`)
- ✅ User crontab retrieval via `crontab -l -u username` and per-user spool paths
- ✅ User existence validation using `net user`
- ✅ Daemon/service checks via `sc query`
- ✅ Cron daemon status checks for the Task Scheduler service (`Schedule`) and an installed cron service
- ✅ File permissions validation via `icacls` (no world write; owner Administrators or SYSTEM)

**Validation Features:**
- ✅ All syntax validation features
- ✅ User existence checks for system crontab entries
- ✅ Daemon status warnings if Task Scheduler and cron services are stopped
- ✅ File permission warnings for a world-writable crontab ACL

**Windows Usage:**
```bash
checkcrontab
checkcrontab myfile.cron
checkcrontab -S system.cron -U user.cron
checkcrontab -u username
```

### Cross-Platform Compatibility
**Always Supported:**
- ✅ Crontab syntax validation
- ✅ Time field validation (minutes, hours, days, months, weekdays)
- ✅ Special keyword validation (@reboot, @daily, etc.)
- ✅ Dangerous command detection
- ✅ Environment variable validation
- ✅ Multi-line command support
- ✅ File format validation (newline at end)
- ✅ RFC compliance checks

**Platform integration (every supported OS):**
- User existence validation (`id` on Linux/macOS, `net user` on Windows)
- System crontab access (`/etc/crontab` on Linux/macOS; ProgramData, `C:\etc\crontab`, Cygwin, MSYS2, or `CRONTAB_SYSTEM_PATH` on Windows)
- Daemon and service checks (systemd, launchd, or the Service Control Manager)
- File permissions validation (Unix mode on Linux/macOS, ACLs on Windows)
