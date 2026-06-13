import pytest
from pydantic import ValidationError
from app.schemas import ActionItem, MeetingExtraction

def test_action_item_validation():
    # Valid ActionItem
    item = ActionItem(title="Fix bug", description="Fix issue #123", priority="HIGH", confidence=0.9)
    assert item.title == "Fix bug"
    assert item.priority == "HIGH"
    
    # Invalid priority
    with pytest.raises(ValidationError):
        ActionItem(title="Fix bug", description="Fix issue #123", priority="URGENT", confidence=0.9)
        
    # Invalid confidence (must be <= 1.0)
    with pytest.raises(ValidationError):
        ActionItem(title="Fix bug", description="Fix issue #123", priority="HIGH", confidence=1.5)

    # Invalid confidence (must be >= 0.0)
    with pytest.raises(ValidationError):
        ActionItem(title="Fix bug", description="Fix issue #123", priority="HIGH", confidence=-0.1)

def test_meeting_extraction_validation():
    item = ActionItem(title="Fix bug", description="Fix issue #123", priority="HIGH", confidence=0.9)
    
    # Valid MeetingExtraction
    ext = MeetingExtraction(meeting_summary="Summary of the meeting.", action_items=[item])
    assert len(ext.action_items) == 1
    assert ext.meeting_summary == "Summary of the meeting."
    
    # Missing required summary
    with pytest.raises(ValidationError):
        MeetingExtraction(meeting_summary="", action_items=[item])
