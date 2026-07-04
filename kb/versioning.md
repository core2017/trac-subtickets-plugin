# バージョン管理方針

## setup.py のバージョンは本家に追従する

`setup.py` の `version` は upstream（本家 trac-subtickets-plugin）のバージョンに合わせるため、
こちら側で bump しない。ローカルバージョンの管理は port 側で対応する。
