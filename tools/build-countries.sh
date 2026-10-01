#!/bin/bash
# Builds weltenbummler/static/countries.json from Natural Earth 1:50m Admin-0 countries.
# One feature per ADM0_A3 (unique, unlike ISO_A2, which is -99 for e.g. France
# and Norway in Natural Earth); German name from NAME_DE.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
[ -f data/ne_50m.geojson ] || curl -sSfL -o data/ne_50m.geojson \
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
npx -y mapshaper@0.6 data/ne_50m.geojson \
  -filter-fields ADM0_A3,ISO_A2_EH,NAME_DE \
  -rename-fields id=ADM0_A3,iso=ISO_A2_EH,name=NAME_DE \
  -simplify 40% keep-shapes \
  -o weltenbummler/static/countries.json format=topojson id-field=id quantization=1e5
