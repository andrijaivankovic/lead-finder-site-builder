import argparse
import imaplib
import os
import re
import smtplib
import ssl
import sys
from datetime import date, datetime
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as email_policy
from email.utils import formataddr, formatdate, getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_search
import lead_store
import outreach_log

ROOT = lead_search.ROOT
PASSWORD_VARIABLE = "MAILBOX_PASSWORD"
FOLDERS = ["inbox", "sent"]
LIST_HEADERS = "FROM TO SUBJECT DATE MESSAGE-ID"
ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$')
UID = re.compile(rb"UID (\d+)")
FLAGS = re.compile(rb"FLAGS \(([^)]*)\)")
BLANK_LINES = re.compile(r"\n{3,}")
SEVEN_BIT_LINE = 900
BLOCK_TAGS = ["p", "div", "li", "tr", "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"]
IMAP_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class MailboxError(Exception):
    pass


def options(settings):
    chosen = dict(settings["mailbox"])
    preset = chosen["providers"].get(chosen.get("provider") or "")
    if preset is None:
        raise MailboxError("The mailbox provider {} is not one of: {}.".format(chosen.get("provider"), ", ".join(chosen["providers"])))
    chosen.update(preset)
    chosen["address"] = (chosen.get("address") or "").strip()
    return chosen


def provider_names(settings):
    return {key: preset["name"] for key, preset in settings["mailbox"]["providers"].items()}


def password(root=None):
    stored = dotenv_values(Path(root or ROOT) / ".env").get(PASSWORD_VARIABLE)
    return (stored or os.getenv(PASSWORD_VARIABLE) or "").strip()


def has_password(root=None):
    return bool(password(root))


def status(settings, root=None):
    chosen = options(settings)
    return {
        "address": chosen["address"],
        "provider": chosen["provider"],
        "provider_name": chosen["name"],
        "has_password": has_password(root),
        "ready": bool(chosen["address"]) and has_password(root),
        "daily_limit": chosen["daily_limit"],
    }


def _ready(settings, root=None):
    chosen = options(settings)
    if not chosen["address"]:
        raise MailboxError("No mailbox address yet. Type it under Mailbox on the Settings page.")
    secret = password(root)
    if not secret:
        raise MailboxError("{} is empty in .env. SETUP.md, section 6, shows where the password comes from.".format(PASSWORD_VARIABLE))
    return chosen, secret


def _quoted(folder):
    return '"{}"'.format(folder.replace("\\", "\\\\").replace('"', '\\"'))


def _check(reply, doing):
    kind, data = reply
    if kind != "OK":
        detail = b" ".join(part for part in data if isinstance(part, bytes)).decode("utf-8", "replace")
        raise MailboxError("The mailbox refused {}: {}".format(doing, detail or kind))
    return data


class Connection:
    def __init__(self, settings, root=None):
        self.options, self.secret = _ready(settings, root)
        self.imap = None

    def __enter__(self):
        chosen = self.options
        try:
            self.imap = imaplib.IMAP4_SSL(
                chosen["imap_host"], chosen["imap_port"], ssl_context=ssl.create_default_context(), timeout=chosen["timeout_seconds"]
            )
        except OSError as error:
            raise MailboxError("Could not reach {}: {}".format(chosen["imap_host"], error))
        try:
            self.imap.login(chosen["address"], self.secret)
        except imaplib.IMAP4.error as error:
            self.close()
            raise MailboxError(
                "{} refused the login for {}. Check the password in .env, and that IMAP access is switched on in "
                "the mailbox's settings. {}".format(chosen["imap_host"], chosen["address"], _plain(error))
            )
        return self

    def __exit__(self, *exception):
        self.close()

    def close(self):
        if self.imap is None:
            return
        try:
            self.imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
        self.imap = None

    def folder(self, key):
        if key == "inbox":
            return "INBOX"
        if key != "sent":
            raise MailboxError("The folder is inbox or sent, not {}.".format(key))
        for line in _check(self.imap.list(), "to list its folders"):
            found = LIST_LINE.match(line or b"")
            if found and b"\\sent" in found.group("flags").lower():
                return found.group("name").decode("utf-8", "replace").strip('"')
        return self.options["sent_folder"]

    def open(self, key, read_only=True):
        name = self.folder(key)
        _check(self.imap.select(_quoted(name), readonly=read_only), "to open {}".format(name))
        return name

    def uids(self, *criteria):
        found = _check(self.imap.uid("SEARCH", *criteria), "to search")
        return [int(number) for number in b" ".join(part for part in found if part).split()]

    def fetch(self, uids, parts):
        if not uids:
            return []
        wanted = ",".join(str(number) for number in uids)
        return _fetched(_check(self.imap.uid("FETCH", wanted, parts), "to fetch messages"))

    def sent_today(self):
        self.open("sent")
        return len(self.uids("SINCE", imap_date(date.today())))


