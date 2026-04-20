import dj_database_url
from django.db import connections


def get_site_db_alias(site_id):
    return f'site_{site_id}'


def ensure_site_connection(site):
    """
    Register a dynamic database connection for the given site.
    Returns the database alias to use with .using(alias).
    """
    alias = get_site_db_alias(site.id)
    if alias not in connections.databases:
        config = dj_database_url.parse(site.database_url)
        config['CONN_MAX_AGE'] = 60
        config['CONN_HEALTH_CHECKS'] = True
        config['TIME_ZONE'] = 'America/Toronto'
        config['ATOMIC_REQUESTS'] = False
        config['AUTOCOMMIT'] = True
        config['OPTIONS'] = config.get('OPTIONS', {})
        connections.databases[alias] = config
    return alias


def test_site_connection(site):
    """Test if we can connect to the site's database."""
    alias = ensure_site_connection(site)
    try:
        conn = connections[alias]
        conn.ensure_connection()
        return True, "Connexion reussie"
    except Exception as e:
        return False, str(e)
