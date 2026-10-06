from types import SimpleNamespace

import pytest
import requests

from evm_approvals.chains import get_chain
from evm_approvals.logs import is_range_error
from evm_approvals.rpc import Rpc, RpcError


def _http_error(status, body: bytes):
    response = requests.Response()
    response.status_code = status
    response._content = body
    return requests.HTTPError(f"{status} Client Error", response=response)


class _RaisingProvider:
    def __init__(self, exc):
        self.exc = exc

    def make_request(self, method, params):
        raise self.exc


def _rpc(exc):
    return Rpc(SimpleNamespace(provider=_RaisingProvider(exc)), get_chain("base"))


def test_get_logs_reads_the_error_from_a_non_200_json_body():
    # Shape of mainnet.base.org's answer to a window wider than 500 blocks.
    body = (b'{"jsonrpc":"2.0","error":{"code":-32614,'
            b'"message":"eth_getLogs is limited to a 500 range"},"id":1}')
    with pytest.raises(RpcError, match="limited to a 500 range") as info:
        _rpc(_http_error(413, body)).get_logs(0, 10000, [])
    assert is_range_error(str(info.value))


def test_get_logs_reraises_http_errors_without_a_json_error():
    exc = _http_error(525, b"<!DOCTYPE html><html>origin SSL handshake failed</html>")
    with pytest.raises(requests.HTTPError):
        _rpc(exc).get_logs(0, 10, [])
