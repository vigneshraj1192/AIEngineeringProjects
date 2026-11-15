"""Unit tests for Repo Map construction, token budgeting, and code retrieval."""

import pytest
from pathlib import Path
from codepilot.config import config
from codepilot.context.repo_map import RepoMapBuilder
from codepilot.context.retrieval import CodeRetriever, KeywordRetriever

SAMPLE_REPO_DIR = Path(__file__).resolve().parent.parent / "sample_repo"

def test_repo_map_construction():
    builder = RepoMapBuilder(SAMPLE_REPO_DIR)
    repo_map = builder.build_or_load(force_refresh=True)

    assert repo_map.root_path == str(SAMPLE_REPO_DIR.resolve())
    assert len(repo_map.files) > 0
    assert any("oauth.py" in p for p in repo_map.files)
    assert any("report.py" in p for p in repo_map.files)

    # Check AST symbol extraction
    oauth_file = next(p for p in repo_map.files if "oauth.py" in p)
    summary = repo_map.files[oauth_file]
    assert "class OAuthHandler" in summary.symbols
    assert any("build_authorize_url" in s for s in summary.symbols)

def test_token_budget_discipline():
    builder = RepoMapBuilder(SAMPLE_REPO_DIR)
    repo_map = builder.build_or_load()

    # Format with tiny budget to force truncation
    formatted_tiny = repo_map.format_for_prompt(max_tokens=50)
    assert "truncated" in formatted_tiny or len(formatted_tiny) < 400

    # Format with generous budget
    formatted_normal = repo_map.format_for_prompt(max_tokens=4000)
    assert "Directory Tree:" in formatted_normal
    assert "oauth.py" in formatted_normal

def test_keyword_retrieval():
    builder = RepoMapBuilder(SAMPLE_REPO_DIR)
    repo_map = builder.build_or_load()

    query = "OAuth redirect handler and authorize url"
    results = KeywordRetriever.retrieve(repo_map, query, top_k=5)
    assert len(results) > 0
    assert any("oauth.py" in r for r in results)

def test_unified_retriever():
    retriever = CodeRetriever(SAMPLE_REPO_DIR)
    builder = RepoMapBuilder(SAMPLE_REPO_DIR)
    repo_map = builder.build_or_load()

    files = retriever.retrieve_relevant_files(
        repo_map=repo_map,
        task_description="Add CSV export functionality to metrics report",
        strategy="keyword",
        top_k=5
    )
    assert len(files) > 0
    assert any("report.py" in f for f in files)
