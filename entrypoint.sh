#!/bin/bash
# Carroo コンテナ起動スクリプト
# 🔴 Trabox の Vue/ant-design 日付コンポーネントは headless Chromium だと選択が
#    確定せず投稿に失敗する。ローカルの headed 実行では成功しているため、Cloud Run でも
#    Xvfb（仮想ディスプレイ）上で headed Chromium を動かす。TRABOX_HEADLESS=False と併用。
#
# xvfb-run はラッパの引数解釈と起動プローブ相性で不安定だったため、Xvfb を直接起動して
# DISPLAY を渡す方式にする。uvicorn は前面で即 $PORT を待受するので起動プローブは速やかに通る。

set -e

# 前回起動のロックが残っていれば除去（Cloud Run の再利用対策）
rm -f /tmp/.X99-lock 2>/dev/null || true

# 仮想ディスプレイ :99 をバックグラウンド起動
Xvfb :99 -screen 0 1440x2400x24 -nolisten tcp -ac >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# Web UI＋/tasks/execute（投稿ワーカー）を同一プロセスで提供
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
