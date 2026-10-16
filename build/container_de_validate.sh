#!/usr/bin/env bash
# Validation DE : pret_europe_german reconstruit-il la ROM Smaragd de l'utilisateur ?
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends libpng-dev build-essential
rm -rf /de_validate /agbcc
git clone --depth 1 --branch pret_europe_german https://github.com/AsparagusEduardo/pokeemerald /de_validate
git clone --depth 1 https://github.com/pret/agbcc /agbcc
cd /agbcc && ./build.sh && ./install.sh /de_validate
cd /de_validate && make tools -j4 && make -j6 LANGUAGE=GERMAN
echo "=== SHA1 BUILT"
sha1sum pokeemerald_de.gba 2>/dev/null || ls -la *.gba
echo "=== SHA1 ROM UTILISATEUR"
sha1sum /derom/Pokemon*.gba
echo "=== DONE"
