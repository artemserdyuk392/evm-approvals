"""Optional block-explorer lookup: is a spender contract's source verified.
Used only when an API key is configured, and never required for a scan."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request


class Explorer:
    def __init__(self, api_url: str, api_key: str, chain_id: int, timeout: int = 15):
        self.api_url = api_url
        self.api_key = api_key
        self.chain_id = chain_id
        self.timeout = timeout

    def is_verified(self, address: str):
        """Return True/False, or None when the lookup itself failed so the rule
        can stay silent rather than guess."""
        query = urllib.parse.urlencode({
            "chainid": self.chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": self.api_key,
        })
        try:
            with urllib.request.urlopen(f"{self.api_url}?{query}",
                                        timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        result = data.get("result")
        if not isinstance(result, list) or not result:
            return None
        return bool((result[0].get("SourceCode") or "").strip())
