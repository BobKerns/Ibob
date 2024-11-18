"""
A utility to inspect `XGitProxy` objects in JSON format.
"""

from typing import Any, Optional    

from xontrib.xgit.types import _NO_VALUE
from xontrib.xgit.proxy import ProxyMetadata, XGitProxy, meta, target
from xontrib.xgit.context_types import GitRepository
from xontrib.xgit.json_types import JsonDescriber, JsonReturn,JsonKV
from xontrib.xgit.to_json import to_json, _JsonDescriber
import xontrib.xgit.vars as xv


def proxy_to_json(obj: Any,
                  repository: Optional[GitRepository]=None
                  ) -> JsonReturn:
    if hasattr(obj, 'repository'):
        repository = obj.repository
    "Convert a proxy object to JSON"
    def handle_proxy(proxy: Any, describer: JsonDescriber) -> JsonKV:
        repo = (repository or describer.repository)
        if isinstance(proxy, XGitProxy):
            t = target(proxy)
            m = meta(proxy)
            rest = {
                '_target': to_json(t, repository=repo)
                } if t is not _NO_VALUE else {}
            return {
                    '_metadata': proxy_to_json(m),
                    **rest
                }
        return {}
    #
    def handle_metadata(meta: ProxyMetadata,
                        describer: JsonDescriber,
                        repository: Optional[GitRepository]=None,
                        ) -> JsonKV:
        if isinstance(meta, ProxyMetadata):
            if repository is None:
                repository = describer.repository
            if repository is None and xv.XGIT:
                repository = xv.XGIT.repository
            if repository is None:
                raise ValueError("No repository provided or available.")
            keys = ('name', 'namespace', 'accessor', 'adaptor', 'target', '_initialized')

            return {
                k:to_json(getattr(meta, k),
                          repository=repository)
                for k in keys
            }
        return {}
    if repository is None and xv.XGIT:
        repository = xv.XGIT.repository
    if repository is None:
        raise ValueError("No repository provided or available.")
    describer = _JsonDescriber(
        repository=repository,
        special_types={
            XGitProxy: handle_proxy,
            ProxyMetadata: handle_metadata,
        })
    return to_json(obj, describer=describer, repository=repository)
