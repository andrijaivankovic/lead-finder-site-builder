import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_brief
import lead_search
import outreach_log

ROOT = lead_search.ROOT


def _print_due(rows):
    if not rows:
        print("\nNobody is waiting on a follow up.\n")
        return

    print("\nDue for a follow up:\n")
    for row in rows:
        print(
            "  {:<28} {:<10} sent {}  ({} days ago)".format(
                row["name"][:28], row["channel"], row["sent_at"], row["days_waiting"]
            )
        )
    print()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Keeps the record of who was contacted, when and through what.")
    parser.add_argument("--due", action="store_true", help="List who is waiting on a follow up")
    parser.add_argument("--sent", help="Record a message as sent, takes a place_id")
    parser.add_argument("--channel", help="email, viber or instagram")
    parser.add_argument("--answered", help="Record a reply, takes a place_id")
    parser.add_argument("--response", help="interested, declined or 'no answer'")
    parser.add_argument("--notes", default="", help="Anything worth remembering")
    arguments = parser.parse_args()

    try:
        settings = lead_search.load_settings()

        if arguments.sent:
            if not arguments.channel:
                raise outreach_log.OutreachError("--sent needs --channel as well.")
            lead, _ = build_brief.find_lead(arguments.sent)
            row = outreach_log.record_send(
                ROOT, arguments.sent, lead["name"], arguments.channel, settings, notes=arguments.notes
            )
            print("\nLogged: {} over {} on {}. Follow up due {}.\n".format(
                row["name"], row["channel"], row["sent_at"], row["follow_up_due"]
            ))
            return

        if arguments.answered:
            if not arguments.response:
                raise outreach_log.OutreachError("--answered needs --response as well.")
            touched = outreach_log.record_response(ROOT, arguments.answered, arguments.response, arguments.notes)
            print("\nRecorded '{}' for {}.\n".format(arguments.response, touched[0]["name"]))
            return

        counts = outreach_log.summary(ROOT)
        print("\nContacted {} businesses. Awaiting {}, interested {}, declined {}.".format(
            counts["total"], counts["awaiting"], counts["interested"], counts["declined"]
        ))
        _print_due(outreach_log.due_for_follow_up(ROOT))

    except (outreach_log.OutreachError, build_brief.BriefError) as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
