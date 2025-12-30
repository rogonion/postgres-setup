# postgres-setup

A utility for creating a customized, rootless PostgreSQL container image with the option of including compiled
extensions like PostGIS.

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

$TASKFILE_BINARY run -- containers extensions postgis build
```

Build postgres runtime with postgis extension:

```shell
TASKFILE_BINARY="./taskw"

$TASKFILE_BINARY run -- containers runtime build --extensions postgis
```


## Application Container Image Features

### Extensions

<table>
    <thead>
        <th>Extension</th> 
        <th>Version</th> 
        <th>Description</th> 
    </thead> 
    <tbody> 
        <tr> 
            <td><code>postgis</code></td> 
            <td>3.6.1</td> 
            <td><strong>Spatial Database Extender.</strong> Includes support for geographic objects, compiled with GDAL, PROJ, and GEOS.</td>
        </tr>
        <tr>
            <td><code>pg_stat_statements</code></td>
            <td>(Built-in)</td>
            <td><strong>Query Performance Monitoring.</strong> Tracks execution statistics of all SQL statements executed. Enabled by default.</td>
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

