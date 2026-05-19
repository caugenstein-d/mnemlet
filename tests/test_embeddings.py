"""Tests for the onnx embedding wrapper."""

import numpy as np
import pytest
from engram.storage.embeddings import EngramEmbedding


@pytest.fixture(scope="module")
def embedder():
    """Create an embedding model (expensive, so module-scoped)."""
    return EngramEmbedding()


def test_embed_single_text(embedder):
    """Embedding a single text returns a 384-dim vector."""
    vec = embedder.embed("Hello world")
    assert isinstance(vec, list)
    assert len(vec) == 384


def test_embed_multiple_texts(embedder):
    """Embedding multiple texts returns list of vectors."""
    texts = ["Hello world", "Dark mode preferences", "Python code style"]
    vecs = embedder.embed_batch(texts)
    assert len(vecs) == 3
    assert all(len(v) == 384 for v in vecs)


def test_identical_texts_have_max_similarity(embedder):
    """Identical texts have cosine similarity of 1.0."""
    v1 = embedder.embed("User prefers dark mode")
    v2 = embedder.embed("User prefers dark mode")
    sim = embedder.cosine_similarity(v1, v2)
    assert sim > 0.999  # Deterministic: same input = same vector


def test_dissimilar_texts_are_far(embedder):
    """Dissimilar texts have low cosine similarity."""
    v1 = embedder.embed("User prefers dark mode")
    v2 = embedder.embed("git commit -m 'fix bug'")
    sim = embedder.cosine_similarity(v1, v2)
    assert sim < 0.5  # Very different


def test_token_count(embedder):
    """Token count is reasonable."""
    tokens = embedder.count_tokens("Hello world, this is a test sentence.")
    assert 5 <= tokens <= 15