def imap_date(day):
    return "{:02d}-{}-{}".format(day.day, IMAP_MONTHS[day.month - 1], day.year)


def _plain(error):
    text = error.args[0] if error.args else error
    return text.decode("utf-8", "replace") if isinstance(text, bytes) else str(text)


def _fetched(data):
    found = []
    for part in data:
        if isinstance(part, tuple):
            found.append({"meta": part[0], "body": part[1]})
        elif isinstance(part, bytes) and found:
            found[-1]["meta"] += part
    messages = []
    for item in found:
        uid = UID.search(item["meta"])
        flags = FLAGS.search(item["meta"])
        if uid:
            messages.append({"uid": int(uid.group(1)), "flags": flags.group(1).decode() if flags else "", "body": item["body"]})
    return messages


def _when(value):
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if moment is None:
        return ""
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment.isoformat(timespec="minutes")


def _people(value):
    return [{"name": name, "address": address.lower()} for name, address in getaddresses([str(value or "")]) if address]


def lead_addresses(root=None):
    known = {}
    folder = lead_store.data_dir(root or ROOT)
    for name in lead_store.list_files(root or ROOT):
        for row in lead_store.load_rows(folder / name):
            for address in re.split(r"[;,\s]+", row.get("email") or ""):
                if "@" in address:
                    known[address.strip().lower()] = {"place_id": row["place_id"], "name": row.get("name", "")}
    return known


def _lead_for(people, known):
    return next((known[person["address"]] for person in people if person["address"] in known), None)


def _summary(item, key, known):
    message = message_from_bytes(item["body"], policy=email_policy)
    senders, receivers = _people(message["From"]), _people(message["To"])
    other = receivers if key == "sent" else senders
    return {
        "uid": item["uid"],
        "from": senders[0] if senders else {"name": "", "address": ""},
        "to": receivers,
        "subject": str(message["Subject"] or ""),
        "date": _when(message["Date"]),
        "unread": "\\seen" not in item["flags"].lower(),
        "lead": _lead_for(other, known),
    }


def list_messages(settings, key="inbox", root=None):
    with Connection(settings, root) as mailbox:
        mailbox.open(key)
        newest = sorted(mailbox.uids("ALL"), reverse=True)[: mailbox.options["list_size"]]
        fetched = mailbox.fetch(newest, "(UID FLAGS BODY.PEEK[HEADER.FIELDS ({})])".format(LIST_HEADERS))
        sent_today = mailbox.sent_today()
    known = lead_addresses(root)
    found = sorted((_summary(item, key, known) for item in fetched), key=lambda entry: entry["uid"], reverse=True)
    return {"folder": key, "messages": found, "sent_today": sent_today, "daily_limit": mailbox.options["daily_limit"]}


def _tidy(content):
    lines = [line.rstrip() for line in content.replace("\r\n", "\n").split("\n")]
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _html_text(content):
    soup = BeautifulSoup(content, "html.parser")
    for hidden in soup(["script", "style", "head"]):
        hidden.decompose()
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(BLOCK_TAGS):
        block.append("\n")
    return soup.get_text()


def _text_of(message):
    plain = message.get_body(preferencelist=("plain",))
    text = _tidy(plain.get_content()) if plain is not None else ""
    if text:
        return text
    html = message.get_body(preferencelist=("html",))
    return _tidy(_html_text(html.get_content())) if html is not None else ""


def _attachments(message):
    return [part.get_filename() or "attachment" for part in message.iter_attachments()]


def read_message(settings, key, uid, root=None):
    with Connection(settings, root) as mailbox:
        mailbox.open(key, read_only=False)
        fetched = mailbox.fetch([uid], "(UID FLAGS BODY.PEEK[])")
        if not fetched:
            raise MailboxError("That message is no longer in the mailbox.")
        _check(mailbox.imap.uid("STORE", str(uid), "+FLAGS", "(\\Seen)"), "to mark the message as read")
    message = message_from_bytes(fetched[0]["body"], policy=email_policy)
    senders, receivers = _people(message["From"]), _people(message["To"])
    known = lead_addresses(root)
    return {
        "uid": uid,
        "folder": key,
        "from": senders[0] if senders else {"name": "", "address": ""},
        "to": receivers,
        "cc": _people(message["Cc"]),
        "subject": str(message["Subject"] or ""),
        "date": _when(message["Date"]),
        "message_id": str(message["Message-ID"] or "").strip(),
        "references": str(message["References"] or "").strip(),
        "text": _text_of(message),
        "attachments": _attachments(message),
        "lead": _lead_for(receivers if key == "sent" else senders, known),
    }


