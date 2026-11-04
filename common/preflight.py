"""Fail closed for unsupported deployment/storage configurations; print no secrets."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from .security import SecurityError, mode, owner_email, require_owner, service_key, service_url


def validate_runtime(audience='ui-client'):
    if os.getenv('KOE_TOPOLOGY', 'local-shared') != 'local-shared' or os.getenv('K_SERVICE'):
        raise SecurityError('Only one-host shared SQLite operation is verified; cloud deployment remains item 22')
    mode()
    require_owner(owner_email())
    service_key(audience)
    production = os.getenv('APP_ENV', 'production') != 'development'
    for variable, default in [('DB_PATH','tokens.db'),('SECURITY_DB_PATH','.runtime/security.db')]:
        path = Path(os.getenv(variable, default))
        if production and not path.is_absolute():
            raise SecurityError(variable+' must be an explicit absolute shared-host path')
    for service in ('ui-client','lead-finder','lead-manager','sdr'):
        url = urlsplit(service_url(service))
        if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise SecurityError('Invalid service URL configuration')
        if production and url.scheme == 'http' and url.hostname not in {'localhost','127.0.0.1','::1'}:
            raise SecurityError('Non-loopback service transport requires HTTPS')
    return {'topology':'local-shared','mode':mode(),'storage':'shared_sqlite','cloud_verified':False}


if __name__ == '__main__':
    import json
    print(json.dumps(validate_runtime()))
