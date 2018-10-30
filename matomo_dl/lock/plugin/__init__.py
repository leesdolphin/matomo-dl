import logging
import typing as typ

from matomo_dl.distribution.file import GitPlugin, Plugin, VersionedPlugin
from matomo_dl.distribution.lock import GitPluginLock, PluginLock, VersionedPluginLock
from matomo_dl.session import SessionStore
from .git import sync_git_plugin_lock
from .versioned import sync_versioned_plugin_lock

logger = logging.getLogger(__name__)

normalise_name = (  # noqa: F841 -- Exported here for convenience
    Plugin.to_normalised_name
)


def sync_plugin_lock(
    session: SessionStore,
    php_version: str,
    matomo_version: str,
    license_key: typ.Optional[str],
    name: str,
    plugin: Plugin,
    existing_lock: typ.Optional[PluginLock],
) -> PluginLock:
    if isinstance(plugin, VersionedPlugin):
        if not isinstance(existing_lock, VersionedPluginLock):
            existing_lock = None
        return sync_versioned_plugin_lock(
            session,
            php_version,
            matomo_version,
            license_key,
            normalise_name(name),
            plugin.version,
            existing_lock,
        )
    elif isinstance(plugin, GitPlugin):
        if not isinstance(existing_lock, GitPluginLock):
            existing_lock = None
        return sync_git_plugin_lock(
            session,
            php_version,
            matomo_version,
            license_key,
            normalise_name(name),
            plugin.git,
            plugin.ref,
            existing_lock,
        )
    else:
        raise ValueError("Unsupported plugin type.")