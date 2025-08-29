# Use the Fedora 42 image from Quay.io
FROM quay.io/fedora/fedora:42

# Install other dependencies
RUN dnf -y update && \
    dnf install -y wget && \
    wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/1.14/gosu-amd64" && \
    chmod +x /usr/local/bin/gosu && \
    dnf remove -y wget && \
    dnf clean all

# Install PostgreSQL 17 server, and client. This step automatically creates the 'postgres' user.
RUN dnf -y install postgresql17-server postgresql17-contrib && \
    dnf clean all

# Set environment variable for the PostgreSQL data directory
ENV PGDATA /var/lib/pgsql/data/17

# Create the PGDATA and initdb.d directories and set permissions
# The 'postgres' user already exists from the previous step.
RUN mkdir -p "$PGDATA" /entrypoint-initdb.d && \
    chown -R postgres:postgres "$PGDATA" /entrypoint-initdb.d

# Create a directory for PostgreSQL lock and socket files and set permissions.
RUN mkdir -p /var/run/postgresql && chown -R postgres:postgres /var/run/postgresql

# Expose the default PostgreSQL port
EXPOSE 5432

# Set the PGDATA and initdb.d paths as volumes for data persistence
VOLUME "$PGDATA" /entrypoint-initdb.d

# Copy the entrypoint script into the container and make it executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Copy custom configuration files to a temporary location
# They will be moved into PGDATA by the entrypoint script
COPY postgresql.conf /tmp/postgresql.conf
COPY pg_hba.conf /tmp/pg_hba.conf
RUN chown -R postgres:postgres /tmp/postgresql.conf /tmp/pg_hba.conf

# The ENTRYPOINT will execute our script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default arguments to the entrypoint script
CMD ["postgres"]