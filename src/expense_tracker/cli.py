"""Presentation layer: command-line interface built with argparse."""
import argparse
import sys
from datetime import date

from . import __version__
from .database import connect
from .models import ValidationError, format_money, parse_month
from .service import ExpenseService


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="expense-tracker", description="Track personal expenses.")
    p.add_argument("--db", default="expenses.db", help="path to the SQLite database file")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add an expense")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("-d", "--date", default=date.today().isoformat())
    a.add_argument("-n", "--note", default="")

    l = sub.add_parser("list", help="list expenses")
    l.add_argument("-c", "--category")
    l.add_argument("--start")
    l.add_argument("--end")

    u = sub.add_parser("update", help="update an expense")
    u.add_argument("id", type=int)
    u.add_argument("--amount")
    u.add_argument("--category")
    u.add_argument("--date")
    u.add_argument("--note")

    d = sub.add_parser("delete", help="delete an expense")
    d.add_argument("id", type=int)

    s = sub.add_parser("summary", help="totals per category")
    s.add_argument("--start")
    s.add_argument("--end")

    b = sub.add_parser("budget", help="set a monthly budget for a category")
    b.add_argument("category")
    b.add_argument("limit")

    st = sub.add_parser("status", help="show budget status for a month")
    st.add_argument("--month", default=date.today().strftime("%Y-%m"), help="YYYY-MM")

    e = sub.add_parser("export", help="export all expenses to CSV")
    e.add_argument("path")
    return p


def run(argv=None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    conn = connect(args.db)
    svc = ExpenseService(conn)
    try:
        if args.command == "add":
            e = svc.add_expense(args.amount, args.category, args.date, args.note)
            print(f"Added #{e.id}: {format_money(e.amount_cents)} on {e.category} ({e.spent_on})", file=out)
        elif args.command == "list":
            rows = svc.list_expenses(args.category, args.start, args.end)
            if not rows:
                print("No expenses found.", file=out)
            for e in rows:
                print(f"#{e.id:<3} {e.spent_on}  {e.category:<12} {format_money(e.amount_cents):>10}  {e.description}", file=out)
        elif args.command == "update":
            e = svc.update_expense(args.id, args.amount, args.category, args.date, args.note)
            print(f"Updated #{e.id}", file=out)
        elif args.command == "delete":
            svc.delete_expense(args.id)
            print(f"Deleted #{args.id}", file=out)
        elif args.command == "summary":
            totals = svc.total_by_category(args.start, args.end)
            for cat, total in totals.items():
                print(f"{cat:<12} {format_money(total):>10}", file=out)
            print(f"{'TOTAL':<12} {format_money(sum(totals.values())):>10}", file=out)
        elif args.command == "budget":
            svc.set_budget(args.category, args.limit)
            print(f"Budget for {args.category.strip().lower()} set to {args.limit}", file=out)
        elif args.command == "status":
            year, month = parse_month(args.month)
            for row in svc.budget_status(year, month):
                flag = "OVER BUDGET" if row["over"] else "ok"
                print(f"{row['category']:<12} {format_money(row['spent']):>10} / {format_money(row['limit']):>10}  {flag}", file=out)
        elif args.command == "export":
            n = svc.export_csv(args.path)
            print(f"Exported {n} expenses to {args.path}", file=out)
        return 0
    except (ValidationError, KeyError) as exc:
        print(f"Error: {exc.args[0]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: file problem - {exc.strerror or exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def main():
    sys.exit(run())
