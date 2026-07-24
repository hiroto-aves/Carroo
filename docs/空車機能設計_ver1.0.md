# 空車（トラック空き）投稿機能 設計書 ver1.0

最終更新: 2026-07-24 / ステータス: 設計確定（実装前）

荷物（案件）投稿に加え、**トラックの空車情報**を Trabox / WebKit 両プラットフォームへ
投稿する機能。加えて **Google カレンダー風の繰り返し登録** を実装する。

---

## 1. 調査結果（実現性：高）

### WebKit — `CarInfo` API（空車＝車両情報）
- エンドポイント: `https://www.wkit.jp/api/CarInfo`（POST / XML / UTF-8）
- 荷物 `LoadInfo` と完全並行。`operation` = I(登録)/U(更新)/D(削除)、一覧取得は operation なし。
- 主要フィールド（`car_data`）:
  - 必須: `operation`, `vacantdate`(空車日時 `YYYY-MM-DD HH:MM:SS`), `vacantprefecture`(空車県),
    `destdate`(行先日時), `destprefecture`(行先県), `carkindtype`(車種区分), `mix`(積合せ), `opentype`(情報公開)
  - `slipno` は空欄（自動採番）。更新/削除時は 8 桁短縮伝票番号を使用。
  - 任意: `vacantarea`/`destarea`(地区), `weight`/`maxweight`(積載量), `carplate`(車番),
    `driver`(乗務員), `note1`(特記), `equipment`(装備), 担当者情報(personname/tel/…)
  - **`load_able1〜10`(積地可能県) / `dest_able1〜10`(卸地可能県)** … 複数の対応可能エリア
- 実装方針: [webkit.py](../app/automations/webkit.py) の LoadInfo ビルダーを CarInfo 版に複製（流用率ほぼ100%）。

### Trabox — `/truck/register`（荷物 `/baggage/register` と対）
- URL: `https://www.trabox.com/truck/register`（他候補は /notfound）
- 同じ `.tbx-form-item` 構造。フォーム行:
  1. 空車地（日時＋県＋市区町村）
  2. 行先地（日時＋県＋市区町村）
  3. その他対応可能空車地 / 4. その他対応可能行先地（= WebKit の load_able/dest_able に対応）
  5. 車両 / 6. 最低運賃 / 7. 担当者 / 8. 備考　→ 送信ボタン「登録」
- 実装方針: 既存ヘルパー（`_select_datetime`・`_select_prefecture`・`_select_city`・
  TZ=Asia/Tokyo 修正）をそのまま流用。行ラベルのマッピングのみ追加。

---

## 2. 確定した仕様（2026-07-24 ユーザー合意）

1. **繰り返し粒度**: 毎週(複数曜日)・**隔週・毎日・毎月**すべて対応する。
2. **投稿タイミング**: 基本は即時に一気に出す。加えて「空車日の◯日前に自動投稿」も選べる（lead_days）。
3. **その他対応可能行先**: WebKit `dest_able`（複数県）＝「大阪含む複数方面OK」として使う。
4. **祝日スキップ**・**有効期限**（開始/終了）を持たせる。
5. **UI**: 荷物とは別メニュー「空車」を新設。単発登録と繰り返し登録を扱う
   （繰り返しは登録フォーム内オプション方式 or 別一覧、実装時に決定）。
6. **進め方**: Phase 1（単発）→ Phase 2（繰り返し）→ Phase 3（UI仕上げ）の順。

---

## 3. データモデル（荷物と分離）

```
truck_schedules （繰り返しルール）
  └─ materialize（日次バッチ）→ truck_postings （具体的な1回分＝実投稿対象）
                                  └─ posting_history（trabox/webkit × 登録/更新/削除）
```
- 単発登録は `truck_schedules` を介さず `truck_postings` を直接作る。
- Firestore に `truck_postings` / `truck_schedules` コレクションを追加（既存 store.py を拡張）。

### truck_schedules（繰り返しルール）フィールド案
```
freq: DAILY | WEEKLY | BIWEEKLY | MONTHLY
interval, byday:[曜日], bymonthday(月次用)
vacant_time:"09:00", dest_offset_days:+1, dest_time:"07:00"   # 相対時刻で保持
vacant:{pref,city}, dest:{pref,city} または dest_able:[県...]
vehicle, min_freight, platforms:[trabox,webkit]
lead_days（◯日前に投稿）, active_from, active_until（無期限可）
skip_holidays: bool
status: active | paused
```
※ルールは「型」を相対で保持し、実日付は生成時に計算する。

---

## 4. 繰り返しの自動生成（マテリアライズ）
- **Cloud Scheduler（日次 cron・無料枠3ジョブ内＝¥0）** → Cloud Run `/schedules/materialize`
- 各 active ルールで `今日〜今日+lead_days` の該当日を算出（隔週/毎日/毎月/祝日スキップ考慮）
  → 未生成なら `truck_postings` を作成 → 既存 Cloud Tasks キュー（同時1件）へ投入 → 空車ポスター実行
- 重複防止: `rule_id + 空車日` をキーに生成済み管理
- 後始末: 空車日を過ぎた投稿は掲載終了（任意で自動削除）
- 祝日判定: `jpholiday` 等のライブラリ or 内部テーブル

---

## 5. GCP構成（追加最小・¥0維持）
- 追加は Cloud Scheduler 1ジョブ（日次）のみ。Cloud Run / Cloud Tasks / Firestore は既存流用。
- 投稿実行は既存の順序実行キュー（同時1件）に相乗り＝ブラウザ競合なし。

---

## 6. 実装段階
- **Phase 1**: WebKit `CarInfo` ビルダー＋Trabox `/truck/register` 自動化＋空車 CRUD＋一覧UI。
- **Phase 2**: 繰り返しルール＋日次マテリアライズ（Cloud Scheduler）＋祝日スキップ/有効期限。
- **Phase 3**: カレンダー風 繰り返しエディタ、次回投稿プレビュー。

### 実装前の残タスク
- Trabox `/truck/register` の各行の詳細 DOM マッピング（サブ入力の name/セレクタ）
- WebKit `CarInfo` の車種区分など既存コード表の流用可否確認
