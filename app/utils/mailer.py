"""メール送信ユーティリティ

投稿結果通知などのメールを送信する。

【送信方式】
1. **Resend 送信API（推奨・優先）**
   - `RESEND_API_KEY` が設定されていれば Resend の HTTP API で送信する。
   - お名前.com の「海外からの送信制限」に影響されず（Cloud Run の US 判定 IP でも送れる）、
     独自ドメイン `carroo@takeuchiunso.com` を SPF/DKIM 認証済みで送信できる。
   - 差出人ドメイン（takeuchiunso.com）は Resend 側でドメイン認証しておくこと。
2. **SMTP（フォールバック）**
   - `RESEND_API_KEY` 未設定で `SMTP_HOST/SMTP_USER/SMTP_PASSWORD` が揃っていれば SMTP で送信。
   - ローカル検証や将来の別プロバイダ用に残している。
   - ⚠️ Cloud Run から お名前.com SMTP へは US 国コード判定で 554 拒否されるため本番では不可。

【.env 設定】
    # 方式1（推奨）
    RESEND_API_KEY=re_xxxxxxxx
    MAIL_FROM=carroo@takeuchiunso.com          # 送信元（Resend で認証したドメインのアドレス）
    MAIL_FROM_NAME=Carroo 投稿システム          # 差出人表示名（任意）
    # 方式2（フォールバック）
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / MAIL_FROM

いずれも未設定の場合は送信をスキップして警告ログのみ残す（投稿処理は失敗させない）。
"""
import json
import logging
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM_NAME = "Carroo 投稿システム"


def is_mail_configured() -> bool:
    """メール送信設定（Resend か SMTP のいずれか）が揃っているか"""
    if os.getenv("RESEND_API_KEY"):
        return True
    return bool(
        os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")
    )


def _mail_from() -> str:
    """送信元アドレス（Resend 認証ドメインのアドレス）。SMTP 用に SMTP_USER も許容。"""
    return os.getenv("MAIL_FROM") or os.getenv("SMTP_USER") or ""


def _from_header(mail_from: str) -> str:
    """差出人ヘッダ 'Name <addr>' を生成（表示名は RFC2047 でエンコード）"""
    name = os.getenv("MAIL_FROM_NAME", DEFAULT_FROM_NAME)
    return formataddr((str(Header(name, "utf-8")), mail_from))


def _send_via_resend(to_address: str, subject: str, body: str) -> bool:
    """Resend 送信API でテキストメールを送信する"""
    api_key = os.getenv("RESEND_API_KEY")
    mail_from = _mail_from()
    if not mail_from:
        logger.warning("[Mailer] MAIL_FROM 未設定のため Resend 送信をスキップ")
        return False
    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            content=json.dumps(
                {
                    "from": _from_header(mail_from),
                    "to": [to_address],
                    "subject": subject,
                    "text": body,
                }
            ),
            timeout=30,
        )
        if resp.status_code in (200, 201):
            msg_id = ""
            try:
                msg_id = resp.json().get("id", "")
            except Exception:
                pass
            logger.info(f"[Mailer] Resend 送信成功: {to_address} 「{subject}」 id={msg_id}")
            return True
        logger.error(
            f"[Mailer] Resend 送信失敗: {to_address} "
            f"status={resp.status_code} body={resp.text[:300]}"
        )
        return False
    except Exception as e:
        logger.error(f"[Mailer] Resend 送信エラー: {to_address} - {e}")
        return False


def _send_via_smtp(to_address: str, subject: str, body: str) -> bool:
    """SMTP でテキストメールを送信する（フォールバック）"""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    mail_from = _mail_from()

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = _from_header(mail_from)
        msg["To"] = to_address

        # ポート 465 は SSL 方式、それ以外（587 等）は STARTTLS 方式で接続
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(user, password)
                server.sendmail(mail_from, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(mail_from, [to_address], msg.as_string())

        logger.info(f"[Mailer] SMTP 送信成功: {to_address} 「{subject}」")
        return True
    except Exception as e:
        logger.error(f"[Mailer] SMTP 送信失敗: {to_address} - {e}")
        return False


def send_email(to_address: str, subject: str, body: str) -> bool:
    """テキストメールを送信する

    RESEND_API_KEY があれば Resend、無ければ SMTP を使う。

    Returns:
        送信成功なら True。未設定・送信失敗時は False（例外は投げない）
    """
    if not to_address:
        logger.warning("[Mailer] 宛先が空のため送信スキップ")
        return False
    if not is_mail_configured():
        logger.warning(
            "[Mailer] メール未設定のため送信スキップ "
            "(RESEND_API_KEY か SMTP_HOST/SMTP_USER/SMTP_PASSWORD を設定してください) "
            f"宛先={to_address} 件名={subject}"
        )
        return False

    if os.getenv("RESEND_API_KEY"):
        return _send_via_resend(to_address, subject, body)
    return _send_via_smtp(to_address, subject, body)
