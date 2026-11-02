from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def insert_submission(db: Database, submission: dict) -> bool:
    """Inserts the confirmed submission. Returns True if newly inserted, False if a
    submission for this session_id already existed (the unique index from Step 2 makes this
    safe to call again after a retry - a duplicate save is a no-op, not an error)."""
    try:
        db["submissions"].insert_one(submission)
        return True
    except DuplicateKeyError:
        return False


def get_submission(db: Database, session_id: str) -> dict | None:
    return db["submissions"].find_one({"session_id": session_id}, {"_id": 0})
