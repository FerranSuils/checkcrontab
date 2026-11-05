## Checkcrontab - crontabファイルの構文をチェック

[![CI](https://github.com/wachawo/checkcrontab/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/checkcrontab/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/checkcrontab/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/checkcrontab?branch=main)
[![PyPI](https://img.shields.io/pypi/v/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)
[![Downloads](https://img.shields.io/pypi/dm/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/checkcrontab/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/checkcrontab.svg)](https://pypi.org/project/checkcrontab/)

crontabファイルの構文をチェックするPythonスクリプト。Linux、macOS、Windowsのクロスプラットフォームサポート。

**[English](https://github.com/wachawo/checkcrontab/blob/main/README.md)** | [Español](https://github.com/wachawo/checkcrontab/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/checkcrontab/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/checkcrontab/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/checkcrontab/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/checkcrontab/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/checkcrontab/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/checkcrontab/blob/main/docs/README_ZH.md) | **[日本語](https://github.com/wachawo/checkcrontab/blob/main/docs/README_JA.md)** | [हिन्दी](https://github.com/wachawo/checkcrontab/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/checkcrontab/blob/main/docs/README_KR.md)

### 要件

- **Python 3.7以上**
- **Linux**: サービスと cron デーモン確認用の `systemctl`、`/etc/crontab` の読み取り
- **macOS**: launchd と cron（`com.vix.cron`）確認用の `launchctl`、`/etc/crontab` の読み取り
- **Windows**: タスク スケジューラとローカル アカウント用の `sc` / `net`、ACL 用の `icacls`

### プラットフォームサポート

**Linux（完全サポート）：**
- ✅ システム crontab 検証（`/etc/crontab`）
- ✅ ユーザー crontab 検証（`crontab -l -u username`）
- ✅ ユーザー存在確認
- ✅ systemctl によるデーモン/サービス確認
- ✅ すべての crontab 構文機能
- ✅ ファイル権限の検証
- ✅ cron デーモンの状態確認

**macOS（完全サポート）：**
- ✅ システム crontab 検証（`/etc/crontab`）
- ✅ ユーザー crontab 検証（`crontab -l -u username`）
- ✅ ユーザー存在確認
- ✅ launchctl によるデーモン/サービス確認
- ✅ すべての crontab 構文機能
- ✅ ファイル権限の検証
- ✅ cron の状態確認（`com.vix.cron` / `com.apple.cron`）

**Windows（完全サポート）：**
- ✅ ファイルベースの crontab 構文検証
- ✅ ユーザー存在確認（`net user`）
- ✅ システム crontab へのアクセス（`%ProgramData%\crontab`、`C:\etc\crontab`、Cygwin、MSYS2、または `CRONTAB_SYSTEM_PATH`）
- ✅ `sc` によるデーモン/サービス確認
- ✅ すべての crontab 構文機能
- ✅ `icacls` による権限検証
- ✅ タスク スケジューラ（`Schedule`）または導入済み cron サービスの状態確認

### インストール

```bash
pip3 install checkcrontab
```

またはGitHubから：

```bash
pip3 install git+https://github.com/wachawo/checkcrontab.git
```

### 使用方法

```bash
# システム crontab をチェック（Linux/macOS のみ）
checkcrontab

# crontab ファイルをチェック
checkcrontab /etc/crontab

# ユーザー crontab をチェック（Linux/macOS のみ）
checkcrontab username

# 明示的なタイプフラグでチェック
checkcrontab -S system.cron -U user.cron -u username1 -u username2

# ディレクトリ内のすべての crontab をチェック
checkcrontab /etc/cron.d

# ヘルプを表示
checkcrontab --help

# バージョンを表示
checkcrontab --version
```

### JSON出力

機械可読な出力には`--format json`フラグを使用：

```bash
checkcrontab --format json examples/user_valid.txt
```

JSON出力例：

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

### コマンドラインオプション

- `-S, --system` - システムcrontabファイル
- `-U, --user` - ユーザーcrontabファイル
- `-u, --username` - チェックするユーザー名
- `-v, --version` - バージョンを表示
- `-d, --debug` - デバッグ出力
- `-n, --no-colors` - カラー出力を無効化
- `--format {text,json,sarif}` - 出力形式（デフォルト：text）
- `--strict` - 警告をエラーとして扱う
- `--exit-zero` - 常にコード 0 で終了

### 機能

- **クロスプラットフォーム構文検証**（Linux、macOS、Windows）
- **プラットフォーム固有機能：**
  - **Linux/macOS**: システムおよびユーザーcrontab検証、ユーザー存在性チェック、デーモン検証
  - **Windows**: ファイルベースの検証のみ
- **時間フィールド検証**（分、時、日、月、曜日）
- **危険なコマンド検出**
- **特別なキーワードサポート**（@reboot、@dailyなど）
- **複数行コマンドサポート**

### ドキュメント

- **[Features Documentation](https://github.com/wachawo/checkcrontab/blob/main/docs/FEATURES.md)** - 機能と機能の詳細ドキュメント

### 開発ツール

```bash
pip3 install pre-commit flake8 pytest mypy ruff
pre-commit install
pre-commit run --all-files
pre-commit autoupdate
```

### pre-commitでの使用

プロジェクトでcheckcrontabをpre-commitフックとして使用できます：

1. `.pre-commit-config.yaml`に追加：

```yaml
repos:
  - repo: https://github.com/wachawo/checkcrontab
    rev: 0.0.8  # 最新バージョンを使用
    hooks:
      - id: checkcrontab
```

2. pre-commitをインストール：

```bash
pip install pre-commit
pre-commit install
```

3. フックは自動的にリポジトリ内のすべての`.cron`、`.crontab`、`.tab`ファイルをチェックします。

### ライセンス

MIT License
