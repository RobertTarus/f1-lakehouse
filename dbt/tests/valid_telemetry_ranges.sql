select *

from {{ ref('silver_telemetry') }}

where speed_kph < 0
   or speed_kph > 400

   or throttle_pct < 0
   or throttle_pct > 100

   or rpm < 0
   or rpm > 20000

   or gear < 0
   or gear > 8
