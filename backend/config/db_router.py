class BlogRouter:
    """
    Route blog models to the appropriate database.
    Blog models go to the site-specific database when using .using(),
    and should NOT be migrated on the default database.
    sites_mgmt models always go to default.
    """

    BLOG_MODELS = {'blogpost', 'category', 'tag'}

    def db_for_read(self, model, **hints):
        # Blog models are always accessed via .using(alias) explicitly
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'blog':
            # Only migrate blog tables on site databases (site_*), not default
            return db != 'default'
        # All other apps (auth, sites_mgmt, etc.) only on default
        return db == 'default'
