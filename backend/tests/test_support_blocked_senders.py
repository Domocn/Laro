"""Inbound support email: cold-sales senders on the block list never become tickets."""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _support():
    return importlib.import_module("routers.support")


def test_default_blocked_domain(monkeypatch):
    monkeypatch.delenv("SUPPORT_BLOCKED_SENDERS", raising=False)
    s = _support()
    assert s._is_blocked_sender("market@appfast.com")
    assert s._is_blocked_sender("MARKET@AppFast.com")
    assert s._is_blocked_sender("x@mail.appfast.com")


def test_lookalike_domains_not_blocked(monkeypatch):
    monkeypatch.delenv("SUPPORT_BLOCKED_SENDERS", raising=False)
    s = _support()
    assert not s._is_blocked_sender("someone@notappfast.com")
    assert not s._is_blocked_sender("user@gmail.com")
    assert not s._is_blocked_sender("")
    assert not s._is_blocked_sender("not-an-address")


def test_env_extends_block_list(monkeypatch):
    monkeypatch.setenv("SUPPORT_BLOCKED_SENDERS", "spam@example.org, @seo-agency.io")
    s = _support()
    assert s._is_blocked_sender("spam@example.org")
    assert not s._is_blocked_sender("friend@example.org")
    assert s._is_blocked_sender("bob@seo-agency.io")
