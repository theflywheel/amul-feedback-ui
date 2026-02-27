#!/usr/bin/env sh
set -e

if [ "${INIT_FROM_SHEETS:-0}" = "1" ]; then
  python3 scripts/init_from_sheets.py \
    --db "${DB_PATH:-app.db}" \
    --golden-sheet "${GOLDEN_SHEET_PATH:-data/Sheets/500_goldenset_final_sheet.csv}" \
    --eval-sheet "${EVAL_SHEET_PATH:-data/Sheets/Amul Eval Sheet.csv}" \
    ${SYNC_ACTIVE:+--sync-active}
fi

exec python3 app.py
