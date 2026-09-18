-- ============================================================
-- GOLD TELEMETRY LAP RECONCILIATION
--
-- Every telemetry lap must correspond to a Silver lap record.
-- ============================================================

select

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    lap_match_status

from {{ ref('lap_telemetry_metrics') }}

where has_lap_record = false
   or lap_match_status = 'NO_LAP_RECORD'
