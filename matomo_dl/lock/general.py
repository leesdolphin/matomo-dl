import logging
import typing as typ

from matomo_dl.distribution.file import DistributionFile
from matomo_dl.distribution.lock import DistributionLockFile
from matomo_dl.lock.matomo import sync_matomo_lock
from matomo_dl.lock.plugin import sync_plugin_lock
from matomo_dl.session import SessionStore

logger = logging.getLogger(__name__)
DEFAULT_ASSUMED_PHP_VERSION = "7.2"


def build_lock(
    session: SessionStore,
    dist: DistributionFile,
    lock: typ.Optional[DistributionLockFile],
) -> DistributionLockFile:
    matomo_lock = sync_matomo_lock(session, dist.version, lock.matomo if lock else None)
    if lock:
        old_plugin_locks = {
            name: plugin_lock for name, plugin_lock in lock.plugin_locks.items()
        }
    else:
        old_plugin_locks = {}
    plugin_locks = {}
    for name, plugin in dist.plugins.items():
        p_lock = sync_plugin_lock(
            session,
            dist.php_version or DEFAULT_ASSUMED_PHP_VERSION,
            matomo_lock.version,
            dist.license_key,
            name,
            plugin,
            old_plugin_locks.get(name),
        )
        plugin_locks[name] = p_lock
    return DistributionLockFile(
        matomo=matomo_lock,
        plugin_locks=plugin_locks,
        distribution_hash=dist.versioning_hash,
    )
