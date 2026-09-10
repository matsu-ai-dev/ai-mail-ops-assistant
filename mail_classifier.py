import os
import imaplib
import email

from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from email.header import decode_header
from imapclient.imap_utf7 import decode as decode_utf7
from imapclient.imap_utf7 import encode as encode_utf7

DRY_RUN = True
LIMIT = 3

def get_latest_mail(imap):
    imap.select("INBOX", readonly=False)

    status, messages = imap.uid("SEARCH", None, "ALL")
    mail_uids = messages[0].split()

    print(f"全メール件数:{len(mail_uids)}")
    print(mail_uids[-3:])

    latest_uid = mail_uids[-1]
    print("最新UID:", latest_uid)

    status, msg_data = imap.uid(
        "FETCH",
        latest_uid,
        "(RFC822)"
    )

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    return latest_uid, msg

def get_mail_body(msg):
    body = ""

    for part in msg.walk():

        if part.get_content_type() == "text/plain":

            print("本文発見")

            raw_body = part.get_payload(decode=True)

            if raw_body is not None:

                charset = part.get_content_charset()

                print("メールに書かれていた文字コード:", charset)

                if charset is None:
                    charset = "iso-2022-jp"

                try:
                    body = raw_body.decode(charset)
                except UnicodeDecodeError:
                    body = raw_body.decode("iso-2022-jp", errors="ignore")

                return body

    return body


def get_seen_uids(imap, limit=3):
    imap.select("INBOX", readonly=False)

    status, messages = imap.uid("SEARCH", None, "SEEN")

    mail_uids = messages[0].split()

    print(f"既読メール件数: {len(mail_uids)}")
    print("処理対象UID:", mail_uids[-limit:])

    return mail_uids[-limit:]


def get_mail_by_uid(imap, mail_uid):
    status, msg_data = imap.uid(
        "FETCH",
        mail_uid,
        "(RFC822)"
    )

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    return msg


def decode_mail_header(header_text):
    decoded_text, encoding = decode_header(header_text)[0]

    if isinstance(decoded_text, bytes):
        decoded_text = decoded_text.decode(
            encoding or "utf-8"
        )

    return decoded_text

