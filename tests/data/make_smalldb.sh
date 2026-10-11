#!/usr/bin/env bash
# Usage: tests/data/make_smalldb.sh /path/to/full/taxdump
set -euo pipefail

fixture_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=${1:?Usage: make_smalldb.sh /path/to/full/taxdump}
source_dir=$(cd -- "$source_dir" && pwd)
if [[ "$source_dir" == "$fixture_dir" ]]; then
    echo "Source must be a full taxdump outside the fixture directory" >&2
    exit 1
fi
for name in delnodes division merged names nodes; do
    test -r "$source_dir/$name.dmp"
done
test -s "$fixture_dir/kept_taxids.list"
staging=$(mktemp -d "$fixture_dir/.fixture-build.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT

head -n 10 "$source_dir/delnodes.dmp" > "$staging/delnodes.dmp"
cp -- "$source_dir/division.dmp" "$staging/division.dmp"
awk 'NR==FNR{key[$0]=1; next} $3 in key' "$fixture_dir/kept_taxids.list" "$source_dir/merged.dmp" > "$staging/merged.dmp"
for name in names nodes; do
    awk 'NR==FNR{key[$0]=1; next} $1 in key' "$fixture_dir/kept_taxids.list" "$source_dir/$name.dmp" > "$staging/$name.dmp"
    test -s "$staging/$name.dmp"
done
# Parse and validate staged files before replacing any checked-in fixture.
python -m taxdumpy cache -d "$staging"
for name in delnodes division merged names nodes; do
    mv -- "$staging/$name.dmp" "$fixture_dir/$name.dmp"
done
