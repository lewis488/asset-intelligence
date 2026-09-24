import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend/ (parent of alembic/) to sys.path so flat imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base  # noqa: E402
import models.user  # noqa: F401, E402
import models.asset  # noqa: F401, E402
import models.vaisala  # noqa: F401, E402
import models.vaisala_programme  # noqa: F401, E402

config = context.config
fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