def ask_ai(client, decoded_subject, decoded_from, body):
    content = f"""
以下のYahooメールを整理してください。

出力形式：
差出人：
読み価値：
要約：
やること：
期限：
重要度：
捨ててよい可能性：
削除推奨：
分類：
フォルダ候補：
理由：

フォルダ候補は以下から選んでください。
UI銀行
会社
大切
投資
旅行
済み
直近
通知不要なメール

ルール：
転職関連メールは「直近」
投資関連メールは「投資」
旅行関連メールは「旅行」
銀行関連メールは「UI銀行」
不要な広告やクーポンは「通知不要なメール」

読み価値は
高
中
低
のいずれかで回答してください。

件名：
{decoded_subject}

差出人：
{decoded_from}

本文：
{body[:1000]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": content
            }
        ]
    )

    response_text = response.choices[0].message.content

    return response_text

def extract_folder(response_text):
    lines = response_text.split("\n")

    folder = None

    for i, line in enumerate(lines):

        if "フォルダ候補：" in line:

            folder = line.split("フォルダ候補：", 1)[1].strip()

            if folder == "":
                if i + 1 >= len(lines):
                    return None
                folder = lines[i + 1].strip()

            folder = folder.replace("　", " ").strip()

            print("抽出したフォルダ候補：")
            print(folder)

            break

    return folder or None

def find_yahoo_folder(imap, folder):
    status, folders = imap.list()

    folder_exists = False
    move_folder_name = None

    for yahoo_folder in folders:

        folder_text = yahoo_folder.decode()
        folder_name = folder_text.split('"')[-2]

        decoded_folder_name = decode_utf7(
            folder_name.encode("ascii")
        )

        print("確認中:", decoded_folder_name)

        if decoded_folder_name == folder:
            folder_exists = True
            move_folder_name = folder_name
            print("一致しました:", decoded_folder_name)
            break

    print("フォルダ存在確認:", folder_exists)
    print("IMAP用フォルダ名:", move_folder_name)

    return folder_exists, move_folder_name

def move_mail(imap, mail_uid, folder, move_folder_name):
    print("移動予定")
    print("メールUID:", mail_uid)
    print("移動先:", folder)
    print("IMAP用移動先:", move_folder_name)

    # 移動前確認
    status, before_check = imap.uid(
        "SEARCH",
        None,
        f"UID {mail_uid.decode()}"
    )

    print("移動前INBOX確認:", before_check)

    result = imap.uid(
        "MOVE",
        mail_uid,
        move_folder_name
    )

    print("UID MOVE結果:", result)

    # 移動後確認
    status, after_check = imap.uid(
        "SEARCH",
        None,
        f"UID {mail_uid.decode()}"
    )

    print("移動後INBOX確認:", after_check)

    if result[0] == "OK" and after_check[0] == b"":
        print("移動完了：INBOXから消えました")
        return True

    elif result[0] == "OK":
        print("MOVEはOKですが、INBOXに残っている可能性があります")
        return False

    else:
        print("UID MOVEに失敗しました")
        return False

def write_log(
    mail_uid,
    decoded_subject,
    decoded_from,
    folder,
    moved,
    move_result,
    process_mode,
    move_reason
):
    import csv
    import os

    file_path = "mail_sort_log_v3.csv"

    file_exists = os.path.exists(file_path)
    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(mail_uid, bytes):
        uid_text = mail_uid.decode()
    else:
        uid_text = str(mail_uid)

    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "処理日時",
                "UID",
                "件名",
                "差出人",
                "分類予定フォルダ",
                "移動したか",
                "移動結果",
                "処理モード",
                "移動理由"
            ])

        writer.writerow([
            processed_at,
            uid_text,
            decoded_subject,
            decoded_from,
            folder,
            moved,
            move_result,
            process_mode,
            move_reason
        ])

def process_one_mail(imap, client):
    latest_uid, msg = get_latest_mail(imap)

    subject = msg["Subject"]
    decoded_subject = decode_mail_header(subject)

    print(decoded_subject)

    from_name = msg["From"]
    decoded_from = decode_mail_header(from_name)

    print(decoded_from)

    print(msg["Date"])

    if msg.is_multipart():
        print("添付やHTMLあり")

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            print(content_type)
    else:
        print(msg.get_content_type())

    body = get_mail_body(msg)

    print(body[:1000])

    response_text = ask_ai(
        client,
        decoded_subject,
        decoded_from,
        body
    )

    print(response_text)

    folder = extract_folder(response_text)

    folder_exists, move_folder_name = find_yahoo_folder(
        imap,
        folder
    )

    if folder_exists:
        if DRY_RUN:
            print("DRY_RUN=True のため、process_one_mail では移動しません")
            return False

        move_success = move_mail(
            imap,
            latest_uid,
            folder,
            move_folder_name
        )

        return move_success

    else:
        print("移動先フォルダが見つからないため、移動しません")
        return False

def main():
    load_dotenv()

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    import imaplib

    imap = imaplib.IMAP4_SSL(
        "imap.mail.yahoo.co.jp"
    )

    print("接続成功")

    mail_address = os.getenv("YAHOO_MAIL_ADDRESS")
    app_password = os.getenv("YAHOO_APP_PASSWORD")

    imap.login(
        mail_address,
        app_password
    )

    print("ログイン成功")

    seen_uids = get_seen_uids(imap, limit=LIMIT)

    for uid in seen_uids:
        try:
            print("==============================")
            print("確認UID:", uid)
            print("==============================")

            msg = get_mail_by_uid(imap, uid)

            subject = msg["Subject"]
            decoded_subject = decode_mail_header(subject)

            from_name = msg["From"]
            decoded_from = decode_mail_header(from_name)

            print("件名:", decoded_subject)
            print("差出人:", decoded_from)

            body = get_mail_body(msg)

            response_text = ask_ai(
                client,
                decoded_subject,
                decoded_from,
                body
            )

            print(response_text)

            folder = extract_folder(response_text)

            print("分類予定フォルダ:", folder)

            if folder == "通知不要なメール":
                if DRY_RUN:
                    print("通知不要判定ですが、DRY_RUN=True のため移動しません")

                    write_log(
                        uid,
                        decoded_subject,
                        decoded_from,
                        folder,
                        "いいえ",
                        "dry-run",
                        "dry-run",
                        "通知不要判定だが、安全確認のため未移動"
                    )

                    continue

                print("通知不要なメールなので、実際に移動します")

                folder_exists, move_folder_name = find_yahoo_folder(
                    imap,
                    folder
                )

                if folder_exists:
                    move_success = move_mail(
                        imap,
                        uid,
                        folder,
                        move_folder_name
                    )

                    print("移動結果:", move_success)

                    write_log(
                        uid,
                        decoded_subject,
                        decoded_from,
                        folder,
                        "はい",
                        "成功" if move_success else "失敗",
                        "実移動",
                        "通知不要判定のため移動"
                    )

                else:
                    print("移動先フォルダが見つからないため、移動しません")

                    write_log(
                        uid,
                        decoded_subject,
                        decoded_from,
                        folder,
                        "いいえ",
                        "フォルダなし",
                        "実移動",
                        "移動先フォルダが見つからないため未移動"
                    )

            else:
                print("通知不要なメール以外なので、今回は移動しません")

                write_log(
                    uid,
                    decoded_subject,
                    decoded_from,
                    folder,
                    "いいえ",
                    "未移動",
                    "判定のみ",
                    "通知不要なメール以外のため未移動"
                )

        except Exception as e:
            print("メール処理中にエラーが発生しました:", e)

            write_log(
                uid,
                "取得失敗",
                "取得失敗",
                "不明",
                "いいえ",
                "エラー",
                "エラー",
                str(e)
            )


if __name__ == "__main__":
    main()
