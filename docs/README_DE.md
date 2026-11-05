## Checkcrontab - Syntax in crontab-Dateien überprüfen

[![CI](https://github.com/wachawo/checkcrontab/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/checkcrontab/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/checkcrontab/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/checkcrontab?branch=main)
[![PyPI](https://img.shields.io/pypi/v/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)
[![Downloads](https://img.shields.io/pypi/dm/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/checkcrontab/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)


Ein Python-Skript zur Überprüfung der Syntax von crontab-Dateien. Plattformübergreifende Unterstützung für Linux, macOS und Windows.

**[English](https://github.com/wachawo/checkcrontab/blob/main/README.md)** | [Español](https://github.com/wachawo/checkcrontab/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/checkcrontab/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/checkcrontab/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/checkcrontab/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/checkcrontab/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/checkcrontab/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/checkcrontab/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/checkcrontab/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/checkcrontab/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/checkcrontab/blob/main/docs/README_KR.md)

### Anforderungen

- **Python 3.7 oder höher**
- **Linux**: `systemctl` für Dienste und den Cron-Daemon, Lesezugriff auf `/etc/crontab`
- **macOS**: `launchctl` für launchd und cron (`com.vix.cron`), Lesezugriff auf `/etc/crontab`
- **Windows**: `sc` und `net` für den Taskplaner und lokale Konten, `icacls` für ACLs

### Plattformunterstützung

**Linux (Vollständige Unterstützung):**
- ✅ System-crontab-Validierung (`/etc/crontab`)
- ✅ Benutzer-crontab-Validierung (über `crontab -l -u username`)
- ✅ Benutzerexistenz-Validierung
- ✅ Daemon/Service-Prüfungen über systemctl
- ✅ Alle crontab-Syntax-Funktionen
- ✅ Prüfung der Dateirechte
- ✅ Status des Cron-Daemons

**macOS (Vollständige Unterstützung):**
- ✅ System-crontab-Validierung (`/etc/crontab`)
- ✅ Benutzer-crontab-Validierung (über `crontab -l -u username`)
- ✅ Benutzerexistenz-Validierung
- ✅ Daemon/Service-Prüfungen über launchctl
- ✅ Alle crontab-Syntax-Funktionen
- ✅ Prüfung der Dateirechte
- ✅ Status des Cron-Daemons (`com.vix.cron` / `com.apple.cron`)

**Windows (Vollständige Unterstützung):**
- ✅ Dateibasierte crontab-Syntax-Validierung
- ✅ Benutzerexistenz-Prüfungen (über `net user`)
- ✅ Zugriff auf die System-crontab (`%ProgramData%\crontab`, `C:\etc\crontab`, Cygwin, MSYS2 oder `CRONTAB_SYSTEM_PATH`)
- ✅ Daemon/Service-Prüfungen über `sc`
- ✅ Alle crontab-Syntax-Funktionen unterstützt
- ✅ Rechteprüfung über `icacls`
- ✅ Status des Taskplaners (`Schedule`) oder eines installierten Cron-Dienstes

### Installation

```bash
pip3 install checkcrontab
```

Oder von GitHub:

```bash
pip3 install git+https://github.com/wachawo/checkcrontab.git
```

### Verwendung

```bash
# System-crontab prüfen (nur Linux/macOS)
checkcrontab

# Crontab-Datei prüfen
checkcrontab /etc/crontab

# Benutzer-crontab prüfen (nur Linux/macOS)
checkcrontab username

# Mit expliziten Typ-Flags prüfen
checkcrontab -S system.cron -U user.cron -u username1 -u username2

# Alle crontab-Dateien in einem Verzeichnis prüfen
checkcrontab /etc/cron.d

# Hilfe anzeigen
checkcrontab --help

# Version anzeigen
checkcrontab --version
```

### JSON-Ausgabe

Für maschinenlesbare Ausgabe verwenden Sie das `--format json`-Flag:

```bash
checkcrontab --format json examples/user_valid.txt
```

Beispiel JSON-Ausgabe:

```json
{
  "success": true,
  "total_files": 2,
  "total_rows": 27,
  "total_rows_errors": 0,
  "total_errors": 0,
  "files": [
    {
      "file": "/etc/crontab",
      "is_system_crontab": true,
      "rows": 5,
      "rows_errors": 0,
      "errors_count": 0,
      "errors": [],
      "success": true
    },
    {
      "file": "examples/user_valid.txt",
      "is_system_crontab": false,
      "rows": 22,
      "rows_errors": 0,
      "errors_count": 0,
      "errors": [],
      "success": true
    }
  ]
}
```

### Kommandozeilenoptionen

- `-S, --system` - System-crontab-Dateien
- `-U, --user` - Benutzer-crontab-Dateien
- `-u, --username` - Zu prüfende Benutzernamen
- `-v, --version` - Version anzeigen
- `-d, --debug` - Debug-Ausgabe
- `-n, --no-colors` - Farbige Ausgabe deaktivieren
- `--format {text,json,sarif}` - Ausgabeformat (Standard: text)
- `--strict` - Warnungen als Fehler behandeln
- `--exit-zero` - Immer mit Code 0 beenden

### Funktionen

- **Plattformübergreifende Syntax-Validierung** (Linux, macOS, Windows)
- **Plattformspezifische Funktionen:**
  - **Linux/macOS**: System- und Benutzer-crontab-Validierung, Benutzerexistenz-Prüfung, Daemon-Validierung
  - **Windows**: Nur dateibasierte Validierung
- **Zeitfeld-Validierung** (Minuten, Stunden, Tage, Monate, Wochentage)
- **Gefährliche Befehle erkennen**
- **Unterstützung für spezielle Schlüsselwörter** (@reboot, @daily, etc.)
- **Unterstützung für mehrzeilige Befehle**

### Dokumentation

- **[Features Documentation](https://github.com/wachawo/checkcrontab/blob/main/docs/FEATURES.md)** - Detaillierte Dokumentation der Funktionen und Fähigkeiten

### Entwicklungstools

```bash
pip3 install pre-commit flake8 pytest mypy ruff
pre-commit install
pre-commit run --all-files
pre-commit autoupdate
```

### Verwendung mit pre-commit

Sie können checkcrontab als pre-commit-Hook in Ihren Projekten verwenden:

1. Fügen Sie zu Ihrer `.pre-commit-config.yaml` hinzu:

```yaml
repos:
  - repo: https://github.com/wachawo/checkcrontab
    rev: 0.0.8  # Verwenden Sie die neueste Version
    hooks:
      - id: checkcrontab
```

2. Installieren Sie pre-commit:

```bash
pip install pre-commit
pre-commit install
```

3. Der Hook überprüft automatisch alle `.cron`, `.crontab` und `.tab` Dateien in Ihrem Repository.

### Lizenz

MIT License
