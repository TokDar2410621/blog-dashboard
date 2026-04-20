"""
Blog adapter: auto-detect blog tables in a site's database and create
SQL views that map them to the standard blog_* names expected by the dashboard.

This allows the dashboard to work with any site, regardless of table naming
(blog_blogpost, marketing_blogpost, articles_post, etc.).
"""

from django.db import connections


def detect_blog_tables(alias):
    """
    Scan a site's database for blog-like tables.
    Returns detection result with suggested config.
    """
    with connections[alias].cursor() as cursor:
        cursor.execute("""
            SELECT table_name, table_type FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        all_tables = {row[0]: row[1] for row in cursor.fetchall()}

    tables = list(all_tables.keys())

    # Check if blog_blogpost exists as a real table with data
    if 'blog_blogpost' in all_tables and all_tables['blog_blogpost'] == 'BASE TABLE':
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM blog_blogpost")
            count = cursor.fetchone()[0]
            if count > 0:
                return {
                    'status': 'standard',
                    'message': f'Tables blog standard detectees avec {count} articles.',
                    'post_count': count,
                    'config': None,
                }

    # Look for alternative post tables
    candidates = []
    for table in tables:
        if table.startswith('blog_') or table.startswith('django_'):
            continue
        if 'post' not in table.lower() and 'article' not in table.lower():
            continue

        # Skip join tables (e.g., marketing_blogpost_tags)
        if table.endswith('_tags') or table.endswith('_categories'):
            continue

        with connections[alias].cursor() as cursor:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s ORDER BY ordinal_position
            """, [table])
            columns = [row[0] for row in cursor.fetchall()]

            if all(col in columns for col in ['title', 'slug', 'content']):
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                candidates.append({
                    'table': table,
                    'columns': columns,
                    'count': count,
                })

    if not candidates:
        return {
            'status': 'none',
            'message': 'Aucune table blog detectee.',
            'config': None,
        }

    # Pick the best candidate (most rows)
    best = max(candidates, key=lambda c: c['count'])
    columns = best['columns']

    # Guess the prefix from the table name
    # e.g., "marketing_blogpost" -> look for marketing_blogcategory, marketing_blogtag
    post_table = best['table']
    prefix_parts = post_table.replace('blogpost', '').replace('blog_post', '').replace('post', '').rstrip('_')

    config = {
        'post_table': post_table,
        'field_map': {},
    }

    # Detect column mappings
    if 'featured_image' in columns and 'cover_image' not in columns:
        config['field_map']['cover_image'] = 'featured_image'

    if 'author_id' in columns and 'author' not in columns:
        config['author_mode'] = 'fk'
        config['author_fk_column'] = 'author_id'

    # Detect category table
    for t in tables:
        if t == 'blog_category':
            continue
        if 'category' in t.lower() and not t.endswith('_tags'):
            if prefix_parts and t.startswith(prefix_parts):
                config['category_table'] = t
                break

    # Detect tag table
    for t in tables:
        if t == 'blog_tag':
            continue
        if 'tag' in t.lower() and 'category' not in t.lower() and not t.endswith('_tags'):
            if prefix_parts and t.startswith(prefix_parts):
                config['tag_table'] = t
                break

    # Detect join table
    for t in tables:
        if t == 'blog_blogpost_tags':
            continue
        if t.endswith('_tags') and post_table.split('post')[0] in t:
            config['post_tags_table'] = t
            with connections[alias].cursor() as cursor:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = %s
                      AND column_name NOT IN ('id', 'blogpost_id')
                    ORDER BY ordinal_position
                """, [t])
                fk_cols = [row[0] for row in cursor.fetchall()]
                if fk_cols:
                    config['post_tag_fk'] = fk_cols[0]
            break

    # Detect content format (HTML vs Markdown)
    with connections[alias].cursor() as cursor:
        cursor.execute(f"""
            SELECT content FROM "{post_table}"
            WHERE content IS NOT NULL AND content != ''
            LIMIT 5
        """)
        samples = [row[0] for row in cursor.fetchall()]

    import re
    html_count = sum(
        1 for s in samples
        if re.search(r'<(p|div|h[1-6]|ul|ol|table|figure|section|article)\b', s, re.IGNORECASE)
    )
    if html_count > len(samples) / 2:
        config['content_format'] = 'html'

    return {
        'status': 'detected',
        'message': f'{best["count"]} articles trouves dans "{post_table}".',
        'post_count': best['count'],
        'config': config,
        'candidates': [{'table': c['table'], 'count': c['count']} for c in candidates],
    }


def setup_blog_views(alias, config):
    """
    Create SQL views + INSTEAD OF triggers in the site's database
    that map custom blog tables to the standard blog_* names.
    """
    post_table = config['post_table']
    category_table = config.get('category_table', '')
    tag_table = config.get('tag_table', '')
    post_tags_table = config.get('post_tags_table', '')
    post_tag_fk = config.get('post_tag_fk', 'tag_id')
    field_map = config.get('field_map', {})
    author_mode = config.get('author_mode', 'field')
    author_fk_col = config.get('author_fk_column', 'author_id')
    cover_col = field_map.get('cover_image', 'cover_image')

    with connections[alias].cursor() as cursor:
        # ── Cleanup: drop existing blog_* objects ──
        _drop_blog_objects(cursor)

        # ── Get source table column info ──
        source_cols = _get_columns(cursor, post_table)

        # ── CATEGORY ──
        if category_table:
            _create_category_view(cursor, category_table)
        else:
            _create_category_table(cursor)

        # ── TAG ──
        if tag_table:
            _create_tag_view(cursor, tag_table)
        else:
            _create_tag_table(cursor)

        # ── BLOGPOST ──
        _create_post_view(cursor, post_table, source_cols,
                          cover_col, author_mode, author_fk_col)
        _create_post_triggers(cursor, post_table, cover_col,
                              author_mode, author_fk_col)

        # ── BLOGPOST_TAGS ──
        if post_tags_table:
            _create_tags_junction_view(cursor, post_tags_table, post_tag_fk)
        else:
            _create_tags_junction_table(cursor)

        # Remove stale migration entries
        cursor.execute("DELETE FROM django_migrations WHERE app = 'blog'")

    return True


# ─── Internal helpers ───────────────────────────────────────────────


def _drop_blog_objects(cursor):
    """Drop all blog_* tables/views and trigger functions."""
    for tbl in ['blog_blogpost_tags', 'blog_blogpost', 'blog_category', 'blog_tag']:
        cursor.execute("""
            SELECT table_type FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        """, [tbl])
        row = cursor.fetchone()
        if row:
            kind = 'VIEW' if row[0] == 'VIEW' else 'TABLE'
            cursor.execute(f'DROP {kind} IF EXISTS "{tbl}" CASCADE')

    funcs = [
        'blog_blogpost_insert_fn', 'blog_blogpost_update_fn', 'blog_blogpost_delete_fn',
        'blog_category_insert_fn', 'blog_category_update_fn', 'blog_category_delete_fn',
        'blog_tag_insert_fn', 'blog_tag_delete_fn',
        'blog_blogpost_tags_insert_fn', 'blog_blogpost_tags_delete_fn',
    ]
    for fn in funcs:
        cursor.execute(f'DROP FUNCTION IF EXISTS {fn}() CASCADE')


def _get_columns(cursor, table):
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, [table])
    return [row[0] for row in cursor.fetchall()]


# ── Category ──

def _create_category_view(cursor, table):
    cat_cols = _get_columns(cursor, table)
    desc = 'description' if 'description' in cat_cols else "'' as description"
    if desc == 'description':
        desc = "COALESCE(description, '')"
    cursor.execute(f"""
        CREATE VIEW blog_category AS
        SELECT id, name, slug, {desc} as description FROM "{table}"
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_category_insert_fn() RETURNS TRIGGER AS $$
        DECLARE v_id BIGINT;
        BEGIN
            INSERT INTO "{table}" (name, slug, description)
            VALUES (NEW.name, NEW.slug, NEW.description)
            RETURNING id INTO v_id;
            NEW.id := v_id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_category_insert_trigger
        INSTEAD OF INSERT ON blog_category
        FOR EACH ROW EXECUTE FUNCTION blog_category_insert_fn()
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_category_update_fn() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE "{table}" SET name=NEW.name, slug=NEW.slug, description=NEW.description
            WHERE id = OLD.id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_category_update_trigger
        INSTEAD OF UPDATE ON blog_category
        FOR EACH ROW EXECUTE FUNCTION blog_category_update_fn()
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_category_delete_fn() RETURNS TRIGGER AS $$
        BEGIN DELETE FROM "{table}" WHERE id = OLD.id; RETURN OLD;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_category_delete_trigger
        INSTEAD OF DELETE ON blog_category
        FOR EACH ROW EXECUTE FUNCTION blog_category_delete_fn()
    """)


def _create_category_table(cursor):
    cursor.execute("""
        CREATE TABLE blog_category (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            description TEXT DEFAULT ''
        )
    """)


# ── Tag ──

def _create_tag_view(cursor, table):
    cursor.execute(f"""
        CREATE VIEW blog_tag AS SELECT id, name FROM "{table}"
    """)
    tag_cols = _get_columns(cursor, table)
    slug_val = "NEW.name" if 'slug' in tag_cols else None
    extra_cols = ', slug' if slug_val else ''
    extra_vals = f', {slug_val}' if slug_val else ''
    cursor.execute(f"""
        CREATE FUNCTION blog_tag_insert_fn() RETURNS TRIGGER AS $$
        DECLARE v_id BIGINT;
        BEGIN
            INSERT INTO "{table}" (name{extra_cols})
            VALUES (NEW.name{extra_vals})
            RETURNING id INTO v_id;
            NEW.id := v_id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_tag_insert_trigger
        INSTEAD OF INSERT ON blog_tag
        FOR EACH ROW EXECUTE FUNCTION blog_tag_insert_fn()
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_tag_delete_fn() RETURNS TRIGGER AS $$
        BEGIN DELETE FROM "{table}" WHERE id = OLD.id; RETURN OLD;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_tag_delete_trigger
        INSTEAD OF DELETE ON blog_tag
        FOR EACH ROW EXECUTE FUNCTION blog_tag_delete_fn()
    """)


def _create_tag_table(cursor):
    cursor.execute("""
        CREATE TABLE blog_tag (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL
        )
    """)


# ── BlogPost ──

def _create_post_view(cursor, table, cols, cover_col, author_mode, author_fk_col):
    # Author
    if author_mode == 'fk':
        author_sel = "COALESCE(u.username, 'Admin') as author"
        join = f'LEFT JOIN auth_user u ON u.id = bp."{author_fk_col}"'
    else:
        author_sel = 'bp.author'
        join = ''

    cover_sel = f'COALESCE(bp."{cover_col}", \'\')' if cover_col in cols else "''"
    reading = 'COALESCE(bp.reading_time, 5)' if 'reading_time' in cols else '5'
    views = 'COALESCE(bp.view_count, 0)' if 'view_count' in cols else '0'
    excerpt = 'bp.excerpt' if 'excerpt' in cols else "''"

    if 'published_at' in cols:
        pub = 'bp.published_at::date'
    else:
        pub = 'bp.created_at::date'

    # New fields (language, translation_group) default to sensible values
    # when the underlying table doesn't have them. Triggers ignore them on write.
    lang_sel = "'fr'::varchar(2) as language"
    tg_sel = "gen_random_uuid()::uuid as translation_group"
    if 'language' in cols:
        lang_sel = "COALESCE(bp.language, 'fr') as language"
    if 'translation_group' in cols:
        tg_sel = "COALESCE(bp.translation_group, gen_random_uuid())::uuid as translation_group"

    cursor.execute(f"""
        CREATE VIEW blog_blogpost AS
        SELECT
            bp.id, bp.title, bp.slug,
            {excerpt} as excerpt,
            bp.content,
            {author_sel},
            {cover_sel} as cover_image,
            {reading} as reading_time,
            false as featured,
            bp.status,
            NULL::timestamptz as scheduled_at,
            {views} as view_count,
            {lang_sel},
            {tg_sel},
            {pub} as published_at,
            bp.created_at,
            bp.updated_at,
            bp.category_id
        FROM "{table}" bp
        {join}
    """)


def _create_post_triggers(cursor, table, cover_col, author_mode, author_fk_col):
    # ── INSERT ──
    if author_mode == 'fk':
        declare = 'v_user_id INTEGER;'
        lookup = f"""
            SELECT id INTO v_user_id FROM auth_user WHERE username = NEW.author LIMIT 1;
            IF v_user_id IS NULL THEN
                SELECT id INTO v_user_id FROM auth_user ORDER BY id LIMIT 1;
            END IF;"""
        a_col = f'"{author_fk_col}"'
        a_val = 'v_user_id'
    else:
        declare = ''
        lookup = ''
        a_col = 'author'
        a_val = 'NEW.author'

    cursor.execute(f"""
        CREATE FUNCTION blog_blogpost_insert_fn() RETURNS TRIGGER AS $$
        DECLARE
            v_new_id BIGINT;
            {declare}
        BEGIN
            {lookup}
            INSERT INTO "{table}" (
                title, slug, excerpt, content, {a_col},
                "{cover_col}", reading_time, status, view_count,
                published_at, created_at, updated_at, category_id
            ) VALUES (
                NEW.title, NEW.slug, NEW.excerpt, NEW.content, {a_val},
                NEW.cover_image, COALESCE(NEW.reading_time, 5), NEW.status,
                COALESCE(NEW.view_count, 0), COALESCE(NEW.published_at, CURRENT_DATE),
                COALESCE(NEW.created_at, NOW()), COALESCE(NEW.updated_at, NOW()),
                NEW.category_id
            ) RETURNING id INTO v_new_id;
            NEW.id := v_new_id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_blogpost_insert_trigger
        INSTEAD OF INSERT ON blog_blogpost
        FOR EACH ROW EXECUTE FUNCTION blog_blogpost_insert_fn()
    """)

    # ── UPDATE ──
    if author_mode == 'fk':
        u_declare = 'v_user_id INTEGER;'
        u_lookup = 'SELECT id INTO v_user_id FROM auth_user WHERE username = NEW.author LIMIT 1;'
        u_author = f'{a_col} = CASE WHEN v_user_id IS NOT NULL THEN v_user_id ELSE "{table}".{author_fk_col} END'
    else:
        u_declare = ''
        u_lookup = ''
        u_author = 'author = NEW.author'

    cursor.execute(f"""
        CREATE FUNCTION blog_blogpost_update_fn() RETURNS TRIGGER AS $$
        DECLARE {u_declare}
        BEGIN
            {u_lookup}
            UPDATE "{table}" SET
                title = NEW.title, slug = NEW.slug, excerpt = NEW.excerpt,
                content = NEW.content, {u_author},
                "{cover_col}" = NEW.cover_image,
                reading_time = NEW.reading_time, status = NEW.status,
                view_count = NEW.view_count, published_at = NEW.published_at,
                updated_at = NOW(), category_id = NEW.category_id
            WHERE id = OLD.id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_blogpost_update_trigger
        INSTEAD OF UPDATE ON blog_blogpost
        FOR EACH ROW EXECUTE FUNCTION blog_blogpost_update_fn()
    """)

    # ── DELETE ──
    cursor.execute(f"""
        CREATE FUNCTION blog_blogpost_delete_fn() RETURNS TRIGGER AS $$
        BEGIN DELETE FROM "{table}" WHERE id = OLD.id; RETURN OLD;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_blogpost_delete_trigger
        INSTEAD OF DELETE ON blog_blogpost
        FOR EACH ROW EXECUTE FUNCTION blog_blogpost_delete_fn()
    """)


# ── BlogPost Tags junction ──

def _create_tags_junction_view(cursor, table, tag_fk):
    cursor.execute(f"""
        CREATE VIEW blog_blogpost_tags AS
        SELECT id::bigint, blogpost_id, "{tag_fk}" as tag_id FROM "{table}"
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_blogpost_tags_insert_fn() RETURNS TRIGGER AS $$
        DECLARE v_id BIGINT;
        BEGIN
            INSERT INTO "{table}" (blogpost_id, "{tag_fk}")
            VALUES (NEW.blogpost_id, NEW.tag_id)
            RETURNING id INTO v_id;
            NEW.id := v_id;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_blogpost_tags_insert_trigger
        INSTEAD OF INSERT ON blog_blogpost_tags
        FOR EACH ROW EXECUTE FUNCTION blog_blogpost_tags_insert_fn()
    """)
    cursor.execute(f"""
        CREATE FUNCTION blog_blogpost_tags_delete_fn() RETURNS TRIGGER AS $$
        BEGIN DELETE FROM "{table}" WHERE id = OLD.id; RETURN OLD;
        END; $$ LANGUAGE plpgsql
    """)
    cursor.execute("""
        CREATE TRIGGER blog_blogpost_tags_delete_trigger
        INSTEAD OF DELETE ON blog_blogpost_tags
        FOR EACH ROW EXECUTE FUNCTION blog_blogpost_tags_delete_fn()
    """)


def _create_tags_junction_table(cursor):
    cursor.execute("""
        CREATE TABLE blog_blogpost_tags (
            id BIGSERIAL PRIMARY KEY,
            blogpost_id BIGINT NOT NULL,
            tag_id BIGINT NOT NULL,
            UNIQUE(blogpost_id, tag_id)
        )
    """)
