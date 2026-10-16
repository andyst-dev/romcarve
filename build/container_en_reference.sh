#!/usr/bin/env bash
# Arbre EN de reference : pret/pokeemerald (reproduit BPEE) + carte de symboles.
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends libpng-dev build-essential
rm -rf /en_validate
git clone --depth 1 https://github.com/pret/pokeemerald /en_validate
cd /agbcc && ./install.sh /en_validate
cd /en_validate && make tools -j4 && make -j6
echo "=== SHA1 EN (attendu f3ae088181bf583e55daf962a92bb46f4f1d07b7)"
sha1sum pokeemerald.gba
echo "=== MAP"
ls -la pokeemerald.map
grep -c "" pokeemerald.map
echo "=== DONE"
