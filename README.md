# gip

Git が「見える」と判断する作業ツリーだけを ZIP にする、小さな CLI です。

```sh
install -m 755 gip ~/.local/bin/gip
cd /path/to/repository
gip                 # カレントディレクトリに <repo>.zip
gip /tmp/source.zip # 出力先を指定
```

`gip` はリポジトリのルートを検出し、次の集合を現在の内容で格納します。

- tracked files（変更済みを含む）
- untracked かつ Git に ignore されていない files

各階層の `.gitignore`、`.git/info/exclude`、global excludes は Git 自身の
`git ls-files --cached --others --exclude-standard` に任せます。`.git`、削除済み
tracked files、空ディレクトリ、出力 ZIP 自身、submodule の中身は入りません。
symlink は追跡せず、リンクとして格納します。
リポジトリ外へ解決される親 symlink の先は辿りません。

### 対応する ignore の範囲

| 用途 | Git が参照する場所 |
| --- | --- |
| チームで共有 | 各階層の `.gitignore` |
| そのリポジトリだけ・共有しない | `git rev-parse --git-path info/exclude` が示す `info/exclude` |
| ユーザー共通 | `core.excludesFile`、または `$XDG_CONFIG_HOME/git/ignore` |

たとえば個人用IDEファイルなど、`.gitignore` にcommitしたくないパターンは
`.git/info/exclude` に書けます。linked worktree等でもGitに正しい場所を解決させる
ため、場所の確認には次を使います。

```sh
git rev-parse --git-path info/exclude
```

これらはすべて `--exclude-standard` 経由で `gip` に反映されます。

必要なのは Python 3.8 以上と Git 2.31 以上だけです。テストは次で実行できます。

```sh
python3 -m unittest -v
```

## 既存手段の調査

2026-08-30 時点で類似品はありますが、Git の ignore 判定をそのまま使って
`tracked + untracked non-ignored` の作業ツリーを、追加除外・内容変換なしで
安全に ZIP 化する小さな汎用 CLI は見当たりませんでした。

## 制限

submodule は境界として扱い、中身を再帰しません。必要になった時点で各
submodule に同じ Git 列挙を再帰適用するのが拡張点です。
