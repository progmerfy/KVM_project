import os
import sys
import tempfile

# Make the libvirt stub importable before any app code runs
sys.path.insert(0, os.path.dirname(__file__))

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["API_USERNAME"] = "admin"
os.environ["API_PASSWORD"] = "admin1234"

from app.database import init_db
from app.main import app

init_db()


def _override_get_current_user():
    return {
        "id": 1,
        "username": "admin",
        "is_admin": 1,
    }


from app.auth import get_current_user

app.dependency_overrides[get_current_user] = _override_get_current_user
