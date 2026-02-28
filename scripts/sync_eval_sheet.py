#!/usr/bin/env python3
import argparse
import csv
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def norm_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def parse_sheet(sheet_path: Path):
    rows = list(csv.reader(sheet_path.open("r", encoding="utf-8-sig", newline="")))
    header_index = None
    for i, row in enumerate(rows):
        lowered = [norm_header(cell) for cell in row]
        if "members" in lowered and "q (gu)" in lowered:
            header_index = i
            break
    if header_index is None:
        raise RuntimeError("Could not find header row containing Members and Q (Gu).")

    header = rows[header_index]
    index_map = {norm_header(name): idx for idx, name in enumerate(header)}
    members_idx = index_map["members"]
    q_gu_idx = index_map["q (gu)"]
    q_en_idx = index_map.get("q (en)")
    category_idx = index_map.get("category")
    fb_q_idx = index_map.get("fb q -for col d")
    fb_search_idx = index_map.get("fb search col e")
    fb_a_idx = index_map.get("fb a col g")

    # Fallback names if sheet headers are changed later.
    if fb_q_idx is None:
        fb_q_idx = index_map.get("feedback q")
    if fb_search_idx is None:
        fb_search_idx = index_map.get("feedback search")
    if fb_a_idx is None:
        fb_a_idx = index_map.get("feedback a")

    entries = []
    unique_emails = set()
    for row in rows[header_index + 1 :]:
        if not row:
            continue
        q_gu = row[q_gu_idx].strip() if q_gu_idx < len(row) else ""
        if not q_gu:
            continue
        category = row[category_idx].strip() if category_idx is not None and category_idx < len(row) else ""
        q_en = row[q_en_idx].strip() if q_en_idx is not None and q_en_idx < len(row) else ""
        members_raw = row[members_idx].strip() if members_idx < len(row) else ""
        fb_q = row[fb_q_idx].strip() if fb_q_idx is not None and fb_q_idx < len(row) else ""
        fb_search = row[fb_search_idx].strip() if fb_search_idx is not None and fb_search_idx < len(row) else ""
        fb_a = row[fb_a_idx].strip() if fb_a_idx is not None and fb_a_idx < len(row) else ""
        members = []
        for part in members_raw.replace(";", ",").split(","):
            email = part.strip().lower().lstrip("@")
            if email and "@" in email:
                members.append(email)
                unique_emails.add(email)
        entries.append(
            {
                "category": category,
                "q_gu": q_gu,
                "q_en": q_en,
                "members": members,
                "feedback_q": fb_q,
                "feedback_search": fb_search,
                "feedback_a": fb_a,
            }
        )
    return entries, sorted(unique_emails)


def build_question_index(conn: sqlite3.Connection):
    rows = conn.execute("SELECT id, category, q_gu, q_en FROM questions").fetchall()
    by_exact = {}
    by_q_gu = {}
    by_q_gu_norm = {}
    for row in rows:
        qid = row["id"]
        category = (row["category"] or "").strip()
        q_gu = (row["q_gu"] or "").strip()
        q_en = (row["q_en"] or "").strip()
        by_exact[(category, q_gu, q_en)] = qid
        by_q_gu.setdefault(q_gu, []).append(qid)
        by_q_gu_norm.setdefault(norm_text(q_gu), []).append(qid)
    return by_exact, by_q_gu, by_q_gu_norm


def map_entries_to_questions(entries, by_exact, by_q_gu, by_q_gu_norm):
    mapped_pairs = []
    unmapped_entries = []
    ambiguous_entries = []

    for item in entries:
        qid = by_exact.get((item["category"], item["q_gu"], item["q_en"]))
        if qid is None:
            exact_q_gu_matches = by_q_gu.get(item["q_gu"], [])
            if len(exact_q_gu_matches) == 1:
                qid = exact_q_gu_matches[0]
            elif len(exact_q_gu_matches) > 1:
                ambiguous_entries.append(item)
                continue
            else:
                normalized_matches = by_q_gu_norm.get(norm_text(item["q_gu"]), [])
                if len(normalized_matches) == 1:
                    qid = normalized_matches[0]
                elif len(normalized_matches) > 1:
                    ambiguous_entries.append(item)
                    continue
        if qid is None:
            unmapped_entries.append(item)
            continue
        mapped_pairs.append(
            (
                qid,
                item["members"],
                {
                    "q_translation_comment": item.get("feedback_q", ""),
                    "search_comment": item.get("feedback_search", ""),
                    "answer_comment": item.get("feedback_a", ""),
                },
            )
        )
    return mapped_pairs, unmapped_entries, ambiguous_entries


