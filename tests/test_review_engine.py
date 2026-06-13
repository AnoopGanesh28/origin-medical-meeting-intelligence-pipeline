import pytest
from app.review_engine import requires_review
from app.schemas import ActionItem

def test_requires_review_low_confidence():
    item = ActionItem(title="test", description="test", assignee="Bob", priority="MEDIUM", confidence=0.79)
    assert requires_review(item) is True
    
def test_requires_review_missing_assignee():
    item1 = ActionItem(title="test", description="test", assignee=None, priority="MEDIUM", confidence=0.95)
    assert requires_review(item1) is True
    
    item2 = ActionItem(title="test", description="test", assignee="", priority="MEDIUM", confidence=0.95)
    assert requires_review(item2) is True
    
def test_requires_review_ambiguous_ownership():
    item1 = ActionItem(title="test", description="test", assignee="Team", priority="MEDIUM", confidence=0.95)
    assert requires_review(item1) is True
    
    item3 = ActionItem(title="test", description="test", assignee="Someone", priority="MEDIUM", confidence=0.95)
    assert requires_review(item3) is True

def test_requires_review_valid():
    item = ActionItem(title="test", description="test", assignee="Alice", priority="MEDIUM", confidence=0.90)
    assert requires_review(item) is False
