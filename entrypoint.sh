#!/bin/bash
set -e

# --- Environment Variable Handling (Mimics Official Image) ---

# Set the default PostgresSQL user to 'postgres' if not specified
export PGUSER="${PGUSER:-postgres}"

# Set the default database name to 'postgres' if not specified
export POSTGRES_DB="${POSTGRES_DB:-postgres}"

# Require a password to be set for the superuser. This is a security best practice.
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo >&2 'Error: POSTGRES_PASSWORD not set.'
    echo >&2 'You must specify POSTGRES_PASSWORD to run this image.'
    exit 1
fi

# Set the data directory based on user-provided ENV or a hardcoded default.
export PGDATA="${PGDATA:-/var/lib/pgsql/data/17}"

# --- Change ownership of the data directory ---
# This ensures the 'postgres' user can write to the mounted volume
chown -R postgres:postgres "$PGDATA"

# --- Database Initialization Logic ---

# Check if PGDATA is an empty or uninitialized directory
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "Initializing a new PostgresSQL database..."
    gosu postgres initdb -D "$PGDATA" -E UTF8

    # Symlink the PGDG extension directory to the default PostgresSQL location.
    # This must be done before creating the extension.
    echo "Creating symlinks for PostgresSQL 17 extensions..."
    ln -s /usr/pgsql-17/share/extension/* /usr/share/pgsql/extension/

    # Symlink the PGDG shared libraries directory to the default PostgresSQL location.
    # This must be done before creating the extension.
    echo "Creating symlinks for PostgresSQL 17 shared libraries..."
    ln -s /usr/pgsql-17/lib/* /usr/lib64/pgsql/

    # Symlink the PGDG contrib directory to the default PostgresSQL location.
    # This must be done before creating the extension.
    echo "Creating symlinks for PostgresSQL 17 contrib..."
    ln -s /usr/pgsql-17/share/contrib/* /usr/share/pgsql/contrib/

    # --- Change ownership to the 'postgres' user ---
    echo "Adjusting permissions for PGDG files..."
    chown -R postgres:postgres /usr/pgsql-17

    # Move custom configuration files into PGDATA
    echo "Moving custom configuration files into $PGDATA..."
    gosu postgres mv /tmp/postgresql.conf "$PGDATA/postgresql.conf"
    gosu postgres mv /tmp/pg_hba.conf "$PGDATA/pg_hba.conf"

    # Start the server temporarily to create the user and database
    echo "Starting temporary PostgresSQL server to create initial user and database..."
    gosu postgres pg_ctl start -D "$PGDATA" -o "-c listen_addresses='localhost'" -w -t 60

    if [ "$POSTGRES_DB" != "postgres" ]; then
      # Create the specified database
      echo "Creating database '$POSTGRES_DB'..."
      gosu postgres createdb -E UTF8 "$POSTGRES_DB"
    fi

    if [ "$PGUSER" != 'postgres' ]; then
      # Create the user and set their password
      echo "Creating user '$PGUSER' and setting password..."
      gosu postgres psql -d "$POSTGRES_DB" -U postgres -c "CREATE USER $PGUSER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';"
      gosu postgres psql -d "$POSTGRES_DB" -U postgres -c "ALTER USER $PGUSER WITH SUPERUSER;"
      gosu postgres psql -d "$POSTGRES_DB" -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $PGUSER;"
    else
      echo "Setting password for default 'postgres' user..."
      gosu postgres psql -d "$POSTGRES_DB" -c "ALTER USER $PGUSER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';"
    fi

    # Stop the temporary server
    echo "Stopping temporary PostgresSQL server..."
    gosu postgres pg_ctl stop -D "$PGDATA" -m fast -w

    # Run custom initialization scripts
    if [ -d "/entrypoint-initdb.d" ] && [ -n "$(find "/entrypoint-initdb.d" -mindepth 1 -maxdepth 1)" ]; then
        echo "Running custom initialization scripts..."
        gosu postgres pg_ctl start -D "$PGDATA" -o "-c listen_addresses='localhost'" -w -t 60

        for f in /entrypoint-initdb.d/*; do
          case "$f" in
            *.sh)  echo "$0: running $f"; "$f" ;;
            *.sql) echo "$0: running $f"; gosu postgres psql -d "$POSTGRES_DB" -f "$f" ;;
            *.sql.gz) echo "$0: running $f"; gunzip -c "$f" | gosu postgres psql -d "$POSTGRES_DB" ;;
            *)     echo "$0: ignoring $f" ;;
          esac
        done

        gosu postgres pg_ctl stop -D "$PGDATA" -m fast -w
    fi
else
    echo "PostgresSQL database directory appears to contain a database; Skipping initialization."
fi

# The final command: run the main PostgresSQL server process
echo "...Starting PostgresSQL server..."
exec gosu postgres "$@"