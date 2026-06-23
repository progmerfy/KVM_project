"""Unit tests for app.auth — JWT token creation, verification, and auth flows."""

import os
import tempfile
from datetime import timedelta
from unittest.mock import patch, MagicMock

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-32-bytes-for-testing!!"

from app.auth import create_access_token, verify_token, require_auth, get_current_user, ALGORITHM
from app.database import init_db, create_user

init_db()


class TestTokenCreation:
    def test_create_and_verify(self):
        token = create_access_token({"sub": "admin", "user_id": 1})
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        payload = verify_token(token)
        assert payload["sub"] == "admin"
        assert payload["user_id"] == 1
        assert "exp" in payload

    def test_expired_token(self):
        token = create_access_token({"sub": "test"}, expires_delta=timedelta(seconds=-1))
        from jwt.exceptions import ExpiredSignatureError
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_token(token)
        assert exc.value.status_code == 401
        assert "expired" in str(exc.value.detail).lower()

    def test_invalid_token(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_token("not.a.token")
        assert exc.value.status_code == 401
        assert "invalid" in str(exc.value.detail).lower()

    def test_missing_auth_header(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            require_auth(credentials=None)
        assert exc.value.status_code == 401

    def test_valid_auth(self):
        token = create_access_token({"sub": "admin", "user_id": 1})
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        payload = require_auth(credentials=creds)
        assert payload["sub"] == "admin"

    def test_get_current_user_success(self):
        token = create_access_token({"sub": "admin", "user_id": 1})
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = get_current_user(payload=require_auth(credentials=creds))
        assert user["username"] == "admin"

    def test_get_current_user_missing_id(self):
        token = create_access_token({"sub": "admin"})
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(payload=require_auth(credentials=creds))
        assert exc.value.status_code == 401

    def test_get_current_user_not_found(self):
        token = create_access_token({"sub": "ghost", "user_id": 99999})
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(payload=require_auth(credentials=creds))
        assert exc.value.status_code == 401


import pytest