def apply_sync(
    conn: sqlite3.Connection,
    mapped_pairs,
    allowed_emails,
):
    conn.execute("BEGIN")
    try:
        # Remove test users and defaults not present in sheet list.
        if allowed_emails:
            placeholders = ",".join("?" for _ in allowed_emails)
            disallowed_users = conn.execute(
                f"SELECT id FROM users WHERE lower(email) NOT IN ({placeholders})",
                allowed_emails,
            ).fetchall()
            disallowed_ids = [row["id"] for row in disallowed_users]
            if disallowed_ids:
                placeholders = ",".join("?" for _ in disallowed_ids)
                conn.execute(f"DELETE FROM feedback WHERE user_id IN ({placeholders})", disallowed_ids)
                conn.execute(f"DELETE FROM assignments WHERE user_id IN ({placeholders})", disallowed_ids)
                conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", disallowed_ids)

        # Remove known local test questions inserted during development.
        conn.execute("DELETE FROM assignments WHERE question_id IN (SELECT id FROM questions WHERE category IN ('CatX','CatZ'))")
        conn.execute("DELETE FROM feedback WHERE question_id IN (SELECT id FROM questions WHERE category IN ('CatX','CatZ'))")
        conn.execute("DELETE FROM questions WHERE category IN ('CatX','CatZ')")

        # Ensure sheet users exist.
        for email in allowed_emails:
            conn.execute(
                "INSERT OR IGNORE INTO users (email, is_admin) VALUES (?, 0)",
                (email,),
            )

        # Rebuild assignments from sheet mappings.
        conn.execute("DELETE FROM assignments")
        for question_id, members, feedback in mapped_pairs:
            for email in sorted(set(members)):
                user = conn.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()
                if user:
                    conn.execute(
                        "INSERT OR IGNORE INTO assignments (user_id, question_id) VALUES (?, ?)",
                        (user["id"], question_id),
                    )
                    if (
                        feedback.get("q_translation_comment")
                        or feedback.get("search_comment")
                        or feedback.get("answer_comment")
                    ):
                        now = datetime.utcnow().isoformat()
                        conn.execute(
                            """
                            INSERT INTO feedback (
                                user_id, question_id, submission_status,
                                q_translation_rating, q_translation_comment,
                                search_rating, search_issue_type, search_comment,
                                answer_accuracy_rating, answer_translation_rating, answer_comment,
                                created_at, updated_at
                            )
                            VALUES (?, ?, 'submitted', NULL, ?, NULL, NULL, ?, NULL, NULL, ?, ?, ?)
                            ON CONFLICT(user_id, question_id) DO UPDATE SET
                                submission_status='submitted',
                                q_translation_comment=excluded.q_translation_comment,
                                search_comment=excluded.search_comment,
                                answer_comment=excluded.answer_comment,
                                updated_at=excluded.updated_at
                            """,
                            (
                                user["id"],
                                question_id,
                                feedback.get("q_translation_comment", ""),
                                feedback.get("search_comment", ""),
                                feedback.get("answer_comment", ""),
                                now,
                                now,
                            ),
                        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description="Sync users and assignments from Amul Eval Sheet.")
    parser.add_argument("--db", default="app.db", help="Path to sqlite DB")
    parser.add_argument(
        "--sheet",
        default="data/Sheets/Amul Eval Sheet.csv",
        help="Path to eval sheet CSV",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    args = parser.parse_args()

    db_path = Path(args.db)
    sheet_path = Path(args.sheet)
    entries, unique_emails = parse_sheet(sheet_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    by_exact, by_q_gu, by_q_gu_norm = build_question_index(conn)
    mapped_pairs, unmapped_entries, ambiguous_entries = map_entries_to_questions(
        entries, by_exact, by_q_gu, by_q_gu_norm
    )

    print(f"sheet_rows={len(entries)}")
    print(f"unique_sheet_emails={len(unique_emails)}")
    print(f"mapped_rows={len(mapped_pairs)}")
    print(f"unmapped_rows={len(unmapped_entries)}")
    print(f"ambiguous_rows={len(ambiguous_entries)}")
    if unmapped_entries:
        print("first_unmapped_q_gu:")
        for item in unmapped_entries[:5]:
            print(f" - {item['q_gu']}")
    if ambiguous_entries:
        print("first_ambiguous_q_gu:")
        for item in ambiguous_entries[:5]:
            print(f" - {item['q_gu']}")

    if args.apply:
        apply_sync(
            conn=conn,
            mapped_pairs=mapped_pairs,
            allowed_emails=[e.lower() for e in unique_emails],
        )
        users_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        assignments_count = conn.execute("SELECT COUNT(*) AS c FROM assignments").fetchone()["c"]
        print(f"applied=1 users={users_count} assignments={assignments_count}")
    else:
        print("applied=0 (dry-run)")

    conn.close()


if __name__ == "__main__":
    main()
