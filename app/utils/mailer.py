"""メール送信ユーティリティ

投稿結果通知などのメールを SMTP で送信する。

【.env 設定（必須）】
    SMTP_HOST=メールプロバイダのSMTPサーバー（例: smtp.gmail.com）
    SMTP_PORT=587 または 465
    SMTP_USER=SMTP認証ユーザー名（通常はメールアドレス）
    SMTP_PASSWORD=SMTP認証パスワード
    MAIL_FROM=送信元アドレス（省略時は SMTP_USER）

任意のSMTPサーバーに対応（Gmail・会社メール・Outlook等）:
- ポート 587 → STARTTLS 方式で自動接続
- ポート 465 → SSL 方式で自動接続（さくら・Xserver等の国内ホスティングに多い）
- Gmail の場合のみ「アプリパスワード」が必要
  （https://myaccount.google.com/apppasswords）

未設定の場合は送信をスキップして警告ログのみ残す（投稿処理は失敗させない）。
"""
import logging
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)


def is_mail_configured() -> bool:
    """SMTP 設定が揃っているか"""
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def send_email(to_address: str, subject: str, body: str) -> bool:
    """テキストメールを送信する

    Returns:
        送信成功なら True。SMTP 未設定・送信失敗時は False（例外は投げない）
    """
    if not to_address:
        logger.warning("[Mailer] 宛先が空のため送信スキップ")
        return False
    if not is_mail_configured():
        logger.warning(
            "[Mailer] SMTP 未設定のため送信スキップ "
            "(.env に SMTP_HOST/SMTP_USER/SMTP_PASSWORD を設定してください) "
            f"宛先={to_address} 件名={subject}"
        )
        return False

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", user)

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((str(Header("Carroo 投稿システム", "utf-8")), mail_from))
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

        logger.info(f"[Mailer] メール送信成功: {to_address} 「{subject}」")
        return True
    except Exception as e:
        logger.error(f"[Mailer] メール送信失敗: {to_address} - {e}")
        return False
