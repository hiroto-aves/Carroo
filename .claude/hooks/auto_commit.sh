#!/bin/bash
# 返答のたびに変更を自動コミットする Stop hook
# - 変更がなければコミットしない
# - マージ/リベース進行中は安全のためスキップ
# - push は1日1回: 前回 push 時と日付が変わっていたら push する
#   （最終 push 日は .claude/.last_push_date に記録・gitignore 対象）

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

# git リポジトリでなければ終了
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# マージ・リベース進行中はスキップ（壊れた状態でのコミット防止）
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    exit 0
fi

# --- 自動コミット ---
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit --quiet -m "chore: 自動コミット $(date '+%Y-%m-%d %H:%M')

Claude Code の Stop hook による返答単位の自動コミット

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
fi

# --- 1日1回の自動 push ---
# 前回 push した日付と今日が違えば push（同日2回目以降はスキップ）
DATE_FILE=".claude/.last_push_date"
TODAY=$(date '+%Y-%m-%d')
LAST_PUSH=$(cat "$DATE_FILE" 2>/dev/null)

if [ "$TODAY" != "$LAST_PUSH" ]; then
    # 未 push のコミットがある場合のみ push
    AHEAD=$(git rev-list --count origin/main..main 2>/dev/null || echo 0)
    if [ "$AHEAD" -gt 0 ]; then
        if git push --quiet origin main 2>/dev/null; then
            echo "$TODAY" > "$DATE_FILE"
        fi
        # push 失敗時（ネットワーク断・認証切れ等）は日付を記録せず、
        # 次の返答時に再試行される
    else
        # push すべきものが無い日はスキップ扱いにせず日付だけ更新
        echo "$TODAY" > "$DATE_FILE"
    fi
fi

exit 0
