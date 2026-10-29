"""Operations helpers: consistent database backups, restore, retention and integrity check.

Usage:
  python -m expense_tracker.ops backup  --db /data/expenses.db --dest /data/backups --keep 7
  python -m expense_tracker.ops restore --db /data/expenses.db --from /data/backups/expenses-....db
  python -m expense_tracker.ops check   --db /data/expenses.db
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime


def backup(db_path: str, dest_dir: str, keep: int = 7, now: datetime = None) -> str:
    """Create a consistent snapshot using SQLite's online backup API (safe while the app is running)."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    os.makedirs(dest_dir, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = os.path.join(dest_dir, f"expenses-{stamp}.db")
    src, dst = sqlite3.connect(db_path), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if not integrity_ok(target):
        os.remove(target)
        raise RuntimeError("Backup failed integrity check and was removed")
    prune(dest_dir, keep)
    return target


def prune(dest_dir: str, keep: int) -> list:
    """Keep only the newest `keep` backups; return the names removed."""
    files = sorted(f for f in os.listdir(dest_dir) if f.startswith("expenses-") and f.endswith(".db"))
    old = files[:-keep] if keep > 0 else files
    for name in old:
        os.remove(os.path.join(dest_dir, name))
    return old


def integrity_ok(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def restore(db_path: str, backup_path: str) -> str:
    """Restore a backup. The current database is first saved as <db>.before-restore."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    if not integrity_ok(backup_path):
        raise RuntimeError("Backup file is corrupt; refusing to restore")
    safety = db_path + ".before-restore"
    if os.path.exists(db_path):
        shutil.copy2(db_path, safety)
    for suffix in ("-wal", "-shm"):  # stale write-ahead files would corrupt the restored copy
        if os.path.exists(db_path + suffix):
            os.remove(db_path + suffix)
    shutil.copy2(backup_path, db_path)
    return safety


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="expense_tracker.ops")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--db", required=True)
    b.add_argument("--dest", required=True)
    b.add_argument("--keep", type=int, default=7)
    r = sub.add_parser("restore")
    r.add_argument("--db", required=True)
    r.add_argument("--from", dest="source", required=True)
    c = sub.add_parser("check")
    c.add_argument("--db", required=True)
    args = p.parse_args(argv)
    try:
        if args.cmd == "backup":
            print(f"Backup created: {backup(args.db, args.dest, args.keep)}")
        elif args.cmd == "restore":
            print(f"Restored. Previous database saved as {restore(args.db, args.source)}")
        else:
            ok = integrity_ok(args.db)
            print("Integrity check:", "OK" if ok else "FAILED")
            return 0 if ok else 1
        return 0
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
