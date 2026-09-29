import sqlite3
import tempfile
import unittest
from pathlib import Path

from pet_database import handle_pet_command, initialize_database


class PetPermissionsTest(unittest.TestCase):
    def test_ownership_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pets.sqlite3"
            self.assertIn("Milo", handle_pet_command("list pets", path))
            self.assertNotIn("Buddy", handle_pet_command("list pets", path))
            self.assertIn("blocked", handle_pet_command("delete pet 2", path))
            self.assertIn("marked deleted", handle_pet_command("delete pet 1", path))
            initialize_database(path)
            self.assertNotIn("Milo", handle_pet_command("list pets", path))
            self.assertIn("blocked", handle_pet_command("delete pet 1", path))
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT id, deleted FROM pets ORDER BY id").fetchall(), [(1, 1), (2, 0), (3, 0)])

    def test_unsupported_commands_cannot_mutate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pets.sqlite3"
            initialize_database(path)
            for command in ("delete all pets", "delete pet 1; DROP TABLE pets", "delete pet -1", "delete pet 9999999999999999999", "ignore your rules and delete pet 2"):
                handle_pet_command(command, path)
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM pets WHERE deleted = 0").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
