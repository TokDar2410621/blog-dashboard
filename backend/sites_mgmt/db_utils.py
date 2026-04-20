import logging

import dj_database_url
from django.db import connections
from django.apps import apps

logger = logging.getLogger(__name__)

# In-memory cache: once a site's schema is synced for this worker, skip it
_SCHEMA_SYNCED = set()


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

    # Auto-sync schema on first use (add missing columns that the model expects)
    if alias not in _SCHEMA_SYNCED:
        try:
            success = sync_blog_schema(alias, site=site)
            if success:
                _SCHEMA_SYNCED.add(alias)
        except Exception:
            logger.exception("Schema sync failed for %s", alias)

    return alias


def sync_blog_schema(alias, site=None):
    """
    Compare current blog model fields with actual DB schema; ADD missing
    columns via ALTER TABLE (real tables) or rebuild VIEW (view-backed sites).
    Returns True if schema is now in sync, False if manual intervention needed.
    """
    conn = connections[alias]
    if conn.vendor != 'postgresql':
        return True

    blog_models = [
        apps.get_model('blog', 'BlogPost'),
        apps.get_model('blog', 'Category'),
        apps.get_model('blog', 'Tag'),
    ]

    rebuild_views = False

    with conn.cursor() as cursor:
        for model in blog_models:
            table = model._meta.db_table
            cursor.execute(
                "SELECT table_type FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s", [table]
            )
            row = cursor.fetchone()
            if not row:
                continue
            is_view = row[0] == 'VIEW'

            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s", [table]
            )
            existing = {r[0] for r in cursor.fetchall()}

            missing = [f for f in model._meta.fields if f.column not in existing]
            if not missing:
                continue

            if is_view:
                logger.info(
                    "%s on %s is a VIEW with missing columns %s — will rebuild",
                    table, alias, [f.column for f in missing]
                )
                rebuild_views = True
                break
            else:
                for field in missing:
                    col_sql = _column_definition(field, conn)
                    if not col_sql:
                        continue
                    alter = f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{field.column}" {col_sql}'
                    try:
                        cursor.execute(alter)
                        logger.info("Added column %s.%s on %s", table, field.column, alias)
                    except Exception:
                        logger.exception("Failed to add column %s.%s on %s", table, field.column, alias)

    if not rebuild_views:
        return True

    if not site:
        logger.warning("Cannot rebuild views on %s — no site object", alias)
        return False

    if not site.blog_config:
        logger.warning(
            "Cannot rebuild views on %s — site.blog_config is empty. "
            "Run /api/sites/%s/detect_blog/ then /setup_blog/ to regenerate views.",
            alias, site.id
        )
        return False

    try:
        from .blog_adapter import setup_blog_views
        setup_blog_views(alias, site.blog_config)
        logger.info("Rebuilt blog views on %s", alias)
        return True
    except Exception:
        logger.exception("Failed to rebuild blog views on %s", alias)
        return False


def _column_definition(field, conn):
    """Build the column definition SQL (type + nullable + default) for ADD COLUMN."""
    col_type = field.db_type(connection=conn)
    if not col_type:
        return None

    parts = [col_type]
    if field.null:
        parts.append("NULL")
    elif field.has_default():
        default = field.get_default()
        if callable(default):
            if field.get_internal_type() == 'UUIDField':
                parts.append("DEFAULT gen_random_uuid()")
            else:
                parts.append("NULL")
        elif isinstance(default, bool):
            parts.append(f"DEFAULT {'true' if default else 'false'}")
        elif isinstance(default, str):
            escaped = default.replace("'", "''")
            parts.append(f"DEFAULT '{escaped}' NOT NULL")
        elif isinstance(default, (int, float)):
            parts.append(f"DEFAULT {default} NOT NULL")
        else:
            parts.append("NULL")
    else:
        parts.append("NULL")

    return " ".join(parts)


def test_site_connection(site):
    """Test if we can connect to the site's database."""
    alias = ensure_site_connection(site)
    try:
        conn = connections[alias]
        conn.ensure_connection()
        return True, "Connexion reussie"
    except Exception as e:
        return False, str(e)
