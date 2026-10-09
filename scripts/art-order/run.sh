#!/usr/bin/env bash
# Shared local/CI entry point. Install requirements into Python 3.13.7 first.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo=$(cd -- "$script_dir/../.." && pwd -P)
source "$script_dir/pin.env"
export KICAD_IMAGE KICAD_VERSION_PREFIX ART_ORDER_PYTHON_VERSION

if [[ ${1:-} == --kicad-adapter ]]; then
  shift
  # Keep host absolute paths unchanged, including Python's /tmp intermediates.
  # No network, credentials, or access to the rest of the host is needed by KiCad.
  exec docker run --rm --network none --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$repo,dst=$repo" \
    --mount type=bind,src=/tmp,dst=/tmp \
    --workdir "$repo" --env HOME=/tmp --entrypoint kicad-cli "$KICAD_IMAGE" "$@"
fi

python_bin=${ART_ORDER_PYTHON:-python3}
"$python_bin" - <<'PY'
import importlib.metadata
import os
import platform
expected = os.environ['ART_ORDER_PYTHON_VERSION']
if platform.python_version() != expected:
    raise SystemExit(f"Use Python {expected}; set ART_ORDER_PYTHON to its executable.")
for package, version in [('shapely', '2.1.2'), ('Pillow', '11.3.0')]:
    try:
        actual = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        actual = 'missing'
    if actual != version:
        raise SystemExit(f"Expected {package}=={version}, found {actual}; install scripts/art-order/requirements.txt.")
PY
cd "$repo"
# Bundle verification is portable and does not require a Docker daemon.
for arg in "$@"; do
  if [[ $arg == --verify-bundle ]]; then
    exec "$python_bin" artwork-resources/pcb-art/manufacturing/order_packages.py "$@"
  fi
done
command -v docker >/dev/null || { echo 'Docker is required for pinned native KiCad exports.' >&2; exit 1; }
# Outputs outside these mounts cannot be addressed by the native CLI.
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ ${args[i]} == --output ]]; then
    output=$($python_bin -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "${args[i+1]:?--output requires a path}")
    case "$output" in
      "$repo"/*|/tmp/*) args[i+1]=$output ;;
      *) echo 'Output must be within the checkout or /tmp for native CLI bind mounts.' >&2; exit 1 ;;
    esac
  fi
done
docker image inspect "$KICAD_IMAGE" >/dev/null 2>&1 || docker pull "$KICAD_IMAGE"
version=$(bash "$script_dir/run.sh" --kicad-adapter version)
[[ $version == "$KICAD_VERSION_PREFIX" ]] || { echo "Unexpected KiCad version: $version" >&2; exit 1; }
export ART_ORDER_KICAD_VERSION="$version"
adapter=$(mktemp /tmp/art-order-kicad.XXXXXX)
trap 'rm -f -- "$adapter"' EXIT
printf '#!/usr/bin/env bash\nexec bash %q --kicad-adapter "$@"\n' "$script_dir/run.sh" > "$adapter"
chmod +x "$adapter"
"$python_bin" -u artwork-resources/pcb-art/manufacturing/order_packages.py "${args[@]}" --kicad-cli "$adapter"
