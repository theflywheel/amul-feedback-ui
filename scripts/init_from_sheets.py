#!/usr/bin/env python3
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from scripts.sync_eval_sheet import (
    apply_sync,
    build_question_index,
    map_entries_to_questions,
    parse_sheet,
)


def upsert_questions(conn: sqlite3.Connection, golden_csv_path: Path):
    seen_ids = set()
    with golden_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("Category") or "").strip()
            q_gu = (row.get("Q (Gu)") or "").strip()
            q_en = (row.get("Q (En)") or "").strip()
            search_results = row.get("Search Results") or ""
            a_en = row.get("A(En)") or ""
            a_gu = row.get("A (Gu)") or ""
            if not q_gu:
                continue
            conn.execute(
                """
                INSERT INTO questions (category, q_gu, q_en, search_results, a_en, a_gu, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(category, q_gu, q_en) DO UPDATE SET
                  search_results=excluded.search_results,
                  a_en=excluded.a_en,
                  a_gu=excluded.a_gu,
                  active=1
                """,
                (category, q_gu, q_en, search_results, a_en, a_gu),
            )
            found = conn.execute(
                "SELECT id FROM questions WHERE category=? AND q_gu=? AND q_en=?",
                (category, q_gu, q_en),
            ).fetchone()
            if found:
                seen_ids.add(found["id"])
    return seen_ids


def main():
    parser = argparse.ArgumentParser(
        description="Initialize data from golden sheet + eval sheet mapping."
    )
    parser.add_argument("--db", default="app.db", help="Path to sqlite DB")
    parser.add_argument(
        "--golden-sheet",
        default="data/Sheets/500_goldenset_final_sheet.csv",
        help="Path to golden set questions CSV",
    )
    parser.add_argument(
        "--eval-sheet",
        default="data/Sheets/Amul Eval Sheet.csv",
        help="Path to eval sheet CSV containing Members mappings",
    )
    parser.add_argument(
        "--sync-active",
        action="store_true",
        help="Deactivate questions not present in golden sheet",
    )
    args = parser.parse_args()

    db_path = (ROOT_DIR / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)
    golden_path = (
        (ROOT_DIR / args.golden_sheet).resolve()
        if not Path(args.golden_sheet).is_absolute()
        else Path(args.golden_sheet)
    )
    eval_path = (
        (ROOT_DIR / args.eval_sheet).resolve()
        if not Path(args.eval_sheet).is_absolute()
        else Path(args.eval_sheet)
    )

    # Trigger app DB init/migrations once.
    with app.test_client() as client:
        client.get("/annotator/login")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN")
    try:
        seen_question_ids = upsert_questions(conn, golden_path)
        if args.sync_active:
            if seen_question_ids:
                placeholders = ",".join("?" for _ in seen_question_ids)
                conn.execute(
                    f"UPDATE questions SET active=0 WHERE id NOT IN ({placeholders})",
                    tuple(seen_question_ids),
                )
            else:
                conn.execute("UPDATE questions SET active=0")
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    entries, unique_emails = parse_sheet(eval_path)
    by_exact, by_q_gu, by_q_gu_norm = build_question_index(conn)
    mapped_pairs, unmapped_entries, ambiguous_entries = map_entries_to_questions(
        entries, by_exact, by_q_gu, by_q_gu_norm
    )

    print(f"golden_unique_questions_upserted={len(seen_question_ids)}")
    print(f"eval_sheet_rows={len(entries)}")
    print(f"unique_sheet_emails={len(unique_emails)}")
    print(f"mapped_rows={len(mapped_pairs)}")
    print(f"unmapped_rows={len(unmapped_entries)}")
    print(f"ambiguous_rows={len(ambiguous_entries)}")

    apply_sync(
        conn=conn,
        mapped_pairs=mapped_pairs,
        allowed_emails=[e.lower() for e in unique_emails],
    )

    users_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    assignments_count = conn.execute("SELECT COUNT(*) AS c FROM assignments").fetchone()["c"]
    active_questions = conn.execute("SELECT COUNT(*) AS c FROM questions WHERE active=1").fetchone()["c"]
    conn.close()
    print(f"applied=1 users={users_count} assignments={assignments_count} active_questions={active_questions}")


if __name__ == "__main__":
    main()
