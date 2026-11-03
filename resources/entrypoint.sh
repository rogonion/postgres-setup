#!/bin/bash
set -e

# --- 1. Environment Defaults ---
# Default to SUSE versioned path if not set
export PGDATA="${PGDATA:-/var/lib/pgsql/data/18}"
export PGUSER="${PGUSER:-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-postgres}"
# The safe location where we baked the configs during build
CONFIG_SOURCE="/usr/share/postgresql/config"

if [ "$#" -eq 0 ]; then
    set -- postgres
fi

if [ "${1#-}" != "$1" ]; then
    set -- postgres "$@"
fi

# --- 2. Security Check ---
# Only enforce password if we are initializing a new DB
# We check if PGDATA is empty or missing
if [ -z "$POSTGRES_PASSWORD" ] && [ -z "$(ls -A "$PGDATA" 2>/dev/null)" ]; then
    echo >&2 'Error: POSTGRES_PASSWORD not set.'
    echo >&2 'You must specify POSTGRES_PASSWORD to initialize this container.'
    exit 1
fi

# --- 3. Database Initialization ---
# Check if PGDATA is empty
if [ -z "$(ls -A "$PGDATA" 2>/dev/null)" ]; then
    echo "Initializing a new PostgreSQL database in $PGDATA..."

    # A. Run initdb
    # We are already the 'postgres' user, so no need for sudo/gosu
    initdb -D "$PGDATA" -E UTF8

    # B. Apply Configuration
    # Copies our custom conf files into the data directory
    if [ -d "$CONFIG_SOURCE" ]; then
        echo "Merging custom configurations..."
        cp "$CONFIG_SOURCE"/* "$PGDATA/"
        chmod 700 "$PGDATA"
        chmod 600 "$PGDATA"/postgresql.conf "$PGDATA"/pg_hba.conf
    fi

    # C. Start Temporary Server for Setup
    echo "Starting temporary server for setup..."
    # -w waits for startup to complete
    pg_ctl -D "$PGDATA" -o "-c listen_addresses='localhost'" -w start

    # D. Create Custom Database (if requested)
    if [ "$POSTGRES_DB" != "postgres" ]; then
        echo "Creating database '$POSTGRES_DB'..."
        createdb -E UTF8 "$POSTGRES_DB"
    fi

    # E. Set User/Password
    if [ "$PGUSER" != "postgres" ]; then
        echo "Creating user '$PGUSER'..."
        psql -d "$POSTGRES_DB" -U postgres -c "CREATE USER $PGUSER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';"
        psql -d "$POSTGRES_DB" -U postgres -c "ALTER USER $PGUSER WITH SUPERUSER;"
        psql -d "$POSTGRES_DB" -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $PGUSER;"
    else
        echo "Setting password for default 'postgres' user..."
        psql -d "$POSTGRES_DB" -c "ALTER USER $PGUSER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';"
    fi

    echo "Enabling pg_stat_statements..."
    psql -d "$POSTGRES_DB" -U postgres -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

    # F. Stop Temporary Server
    echo "Stopping temporary server..."
    pg_ctl -D "$PGDATA" -m fast -w stop
else
    echo "Database directory is not empty. Skipping initialization."
fi

exec "$@"