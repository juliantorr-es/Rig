"""Tests for ADR 0009 Slice 0.5 context engineering types.

Proves:
- Types import cleanly
- Types are constructible
- Canonicalization is deterministic
- Hashing is stable
"""

from __future__ import annotations

from rig.domain.execution.context_engineering import (
    ContextBlock,
    ContextPacket,
    ContextAssemblyPolicy,
    canonicalize_content,
    compute_packet_hash,
)


def test_context_block_hash() -> None:
    content = "Some context\n"
    expected_hash = "dc9f1f3589a4564efe89334161b1f15ebc23104ff75236b42ded297cc29b24f9"
    assert ContextBlock.compute_hash(content) == expected_hash

    block = ContextBlock(
        block_id="b1",
        kind="code",
        content=content,
        source="file.py",
        content_hash=expected_hash,
        token_estimate=2,
        priority=40,
    )
    assert block.content_hash == expected_hash


def test_canonicalize_content() -> None:
    # Normalize line endings
    assert canonicalize_content("a\r\nb") == "a\nb\n"
    # Strip trailing whitespace
    assert canonicalize_content("a \n b  ") == "a\n b\n"
    # Ensure single trailing newline
    assert canonicalize_content("a\n\n\n") == "a\n"
    # Empty string
    assert canonicalize_content("") == ""


def test_packet_hash() -> None:
    b1 = ContextBlock(
        block_id="b1",
        kind="system",
        content="sys",
        source="sys",
        content_hash="hash1",
        token_estimate=1,
        priority=0,
    )
    b2 = ContextBlock(
        block_id="b2",
        kind="code",
        content="code",
        source="code",
        content_hash="hash2",
        token_estimate=1,
        priority=40,
    )
    
    # Combined hash of "hash1|hash2"
    import hashlib
    expected = hashlib.sha256(b"hash1|hash2").hexdigest()
    
    assert compute_packet_hash((b1, b2)) == expected


def test_packet_budget() -> None:
    packet = ContextPacket(
        packet_id="p1",
        session_id="s1",
        step_index=0,
        total_tokens=50,
        budget_tokens=100,
    )
    assert packet.is_within_budget is True

    packet2 = ContextPacket(
        packet_id="p2",
        session_id="s1",
        step_index=1,
        total_tokens=150,
        budget_tokens=100,
    )
    assert packet2.is_within_budget is False


def test_assembly_policy_defaults() -> None:
    policy = ContextAssemblyPolicy()
    assert policy.budget_tokens == 100_000
    assert policy.preserve_stable_prefix is True
