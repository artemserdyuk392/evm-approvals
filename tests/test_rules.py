import time

from evm_approvals.abi import MAX_UINT256
from evm_approvals.rules import (
    Approval,
    evaluate,
    rule_allowance_exceeds_balance,
    rule_approval_for_all,
    rule_nonzero_allowance_zero_balance,
    rule_spender_is_eoa,
    rule_spender_unverified,
    rule_stale_approval,
    rule_unlimited_allowance,
    worst_severity,
)

NOW = int(time.time())
DAY = 86400


def erc20(**kw):
    base = dict(kind="erc20", token="0xtok", spender="0xspd")
    base.update(kw)
    return Approval(**base)


def test_unlimited_allowance_is_high():
    finding = rule_unlimited_allowance(erc20(allowance=MAX_UINT256), {})
    assert finding.severity == "high"
    assert rule_unlimited_allowance(erc20(allowance=5), {}) is None


def test_allowance_exceeds_balance_is_high():
    assert rule_allowance_exceeds_balance(
        erc20(allowance=1000, balance=10), {}).severity == "high"
    # within an order of magnitude does not fire
    assert rule_allowance_exceeds_balance(
        erc20(allowance=1000, balance=500), {}) is None
    # unlimited is covered by its own rule, not this one
    assert rule_allowance_exceeds_balance(
        erc20(allowance=MAX_UINT256, balance=10), {}) is None


def test_approval_for_all_is_high():
    a = Approval(kind="erc721", token="0xtok", spender="0xop", approved=True)
    assert rule_approval_for_all(a, {}).severity == "high"
    a2 = Approval(kind="erc721", token="0xtok", spender="0xop", approved=False)
    assert rule_approval_for_all(a2, {}) is None


def test_spender_is_eoa_is_high():
    assert rule_spender_is_eoa(
        erc20(allowance=5, spender_is_contract=False), {}).severity == "high"
    assert rule_spender_is_eoa(
        erc20(allowance=5, spender_is_contract=True), {}) is None


def test_spender_unverified_only_fires_when_known_false():
    assert rule_spender_unverified(
        erc20(allowance=5, spender_verified=False), {}).severity == "medium"
    assert rule_spender_unverified(erc20(allowance=5, spender_verified=None), {}) is None
    assert rule_spender_unverified(erc20(allowance=5, spender_verified=True), {}) is None


def test_stale_approval_fires_for_old_and_unused():
    ctx = {"now": NOW, "stale_days": 90}
    old_unused = erc20(allowance=100, last_logged_value=100,
                       last_approve_time=NOW - 200 * DAY)
    assert rule_stale_approval(old_unused, ctx).severity == "medium"


def test_stale_approval_ignores_recent():
    ctx = {"now": NOW, "stale_days": 90}
    recent = erc20(allowance=100, last_logged_value=100,
                   last_approve_time=NOW - 10 * DAY)
    assert rule_stale_approval(recent, ctx) is None


def test_stale_approval_ignores_used_allowance():
    # allowance dropped below the last approved amount, so it was spent since.
    ctx = {"now": NOW, "stale_days": 90}
    used = erc20(allowance=40, last_logged_value=100,
                 last_approve_time=NOW - 200 * DAY)
    assert rule_stale_approval(used, ctx) is None


def test_nonzero_allowance_zero_balance_is_low():
    assert rule_nonzero_allowance_zero_balance(
        erc20(allowance=5, balance=0), {}).severity == "low"
    assert rule_nonzero_allowance_zero_balance(
        erc20(allowance=5, balance=10), {}) is None


def test_worst_severity_picks_highest():
    from evm_approvals.rules import Finding
    findings = [Finding("a", "low", ""), Finding("b", "high", ""),
                Finding("c", "medium", "")]
    assert worst_severity(findings) == "high"
    assert worst_severity([]) == "low"


def test_evaluate_reports_all_fired_rules_and_worst_severity():
    a = erc20(allowance=MAX_UINT256, balance=0, spender_is_contract=False)
    findings, severity = evaluate(a, {"now": NOW, "stale_days": 90})
    names = {f.rule for f in findings}
    assert "unlimited_allowance" in names
    assert "spender_is_eoa" in names
    assert "nonzero_allowance_zero_balance" in names
    assert severity == "high"
