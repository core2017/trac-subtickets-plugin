# Subtickets 表示の構造

## アーキテクチャ

サブチケット一覧は以下の流れで表示される。

1. `web_ui.py` の `post_process_request` で Python 側がチケットデータを組み立てる
2. `add_script_data` で JS にデータを渡す（`window.tracSubticketsData`）
3. `htdocs/js/subtickets.js` が DOM を生成してページに挿入する
4. スタイルは `htdocs/css/subtickets.css` が担当

## closed チケットの打ち消し線

CSS 側には既に `.subtickets a.closed { text-decoration: line-through; }` が定義済み。
`subtickets.js` のリンク生成時に `status === 'closed'` なら `closed` クラスを付与することで対応。

行全体に打ち消し線を入れたい場合は `<tr>` に `closed` クラスを付与し、
CSS で `tr.closed td { text-decoration: line-through; }` を追加すればよい。

## trac.ini との関係

`api.py` の環境アップグレード処理で、`parents` カスタムフィールドが未定義の場合に
`trac.ini` へ自動書き込みする。既存環境でラベルを変更したい場合は `trac.ini` を直接編集する。
