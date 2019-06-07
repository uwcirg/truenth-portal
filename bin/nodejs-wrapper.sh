#!/bin/sh -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [-g gulpfile] [nodejs_command]

   -h
          Show this help message

    nodejs_command
          NodeJS command to run

    NodeJS wrapper

    Runs NodeJS tools with node_env, creating virtual environments as necessary
USAGE
}


setup_python_venv() {
    # Setup a python virtual environment on the given path, if not present
    local default_python_venv_path="${repo_root}/env"
    local python_venv_path="${1:-$default_python_venv_path}"
    if [ -d "${python_venv_path}" ]; then
        # Exit early if python virtual environment exists
        return
    fi

    echo "Creating new Python virtual environment: ${python_venv_path}"
    if command -v virtualenv; then
        virtualenv "${python_venv_path}"
    else
        python3 -m venv "${python_venv_path}"
    fi

}


setup_node_venv() {
    if command -v npm; then
        # Exit early if npm already installed
        return
    fi

    setup_python_venv

    # Setup a virtual environment for NodeJS on the given path, if not present
    local default_node_venv_path="${repo_root}/node_env"
    local node_venv_path="${2:-$default_node_venv_path}"
    if [ -d "${node_venv_path}" ]; then
        # Exit early if node_env virtual environment exists
        return
    fi

    # Use existing python virtual environment to install nodeenv module
    local default_python_venv_path="${repo_root}/env"
    local python_venv_path="${1:-$default_python_venv_path}"
    echo "Activating python virtual environment..."
    . "${python_venv_path}/bin/activate"

    echo "Installing node_env"
    pip install nodeenv

    echo "Creating new virtual environment for NodeJS: ${node_venv_path}"
    nodeenv "${node_venv_path}"

    deactivate
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

# Setup virtual environments
node_venv="${repo_root}/node_env"
setup_node_venv "" "$node_venv"

if [ -f "${node_venv}/bin/activate" ]; then
    . "${node_venv}/bin/activate"
    echo "Activating NodeJS virtual environment..."
fi


echo "Installing NodeJS dependencies..."
npm --prefix "${repo_root}/portal" install --no-progress --quiet

PATH="${PATH}:${repo_root}/portal/node_modules/gulp/bin"

nodejs_command="$@"
echo "Running command: '${nodejs_command}'..."
$nodejs_command
