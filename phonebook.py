import sys
from pathlib import Path

import psycopg2
from psycopg2 import errors as pg_errors

from connect import connect_db


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _statement_has_sql_text(stmt: str) -> bool:
    for line in stmt.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        return True
    return False


def _split_sql_statements(sql: str):
    """
    Split a PostgreSQL script into executable statements, respecting dollar-quoting.
    """
    result = []
    buf = []
    i = 0
    n = len(sql)

    def flush():
        nonlocal buf
        stmt = "".join(buf).strip()
        buf = []
        return stmt

    while i < n:
        if sql[i] == "$":
            j = i + 1
            while j < n and sql[j] != "$":
                j += 1
            if j >= n:
                buf.append(sql[i:])
                break
            tag = sql[i + 1 : j]
            buf.append(sql[i : j + 1])
            i = j + 1
            close = "$" + tag + "$"
            k = sql.find(close, i)
            if k == -1:
                buf.append(sql[i:])
                break
            buf.append(sql[i : k + len(close)])
            i = k + len(close)
            continue

        if sql[i] == ";":
            stmt = flush()
            if stmt and _statement_has_sql_text(stmt):
                result.append(stmt)
            i += 1
            continue

        buf.append(sql[i])
        i += 1

    stmt = flush()
    if stmt and _statement_has_sql_text(stmt):
        result.append(stmt)
    return result


def apply_sql_files(conn):
    """
    Apply bundled SQL in dependency order (functions before procedures).
    """
    paths = [
        _script_dir() / "functions.sql",
        _script_dir() / "procedures.sql",
    ]
    with conn.cursor() as cur:
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f"Missing SQL file: {path}")
            text = path.read_text(encoding="utf-8")
            for stmt in _split_sql_statements(text):
                cur.execute(stmt)


def _print_rows(rows):
    if not rows:
        print("No rows returned.")
        return
    for r in rows:
        print(f"id={r[0]}  first_name={r[1]}  phone={r[2]}")


def pattern_search(conn):
    pattern = input("Search pattern (partial match on name or phone): ").strip()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, first_name, phone FROM search_contacts(%s);",
            (pattern,),
        )
        _print_rows(cur.fetchall())


def paginated_list(conn):
    limit_raw = input("Page size (limit): ").strip()
    offset_raw = input("Offset: ").strip()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, first_name, phone FROM get_contacts_paginated(%s, %s);",
            (int(limit_raw), int(offset_raw)),
        )
        _print_rows(cur.fetchall())


def insert_or_update_flow(conn):
    name = input("First name: ").strip()
    phone = input("Phone: ").strip()
    with conn.cursor() as cur:
        cur.execute("CALL insert_or_update_user(%s, %s);", (name, phone))


def bulk_insert_flow(conn):
    print("Enter contacts as name|phone, one per line. Empty line ends input.")
    rows = []
    while True:
        line = input().strip()
        if not line:
            break
        if "|" not in line:
            print("Skipped (use name|phone):", line)
            continue
        name, phone = line.split("|", 1)
        rows.append((name.strip(), phone.strip()))

    if not rows:
        print("No rows to import.")
        return

    with conn.cursor() as cur:
        cur.execute("TRUNCATE bulk_staging;")
        cur.executemany(
            "INSERT INTO bulk_staging (first_name, phone) VALUES (%s, %s);",
            rows,
        )
        cur.execute("CALL bulk_insert_users();")
        cur.execute(
            "SELECT first_name, phone, reason FROM bulk_invalid_results ORDER BY first_name, phone;"
        )
        invalid = cur.fetchall()

    if invalid:
        print("Invalid or conflicting rows:")
        for r in invalid:
            print(f"  name={r[0]}  phone={r[1]}  reason={r[2]}")
    else:
        print("No invalid rows reported by the database.")


def delete_flow(conn):
    ident = input("Delete by first name or phone (exact phone, case-insensitive name): ").strip()
    with conn.cursor() as cur:
        cur.execute("CALL delete_user(%s);", (ident,))
    print("Delete procedure executed (row counts are not returned for CALL).")


def main_menu():
    print("Connecting...")
    conn = connect_db()
    try:
        while True:
            print()
            print("PhoneBook (PostgreSQL) - Practice 8")
            print("0. Apply SQL objects (functions + procedures)")
            print("1. Pattern search (search_contacts)")
            print("2. Paginated list (get_contacts_paginated)")
            print("3. Insert or update user (insert_or_update_user)")
            print("4. Bulk insert (bulk_insert_users + staging)")
            print("5. Delete user (delete_user)")
            print("6. Exit")
            choice = input("Select option (0-6): ").strip()

            if choice == "0":
                try:
                    apply_sql_files(conn)
                    conn.commit()
                    print("SQL objects applied.")
                except Exception as e:
                    conn.rollback()
                    print("Failed to apply SQL:", e)
            elif choice == "1":
                try:
                    pattern_search(conn)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print("Search failed:", e)
            elif choice == "2":
                try:
                    paginated_list(conn)
                    conn.commit()
                except ValueError:
                    print("Limit and offset must be integers.")
                except Exception as e:
                    conn.rollback()
                    print("Pagination query failed:", e)
            elif choice == "3":
                try:
                    insert_or_update_flow(conn)
                    conn.commit()
                    print("Insert/update completed.")
                except pg_errors.Error as e:
                    conn.rollback()
                    print("Insert/update failed:", e.pgerror or e)
            elif choice == "4":
                try:
                    bulk_insert_flow(conn)
                    conn.commit()
                    print("Bulk import transaction committed.")
                except pg_errors.Error as e:
                    conn.rollback()
                    print("Bulk import failed:", e)
            elif choice == "5":
                try:
                    delete_flow(conn)
                    conn.commit()
                except pg_errors.Error as e:
                    conn.rollback()
                    print("Delete failed:", e.pgerror or e)
            elif choice == "6":
                print("Goodbye.")
                break
            else:
                print("Invalid option.")
    finally:
        if conn and not conn.closed:
            conn.close()


def main():
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        sys.exit(0)
    except EOFError:
        print("\nEOF. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