def _clean_send(to, subject, body):
    name, address = parseaddr(to or "")
    if not ADDRESS.match(address or "") or "," in (to or ""):
        raise MailboxError("Send to one address, such as owner@example.com, not {}.".format(to or "nothing"))
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        raise MailboxError("The message needs a subject.")
    if not body:
        raise MailboxError("The message is empty.")
    if "\n" in subject or "\r" in subject:
        raise MailboxError("The subject has to be one line.")
    return address, subject, body


def _smtp(chosen):
    return smtplib.SMTP_SSL(
        chosen["smtp_host"], chosen["smtp_port"], timeout=chosen["timeout_seconds"], context=ssl.create_default_context()
    )


def compose(chosen, sender_name, address, subject, body, reply=None):
    message = EmailMessage()
    message["From"] = formataddr((sender_name, chosen["address"])) if sender_name else chosen["address"]
    message["To"] = address
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=chosen["address"].split("@")[-1])
    if reply and reply.get("message_id"):
        message["In-Reply-To"] = reply["message_id"]
        message["References"] = " ".join(part for part in (reply.get("references", ""), reply["message_id"]) if part)
    plain = body.isascii() and all(len(line) <= SEVEN_BIT_LINE for line in body.splitlines())
    message.set_content(body, cte="7bit" if plain else "quoted-printable")
    return message


def _log_send(place_id, name, address, settings, root):
    if not place_id:
        return ""
    earlier = [row for row in outreach_log.load(root) if row["place_id"] == place_id and row["channel"] == "email"]
    if earlier:
        outreach_log.record_follow_up(root, place_id, "email")
        return "follow_up"
    name = name or (lead_addresses(root).get(address) or {}).get("name") or place_id
    outreach_log.record_send(root, place_id, name, "email", settings)
    return "first"


def send(settings, to, subject, body, place_id="", name="", reply=None, root=None):
    root = root or ROOT
    address, subject, body = _clean_send(to, subject, body)
    chosen, secret = _ready(settings, root)
    if not reply:
        with Connection(settings, root) as mailbox:
            already = mailbox.sent_today()
        if already >= chosen["daily_limit"]:
            raise MailboxError(
                "{} messages already went out today, and the limit is {} while the mailbox warms up. Raise it under "
                "Mailbox on the Settings page when the week's plan allows.".format(already, chosen["daily_limit"])
            )
    message = compose(chosen, settings["outreach"].get("sender_name") or "", address, subject, body, reply)
    try:
        with _smtp(chosen) as server:
            server.login(chosen["address"], secret)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise MailboxError("{} refused the login for {}. Check the password in .env.".format(chosen["smtp_host"], chosen["address"]))
    except smtplib.SMTPRecipientsRefused:
        raise MailboxError("{} refused the address {}.".format(chosen["smtp_host"], address))
    except (smtplib.SMTPException, OSError) as error:
        raise MailboxError("Sending through {} failed: {}".format(chosen["smtp_host"], error))
    logged = "" if reply else _log_send(place_id, name, address, settings, root)
    return {"sent_at": datetime.now().isoformat(timespec="seconds"), "to": address, "logged": logged}


def check(settings, root=None):
    chosen, secret = _ready(settings, root)
    with Connection(settings, root) as mailbox:
        mailbox.open("inbox")
        inbox = len(mailbox.uids("ALL"))
        sent_folder = mailbox.folder("sent")
    try:
        with _smtp(chosen) as server:
            server.login(chosen["address"], secret)
    except smtplib.SMTPAuthenticationError:
        raise MailboxError("Reading works, but {} refused the login for sending.".format(chosen["smtp_host"]))
    except (smtplib.SMTPException, OSError) as error:
        raise MailboxError("Reading works, but {} could not be reached for sending: {}".format(chosen["smtp_host"], error))
    return {"address": chosen["address"], "inbox": inbox, "sent_folder": sent_folder}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Reads and sends mail through your own mailbox.")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("check", help="Log in to read and to send, and say whether both work")
    list_command = commands.add_parser("list", help="List the newest messages")
    list_command.add_argument("--sent", action="store_true", help="The Sent folder instead of the inbox")
    arguments = parser.parse_args()

    settings = lead_search.load_settings()
    try:
        if arguments.action == "check":
            result = check(settings)
            print("\nReading and sending both work for {}. {} messages in the inbox, sent mail in {}.\n".format(
                result["address"], result["inbox"], result["sent_folder"]
            ))
        else:
            found = list_messages(settings, "sent" if arguments.sent else "inbox")
            print()
            for item in found["messages"]:
                person = item["to"][0] if arguments.sent and item["to"] else item["from"]
                print("{}{}  {}  {}".format("* " if item["unread"] else "  ", item["date"], person["address"], item["subject"]))
            print("\n{} of {} sent today.\n".format(found["sent_today"], found["daily_limit"]))
    except MailboxError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
