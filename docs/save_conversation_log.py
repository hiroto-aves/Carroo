#!/usr/bin/env python3
"""会話ログ自動保存スクリプト

Claude Code のトランスクリプト（JSONL）を解析し、会話をまとめずそのまま
docs/conversation_logs/YYYY-MM-DD.txt に日付ごとに保存する。

- Claude が返答するたびに Stop hook から自動実行される（.claude/settings.json）
- 実行のたびに当日までの全会話を日付ファイルへ反映（追記と同じ効果・重複なし）
- ユーザー発言・Claude返答・ツール呼び出しと結果をすべて含む
- 手動実行: python3 docs/save_conversation_log.py

hook からは stdin に JSON（transcript_path 含む）が渡される。
手動実行時はプロジェクトのトランスクリプトディレクトリを全走査する。
"""
import json
import sys
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "docs" / "conversation_logs"
# Claude Code のトランスクリプト保存場所（プロジェクトパスから自動決定）
TRANSCRIPT_DIR = Path.home() / ".claude" / "projects" / str(PROJECT_ROOT).replace("/", "-")
JST = timezone(timedelta(hours=9))

# ツール結果の最大保存長（画像やバイナリの巨大データはログに不要）
MAX_RESULT_LEN = 4000


def jst_date(ts: str) -> str:
    """ISO タイムスタンプ → JST の日付文字列"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return datetime.now(JST).strftime("%Y-%m-%d")


def jst_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return "--:--:--"


def clean(text: str) -> str:
    """base64 等の巨大バイナリ文字列を除去"""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, default=str)
    text = re.sub(r"[A-Za-z0-9+/=]{500,}", "[バイナリデータ省略]", text)
    if len(text) > MAX_RESULT_LEN:
        text = text[:MAX_RESULT_LEN] + f"\n…（{len(text) - MAX_RESULT_LEN} 文字省略）"
    return text


def format_entry(rec: dict) -> tuple:
    """JSONL 1レコード → (日付, 整形テキスト) or None"""
    rec_type = rec.get("type")
    ts = rec.get("timestamp", "")
    msg = rec.get("message", {})

    if rec_type == "user":
        content = msg.get("content")
        parts = []
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for c in content:
                if c.get("type") == "text":
                    parts.append(c["text"])
                elif c.get("type") == "tool_result":
                    body = c.get("content", "")
                    if isinstance(body, list):
                        body = "\n".join(
                            x.get("text", "[画像]") if isinstance(x, dict) else str(x)
                            for x in body
                        )
                    parts.append(f"【ツール結果】\n{clean(body)}")
        if not parts:
            return None
        text = "\n".join(parts)
        # ツール結果のみのレコードはラベルを変える
        label = "🔧 ツール結果" if text.startswith("【ツール結果】") else "👤 ユーザー"
        return jst_date(ts), f"[{jst_time(ts)}] {label}\n{text}\n"

    if rec_type == "assistant":
        content = msg.get("content", [])
        parts = []
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "text":
                parts.append(f"🤖 Claude:\n{c['text']}")
            elif c.get("type") == "tool_use":
                inp = clean(json.dumps(c.get("input", {}), ensure_ascii=False))
                parts.append(f"🔨 ツール呼び出し: {c.get('name')}\n{inp}")
        if not parts:
            return None
        return jst_date(ts), f"[{jst_time(ts)}] " + "\n".join(parts) + "\n"

    return None


def collect_transcripts() -> list:
    """対象のトランスクリプトファイル一覧"""
    # hook 実行時: stdin から transcript_path を受け取る
    if not sys.stdin.isatty():
        try:
            payload = json.load(sys.stdin)
            tp = payload.get("transcript_path")
            if tp and Path(tp).exists():
                return [Path(tp)]
        except (json.JSONDecodeError, ValueError):
            pass
    # 手動実行時: プロジェクトの全トランスクリプトを走査
    if TRANSCRIPT_DIR.exists():
        return sorted(TRANSCRIPT_DIR.glob("*.jsonl"))
    return []


def main():
    files = collect_transcripts()
    if not files:
        print("トランスクリプトが見つかりません", file=sys.stderr)
        return

    by_date = {}
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry = format_entry(rec)
            if entry:
                date, text = entry
                by_date.setdefault(date, []).append(text)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    sep = "─" * 70 + "\n"
    for date, entries in by_date.items():
        out = LOG_DIR / f"{date}.txt"
        header = f"# 会話ログ {date}（自動保存・全文そのまま）\n\n"
        out.write_text(header + sep.join(entries), encoding="utf-8")
    print(f"保存完了: {', '.join(sorted(by_date))} → {LOG_DIR}")


if __name__ == "__main__":
    main()
