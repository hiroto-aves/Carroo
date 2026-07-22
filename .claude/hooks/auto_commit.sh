#!/bin/bash
# 返答のたびに変更を自動コミットする Stop hook
# - 変更がなければ何もしない
# - マージ/リベース進行中は安全のためスキップ
# - push はしない（「保存して」指示のときのみ手動フローで push）

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

# git リポジトリでなければ終了
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# マージ・リベース進行中はスキップ（壊れた状態でのコミット防止）
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    exit 0
fi

# 変更がなければ終了
[ -z "$(git status --porcelain)" ] && exit 0

git add -A
git commit --quiet -m "chore: 自動コミット $(date '+%Y-%m-%d %H:%M')

Claude Code の Stop hook による返答単位の自動コミット

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"

exit 0
