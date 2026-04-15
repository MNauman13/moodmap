import pytest
import uuid
from unittest.mock import patch
from backend.models.db_models import JournalEntry
from sqlalchemy import select

# This decorator tells Pytest that we need to run this asynchronously
@pytest.mark.asyncio
async def test_create_journal_entry_success(client, db_session, mock_user_id):
    """
    Tests that a user can submit a journal entry, it saves to the DB,
    and it successfully triggers the Celery worker (without actually running it)
    """

    payload = {
        "text": "today was a remarkably good day. I felt very productive.",
        "mood_tags": ["happy", "focused"]
    }

    # 1. THE MOCK: We intercept the Celery .delay() function
    with patch('backend.routers.journal.analyze_entry.delay') as mock_celery_task:
        
        # We also need to give the fake task a fake ID so the router doesn't crash
        mock_celery_task.return_value.id = "fake-celery-task-id-123"

        # 2. THE ACTION: Make the request using our injected test client
        response = await client.post("/api/v1/journal", json=payload)
        
        # 3. THE ASSERTIONS
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "fake-celery-task-id-123"
        assert "entry_id" in data

        # 4. DATABASE VERIFICATION
        entry_uuid = uuid.UUID(data["entry_id"])
        # Did it actually save to our test SQLite database correctly?
        entry_result = await db_session.execute(
            select(JournalEntry).where(JournalEntry.id == entry_uuid)
        )
        saved_entry = entry_result.scalar_one_or_none()
        
        assert saved_entry is not None
        assert saved_entry.raw_text == payload["text"]
        assert saved_entry.word_count == 10 # "Today was a remarkably good day. I felt very productive."
        
        # Verify the Celery task was actually called with the correct database ID!
        mock_celery_task.assert_called_once_with(str(saved_entry.id))