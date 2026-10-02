#!/bin/bash
# Builds weltenbummler/static/countries.json from Natural Earth 1:50m:
#   countries  Admin-0, one feature per ADM0_A3 (unique, unlike ISO_A2, which
#              is -99 for e.g. France and Norway in Natural Earth)
#   states     Admin-1 of the USA, keyed by ISO 3166-2 ("US-CA")
# German names from NAME_DE / name_de.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
[ -f data/ne_50m.geojson ] || curl -sSfL -o data/ne_50m.geojson "$NE/ne_50m_admin_0_countries.geojson"
[ -f data/ne_50m_admin1.geojson ] || curl -sSfL -o data/ne_50m_admin1.geojson "$NE/ne_50m_admin_1_states_provinces.geojson"
npx -y mapshaper@0.6 \
  -i data/ne_50m.geojson data/ne_50m_admin1.geojson combine-files \
  -rename-layers countries,states \
  -filter-fields ADM0_A3,ISO_A2_EH,NAME_DE target=countries \
  -rename-fields id=ADM0_A3,iso=ISO_A2_EH,name=NAME_DE target=countries \
  -filter 'adm0_a3 === "USA"' target=states \
  -each 'id = iso_3166_2; iso = ""; name = id === "US-DC" ? "Washington, D.C." : name_de' target=states \
  -filter-fields id,iso,name target=states \
  -simplify 40% keep-shapes target=* \
  -o weltenbummler/static/countries.json format=topojson id-field=id quantization=1e5 target=*
