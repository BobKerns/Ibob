"""
A utility to inspect `XGitProxy` objects in JSON format.
"""

from typing import Any

from xontrib.xgit.types import _NO_VALUE
from xontrib.xgit.proxy import ProxyMetadata, XGitProxy, meta, target
from xontrib.xgit.to_json import to_json, JsonReturn, JsonDescriber, JsonKV


def proxy_to_json(obj: Any) -> JsonReturn:
    "Convert a proxy object to JSON"
    def handle_proxy(proxy: Any, describer: JsonDescriber) -> JsonKV:
        if isinstance(proxy, XGitProxy):
            t = target(proxy)
            m = meta(proxy)
            rest = {'_target': to_json(t)} if t is not _NO_VALUE else {}
            return {
                    '_metadata': to_json(m),
                    **rest
                }
        return {}
    #
    def handle_metadata(meta: ProxyMetadata, describer: JsonDescriber) -> JsonKV:
        if isinstance(meta, ProxyMetadata):
            print(meta)
            keys = ('name', 'namespace', 'accessor', 'adaptor', 'target', '_initialized')

            return {k: to_json(getattr(meta, k)) for k in keys}
        return {}
    describer = JsonDescriber(special_types={
        XGitProxy: handle_proxy,
        ProxyMetadata: handle_metadata,
        })
    return to_json(obj, describer=describer)
