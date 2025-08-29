# postgres-setup

A utility for creating a postgres container image with the option of including a set of extensions.

[Fedora](https://quay.io/repository/fedora/fedora?tab=tags) is used as the base of the images.

Pre-requisites:

- [Podman](https://podman.io/) or [Docker](https://www.docker.com/).
- [Python](https://www.python.org/) - Created with version 3.13.
- [Poetry](https://python-poetry.org/docs/).

Run `poetry install` to set up the environment.

## Usage

Run `poetry run python build.py -h` or `poetry run python build.py --help` for script usage.

The list of extensions can be found [here](extensions/README.md).

The basic flow of the [script](build.py) is as follows:
1. Load the [base](Containerfile) `Containerfile` into a temporary file.
2. If extensions are specified in the arguments:
   1. Search for each extension module by name and version.
   2. If found, execute the extension `build_and_get_snippet` function. The function typically performs the following duties:
      1. Optionally build the container image that compiles the extension from source.
      2. Return the `Containerfile` snippet which may contain commands such as:
         1. copy files from resulting build extension image.
         2. install extension package.
         3. install dependency packages required by extension.
   3. Append the snippets to the temporary `Containerfile`.
3. Build the final temporary `Containerfile`.

## Application Container Image Features

### Ports

<table>
    <thead>
        <th>Port</th>
        <th>Purpose</th>
    </thead>
    <tbody>
        <tr>
            <td><code>5432</code></td>
            <td>This is the <strong>default TCP port</strong> on which the PostgreSQL server listens for connections. To access the database from outside the container, this port must be mapped to a port on the host machine using the <code>-p</code> flag in the <code>docker run</code> command.</td>   
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
            <td><code>/var/lib/pgsql/data/17</code></td>
            <td>This is the <strong>data directory</strong> where all PostgreSQL files, including tables, indexes, and transaction logs, are stored. Mounting a volume to this path is crucial for data persistence.</td>   
        </tr>
        <tr>
            <td><code>/entrypoint-initdb.d</code></td>
            <td>customize the database setup when a container is started for the very first time. You can place shell scripts (.sh), SQL scripts (.sql), and compressed SQL files (.sql.gz) in a local directory on your host machine and mount it to <code>/entrypoint-initdb.d</code> inside the container.</td>
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
            <td></td>
            <td>Sets the password for the superuser. This is a required variable for security.</td>   
        </tr>
        <tr>
            <td><code>POSTGRES_DB</code></td>
            <td></td>
            <td>Specifies the name of the database to be created during initialization.</td>   
        </tr>
        <tr>
            <td><code>PGDATA</code></td>
            <td></td>
            <td>Overrides the default location for the data directory.</td>   
        </tr>
    </tbody>
</table>

