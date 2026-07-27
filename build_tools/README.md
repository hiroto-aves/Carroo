# Tailwind セルフホストCSS の再ビルド

本番は `static/tailwind.css`（コミット済みの生成物）を配信する。Play CDN は使わない
（strict CSP のため。unsafe-eval と外部スクリプト依存を排除）。

クラスを追加/変更したら以下で再生成してコミットする：

```bash
# 1) Tailwind standalone CLI（Node 不要の単一バイナリ）を取得（初回のみ）
curl -sL -o /tmp/tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-macos-arm64
chmod +x /tmp/tailwindcss

# 2) ビルド（content グロブは tailwind.config.js の app/**/*.py を走査）
/tmp/tailwindcss -c build_tools/tailwind.config.js \
  -i build_tools/tailwind.input.css -o static/tailwind.css --minify
```

注意:
- クラス名は .py 内の文字列としてスキャンされる。動的連結（`"bg-"+color` 等）は検出
  されないので、そういう用途はインライン style か固定クラスにする。
- 任意値クラス（`grid-cols-[...]`）は極力インライン style にする（取りこぼし回避）。
