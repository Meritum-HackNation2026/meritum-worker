#!/usr/bin/env bash
# Guide the repository owner through replacing the EUvsDisinfo MCP credential.
set -euo pipefail

repo=Meritum-HackNation2026/meritum-worker

printf '%s\n' '1/3 Poproś administratora EUvsDisinfo MCP o nowy klucz do wywołania cases na /mcp.'
read -r -p 'Masz nowy klucz? Naciśnij Enter, aby przejść dalej. ' </dev/tty

printf '%s\n' '2/3 Zastąp sekret EUVSDISINFO_MCP_API_KEY na GitHubie.'
read -r -p 'Zastąpić sekret w meritum-worker? [t/N] ' confirmed </dev/tty
if [[ "$confirmed" != t && "$confirmed" != T ]]; then
  exit 1
fi
gh secret set EUVSDISINFO_MCP_API_KEY --repo "$repo" </dev/tty

printf '%s\n' \
  '3/3 Wdróż nowy sekret i sprawdź gotowość.' \
  "Dev: gh workflow run ci.yml --ref develop --repo $repo" \
  'Po udanym wdrożeniu sprawdź, czy euvsdisinfo zniknęło z listy niedostępnych dostawców w GET /api/v1/health na dev.' \
  'Po potwierdzeniu wyniku na dev powtórz w uzgodnionym oknie wdrożeniowym na prod.' \
  "Prod: gh workflow run ci.yml --ref main --repo $repo" \
  'Sprawdź tę samą listę w raporcie gotowości prod.'
