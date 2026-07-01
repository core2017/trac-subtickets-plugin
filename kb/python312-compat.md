# Python 3.12 対応

## NameError: name 'tracsubtickets' is not defined

### 問題

Python 3.12 にアップデート後、Trac が以下のエラーを返すようになった。

```
TracError: Unable to check for upgrade of tracsubtickets.api.SubTicketsSystem:
NameError: name 'tracsubtickets' is not defined
```

### 原因

2つの問題が絡んでいた。

1. `tracsubtickets/__init__.py` で `pkg_resources.require('Trac >= 1.0')` を呼んでいた。
   Python 3.12 では `pkg_resources` の挙動が変わり、これが失敗するケースがある。

2. Python 3.12 では、`__init__.py` で例外が発生したモジュールは `sys.modules` から
   確実に削除される（3.11 以前は部分初期化の状態で残ることがあった）。
   その結果、`api.py` 内の `import tracsubtickets` が失敗し、
   グローバル変数 `tracsubtickets` がバインドされず NameError になっていた。

### 修正（適用済み）

- `tracsubtickets/__init__.py`: `pkg_resources` の import と `require()` を削除（空ファイル化）
  - プラグインは Trac の中でロードされるため、このチェック自体が不要
- `tracsubtickets/api.py`: `import tracsubtickets.db_default` → `from . import db_default`（relative import）
- `tracsubtickets/api.py`: `tracsubtickets.db_default.xxx` → `db_default.xxx`（6箇所）

## 開発環境でのデバッグ実行手順

```sh
# 開発モードでインストール（root で実行）
sudo pip install -e .

# Trac standalone サーバーで起動
tracd --port 8000 /path/to/trac/env
```

`sudo pip` で root 実行すると WARNING が出るが、Trac 本体も同じ方法で
インストールされているため無視してよい。
