import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from letta.config import LettaConfig
from letta.orm import Base
from letta.settings import settings

# Monkey patch SQLAlchemy to handle OpenGauss version detection
def patch_sqlalchemy_version_detection():
    """Patch SQLAlchemy to treat OpenGauss as PostgreSQL 13"""
    try:
        from sqlalchemy.dialects.postgresql.base import PGDialect

        original_get_server_version_info = PGDialect._get_server_version_info

        def patched_get_server_version_info(self, connection):
            try:
                return original_get_server_version_info(self, connection)
            except Exception as e:
                print(f"[ALEMBIC PATCH] PGDialect._get_server_version_info failed: {e}")
                print("[ALEMBIC PATCH] Using PostgreSQL 13 version tuple for OpenGauss compatibility")
                return (13, 0)

        PGDialect._get_server_version_info = patched_get_server_version_info
        print("[ALEMBIC PATCH] Successfully patched PGDialect._get_server_version_info for OpenGauss.")

    except ImportError:
        print("[ALEMBIC PATCH] Could not import PGDialect, skipping patch.")
    except Exception as e:
        print(f"[ALEMBIC PATCH] An unexpected error occurred during patching: {e}")


# Apply the patch before any engine creation
patch_sqlalchemy_version_detection()

letta_config = LettaConfig.load()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

if settings.letta_pg_uri_no_default:
    config.set_main_option("sqlalchemy.url", settings.letta_pg_uri)
    print(f"Using database: ", settings.letta_pg_uri)
else:
    config.set_main_option("sqlalchemy.url", "sqlite:///" + os.path.join(letta_config.recall_storage_path, "sqlite.db"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
