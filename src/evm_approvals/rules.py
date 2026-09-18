"""Risk rules as a plain checklist. Each rule is one function that returns a
Finding when it fires; overall risk is the worst severity among fired rules,
with no weighting and no hidden score."""

from __future__ import annotations

from dataclasses import dataclass

from .abi import MAX_UINT256

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Finding:
    rule: str
    severity: str
    reason: str


@dataclass
class Approval:
    kind: str                     # "erc20" or "erc721"
    token: str
    spender: str
    symbol: str = ""
    decimals: int | None = None
    allowance: int = 0            # erc20 current allowance
    approved: bool = False        # erc721 isApprovedForAll
    balance: int | None = None
    last_approve_time: int | None = None
    last_logged_value: int | None = None
    spender_is_contract: bool = True
    spender_verified: bool | None = None


def rule_unlimited_allowance(a: Approval, ctx: dict):
    # Infinite allowance never decays: whoever controls the spender can move
    # every token the owner holds now and every one they ever receive.
    if a.kind == "erc20" and a.allowance >= MAX_UINT256:
        return Finding("unlimited_allowance", "high",
                       "allowance is unlimited (2**256-1)")
    return None


def rule_allowance_exceeds_balance(a: Approval, ctx: dict):
    # A finite allowance an order of magnitude above the balance is far more
    # than any real interaction needs, so a drained spender takes more.
    if a.kind != "erc20" or a.allowance == 0 or a.allowance >= MAX_UINT256:
        return None
    if a.balance and a.allowance > a.balance * 10:
        return Finding("allowance_exceeds_balance", "high",
                       "allowance exceeds the token balance by more than 10x")
    return None


def rule_approval_for_all(a: Approval, ctx: dict):
    # setApprovalForAll hands over every token id in a collection at once; it is
    # the NFT equivalent of an unlimited ERC-20 allowance.
    if a.kind == "erc721" and a.approved:
        return Finding("approval_for_all", "high",
                       "operator is approved for all tokens in the collection")
    return None


def rule_spender_is_eoa(a: Approval, ctx: dict):
    # A spender with no code cannot be a protocol contract. A live approval to
    # an externally owned account is almost always phishing or a mistake.
    if not a.spender_is_contract:
        return Finding("spender_is_eoa", "high",
                       "spender is an externally owned account, not a contract")
    return None


def rule_spender_unverified(a: Approval, ctx: dict):
    # Optional, only meaningful when an explorer key let us check. Unverified
    # source is not proof of malice but removes any way to audit the spender.
    if a.spender_verified is False:
        return Finding("spender_unverified", "medium",
                       "spender contract source is not verified on the explorer")
    return None


def rule_stale_approval(a: Approval, ctx: dict):
    # Old and seemingly unused: the current allowance still equals the amount
    # last approved (no decrement observed), so it looks granted and forgotten.
    days = ctx.get("stale_days", 90)
    now = ctx.get("now")
    if a.last_approve_time is None or now is None:
        return None
    age_days = (now - a.last_approve_time) / 86400
    if age_days < days:
        return None
    unused = (a.last_logged_value is None
              or a.allowance == a.last_logged_value
              or (a.kind == "erc721" and a.approved))
    if unused:
        return Finding("stale_approval", "medium",
                       f"approval is older than {days} days and appears unused")
    return None


def rule_nonzero_allowance_zero_balance(a: Approval, ctx: dict):
    # Nothing to steal today, so low priority, but the approval stays latent and
    # applies the moment any of this token lands in the wallet.
    if a.kind == "erc20" and a.allowance > 0 and a.balance == 0:
        return Finding("nonzero_allowance_zero_balance", "low",
                       "allowance is set while the token balance is zero")
    return None


ALL_RULES = (
    rule_unlimited_allowance,
    rule_allowance_exceeds_balance,
    rule_approval_for_all,
    rule_spender_is_eoa,
    rule_spender_unverified,
    rule_stale_approval,
    rule_nonzero_allowance_zero_balance,
)


def evaluate(approval: Approval, ctx: dict | None = None):
    ctx = ctx or {}
    findings = [rule(approval, ctx) for rule in ALL_RULES]
    findings = [f for f in findings if f is not None]
    return findings, worst_severity(findings)


def worst_severity(findings) -> str:
    if not findings:
        return "low"
    return max((f.severity for f in findings), key=lambda s: SEVERITY_ORDER[s])
