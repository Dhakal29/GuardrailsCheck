"""Local permission-guardrail exercise; the fixed identity is NOT authentication."""

import re
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).with_name("demo_pets.sqlite3")
DEMO_USER_ID = "demo-owner"


def initialize_database(path=DATABASE_PATH):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS pets ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL, species TEXT NOT NULL, "
            "owner_id TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)"
        )
        connection.executemany(
            "INSERT OR IGNORE INTO pets (id, name, species, owner_id) VALUES (?, ?, ?, ?)",
            [(1, "Milo", "cat", DEMO_USER_ID),
             (2, "Buddy", "dog", "another-owner"),
             (3, "Luna", "dog", DEMO_USER_ID)],
        )


def delete_pet(path, user_id, pet_id):
    """Atomically enforce ownership and soft-delete one active record."""
    if type(pet_id) is not int or not 0 < pet_id <= 2**63 - 1:
        raise ValueError("Pet ID must be a positive SQLite integer.")
    with sqlite3.connect(path) as connection:
        result = connection.execute(
            "UPDATE pets SET deleted = 1 "
            "WHERE id = ? AND owner_id = ? AND deleted = 0",
            (pet_id, user_id),
        )
        return result.rowcount == 1


def handle_pet_command(message, path=DATABASE_PATH):
    """Return None for chat; only exact supported commands can access the DB."""
    command = message.strip().lower()
    match = re.fullmatch(r"delete pet ([0-9]{1,19})", command)
    if command != "list pets" and match is None:
        if command.startswith("delete"):
            return "Use exactly: delete pet <id>. Bulk deletion and SQL are not supported."
        return None

    initialize_database(path)
    if command == "list pets":
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT id, name, species FROM pets "
                "WHERE owner_id = ? AND deleted = 0 ORDER BY id",
                (DEMO_USER_ID,),
            ).fetchall()
        return "\n".join(f"{pet_id}: {name} ({species})" for pet_id, name, species in rows) or "No active pets."

    pet_id = int(match.group(1))
    if pet_id > 2**63 - 1:
        return "Pet ID is too large."
    if delete_pet(path, DEMO_USER_ID, pet_id):
        return f"Pet {pet_id} marked deleted in the local demo database."
    return "Deletion blocked: pet is unavailable or you do not own it."


if __name__ == "__main__":
    print("Local demo user: demo-owner (simulated identity, not a login).")
    print("Commands: list pets, delete pet <id>, exit. Try ID 2 to test denied access.")
    try:
        while True:
            message = input("\nYou: ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            print(handle_pet_command(message) or "Use list pets or delete pet <id>.")
    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")
