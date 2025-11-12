"""Tests for research planner."""

import pytest
from app.research.planner import make_plan


def test_planner_generates_steps():
    """Test that planner generates at least 8 steps."""
    question = "History of phosphate mining in NSW"
    plan = make_plan(question, region="Clarence Valley, NSW", time_window="1970-1995", depth="standard")
    
    assert len(plan) >= 8
    assert all(step.query for step in plan)
    assert all(step.rationale for step in plan)
    assert all(step.scope in ("web", "trove") for step in plan)


def test_planner_includes_region():
    """Test that region appears in queries when provided."""
    question = "Mining history"
    region = "Clarence Valley, NSW"
    plan = make_plan(question, region=region, depth="brief")
    
    # At least one step should include the region
    region_in_queries = any(region in step.query for step in plan)
    assert region_in_queries


def test_planner_includes_time_window():
    """Test that time window appears in queries when provided."""
    question = "Mining history"
    time_window = "1970-1995"
    plan = make_plan(question, time_window=time_window, depth="brief")
    
    # At least one step should include the time window
    time_in_queries = any(time_window in step.query for step in plan)
    assert time_in_queries


def test_planner_mixes_scopes():
    """Test that plan includes both web and trove scopes."""
    question = "Test question"
    plan = make_plan(question, depth="standard")
    
    web_steps = [s for s in plan if s.scope == "web"]
    trove_steps = [s for s in plan if s.scope == "trove"]
    
    assert len(web_steps) > 0
    assert len(trove_steps) > 0


def test_planner_depth_variations():
    """Test that different depths produce different step counts."""
    question = "Test question"
    
    brief = make_plan(question, depth="brief")
    standard = make_plan(question, depth="standard")
    deep = make_plan(question, depth="deep")
    
    assert len(brief) <= len(standard) <= len(deep)
    assert len(brief) >= 6
    assert len(standard) >= 10
    assert len(deep) >= 15

