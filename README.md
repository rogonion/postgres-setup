# postgres-setup

A utility for creating a customized, rootless [PostgreSQL](https://www.postgresql.org/) container image with the option
of including extensions from custom compiled ones to [contrib](https://www.postgresql.org/docs/current/contrib.html).

**Base Image:** [openSUSE Leap 16.0](https://registry.opensuse.org/cgi-bin/cooverview)  
**PostgreSQL Version:** 18.1 (Compiled from source)

## Pre-requisites

**OS:** Linux-based.

<table>
    <caption>Required Tools</caption>
    <thead>
        <tr>
            <th>Package</th>
            <th>Version</th>
            <th>Notes</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Python</td>
            <td>3.13+</td>
            <td>
                <p>Core language the CLI tool is written in.</p>
            </td>
        </tr>
        <tr>
            <td><a href="https://python-poetry.org/docs/">Poetry</a></td>
            <td>2.2.1+</td>
            <td>
                <p>Project dependency manager.</p>
            </td>
        </tr>
        <tr>
            <td><a href="https://buildah.io/">Buildah</a></td>
            <td>1.41.5+</td>
            <td>
                <p>Used to programmatically create OCI-compliant container images without a daemon.</p>
            </td>
        </tr>
        <tr>
            <td><a href="https://taskfile.dev/">Taskfile</a></td>
            <td>3.46.3+</td>
            <td>
                <p>Optional. You can use the provided <a href="taskw">shell script wrapper</a> (<code>./taskw</code>) which scopes the binary to the project.</p>
            </td>
        </tr>
    </tbody>
</table>

## Usage

List available tasks:

```shell
./taskw --list
```

Setup python virtual environment and install dependencies:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY init
```

View CLI tool options and build help:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY run -- --help
```

### Example

Build postgres binaries from source:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY run -- containers core build
```

Build postgis extension:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY run -- containers extensions postgis,pgvector,rum build
```

Build postgres runtime with postgis extension:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY run -- containers runtime build --extensions postgis
```

Sample script to run the built postgres container using `podman`.

```shell
#!/bin/bash

CONTAINER="postgres18.1"
NETWORK="tumbleweed"
NETWORK_ALIAS="postgres18.1"
CONTAINER_UID=26
HOST_PORT=5432
VOLUME="postgres"
ENV_POSTGRES_PASSWORD="postgres2025"
IMAGE="localhost/postgres:18.1"

podman volume exists $VOLUME || podman volume create $VOLUME

podman unshare chown -R $CONTAINER_UID:$CONTAINER_UID $(podman volume inspect $VOLUME --format '{{.Mountpoint}}')

podman run -d \
        --name $CONTAINER \
        --network $NETWORK \
        --network-alias $NETWORK_ALIAS \
        --user $CONTAINER_UID:$CONTAINER_UID \
        -p $HOST_PORT:5432 \
        -v $VOLUME:/var/lib/pgsql/data \
        -e POSTGRES_PASSWORD="$ENV_POSTGRES_PASSWORD" \
        $IMAGEp
```

## Application Container Image Features

### Extensions

Postgres provides a comprehensive set of extensions via its `contrib` package which is built by default.

In addition, an additional set of extensions that have to be built/sourced elsewhere are provided by the CLI tool.

Below is a sample set of extensions grouped by use-cases.

#### Geospatial

<table>
    <thead>
        <th>Extension</th>
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody> 
        <tr> 
            <td><a href="https://postgis.net/">postgis</a></td> 
            <td>3.6.1</td> 
            <td>
                <p>Adds geospatial capabilities.</p>
                <p>Provides <code>geometry</code> and <code>geography</code> types.</p>
            </td>
        </tr>
        <tr> 
            <td>postgis topology</td> 
            <td></td> 
            <td>Manage topological data (shared boundaries between shapes)</td>
        </tr>
        <tr>
            <td>address_standardizer</td>
            <td></td>
            <td>Normalizes address strings into parts (street, city, zip)</td>
        </tr>
    </tbody>
</table>

#### Semantic & AI Search

<table>
    <thead>
        <th>Extension</th>
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody> 
        <tr> 
            <td><a href="https://github.com/pgvector/pgvector">pgvector</a></td> 
            <td>0.8.1</td> 
            <td>
                <p>Adds vector search capabilities.</p>
                <p>Provides <code>vector</code> type, and <code>hnsw</code> and <code>ivfflat</code> indexes.</p>
            </td>
        </tr>
        <tr> 
            <td>btree_gin</td> 
            <td></td> 
            <td>Manage topological data (shared boundaries between shapes)</td>
        </tr>
        <tr>
            <td>address_standardizer</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Allows standard types (int, uuid) to be indexed in GIN.</p> 
                <p>Combine vectory query with hard scalar filter.</p>
            </td>
        </tr>
    </tbody>
</table>

#### Advanced Text Search

<table>
    <thead>
        <th>Extension</th>
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody> 
        <tr> 
            <td><a href="https://github.com/postgrespro/rum">rum</a></td> 
            <td>1.3.15</td> 
            <td>
                <p><code>RUM</code> Index - Inverted index that stores weights and positions alongside terms.</p>
                <p>Good for fast ranking for search results by relevance or timestamps.</p>
            </td>
        </tr>
        <tr>
            <td>pg_trgm</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Break text into 3 character trigrams for similarity comparison.</p>
                <p>Good for fuzzy search (suggestions) and typo tolerance.</p>
            </td>
        </tr>
        <tr>
            <td>fuzzystrmatch</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Algorithms for string phonetics (soundex, metaphone, levenshtein).</p>
                <p>Good for matching names that sound similar but are spelled differently.</p>
            </td>
        </tr>
        <tr>
            <td>unaccent</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Removes accents/diacritics from text.</p>
            </td>
        </tr>
    </tbody>
</table>

#### Performance and maintenance

<table>
    <thead>
        <th>Extension</th>
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody>
        <tr>
            <td>pg_stat_statements</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Tracks execution statistics of all SQL statements.</p>
            </td>
        </tr>
        <tr>
            <td>pg_buffercache</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Inspects the contents of the shared buffer cache (RAM).</p>
                <p>Debugging why specific tables are "hot" or getting evicted from memory.</p>
            </td>
        </tr>
        <tr>
            <td>auto_explain</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Automatically logs the execution plan of slow queries.</p>
            </td>
        </tr>
        <tr>
            <td>pg_visibility</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Inspects the visibility map and page-level details.</p>
            </td>
        </tr>
    </tbody>
</table>

#### Data Types & Utilities

<table>
    <thead>
        <th>Extension</th>
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody>
        <tr>
            <td>uuid-ossp</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Generates UUIDs (v1, v4, etc.).</p>
            </td>
        </tr>
        <tr>
            <td>citext</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Case-insensitive text type.</p>
                <p>Emails/Usernames: Handles User@Example.com = user@example.com automatically.</p>
            </td>
        </tr>
        <tr>
            <td>hstore</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Key-value store within a single column.</p>
            </td>
        </tr>
        <tr>
            <td>pgcrypto</td>
            <td>Built-in via <code>contrib</code></td>
            <td>
                <p>Cryptographic functions (hashing, encryption).</p>
            </td>
        </tr>
    </tbody>
</table>

### Ports

<table>
    <thead>
        <th>Port</th>
        <th>Purpose</th> 
    </thead> 
    <tbody>
        <tr> 
            <td><code>5432</code></td> 
            <td><strong>Default PostgreSQL Port.</strong> Map this to your host using <code>-p 5432:5432</code> to access the database.</td>
        </tr>
    </tbody>
</table>

### Volumes

<table>
    <thead>
        <th>Path</th>
        <th>Purpose</th>
    </thead>
    <tbody> 
        <tr> 
            <td><code>/var/lib/pgsql/data/18</code></td> 
            <td><strong>Data Directory.</strong> Stores all database files (tables, WAL, indexes).
            <strong>Note:</strong> Ensure you mount a volume here to persist data across restarts.</td>
        </tr>
    </tbody>
</table>

### Environment variables

<table>
    <thead> 
        <th>Name</th>
        <th>Default</th>
        <th>Purpose</th>
    </thead>
    <tbody>
        <tr>
            <td><code>POSTGRES_USER</code></td>
            <td><code>postgres</code></td>
            <td>Sets the superuser for the database.</td>
        </tr>
        <tr>
            <td><code>POSTGRES_PASSWORD</code></td>
            <td>(None)</td>
            <td>Sets the password for the superuser. <strong>Highly Recommended</strong> for security.</td>
        </tr>
        <tr>
            <td><code>PGDATA</code></td>
            <td><code>/var/lib/pgsql/data/18</code></td>
            <td>Internal pointer to the data volume. Generally should not be changed.</td>
        </tr>
    </tbody>
</table>

