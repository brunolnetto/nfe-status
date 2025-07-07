WITH
  -- 1) Build the timeline per day: start‑of‑day event + each status_servico4 transition
  timeline AS (
    -- anchor at actual start‑of‑day (first event timestamp for first day, else midnight)
    SELECT
      autorizador,
      dia,
      DATETIME(started_at)            AS ts,
      JSON_EXTRACT(initial, '$.status_servico4') AS status
    FROM daily_status

    UNION ALL

    -- each status_servico4 transition
    SELECT
      autorizador,
      dia,
      -- strip the trailing Z and convert to DATETIME
      DATETIME(
        REPLACE(REPLACE(JSON_EXTRACT(value, '$.when'), 'T', ' '), 'Z','')
      )                               AS ts,
      JSON_EXTRACT(value, '$.to')     AS status
    FROM daily_status,
         JSON_EACH(transitions, '$.status_servico4')
  ),

  -- 2) Order and peek at next timestamp (per day)
  ordered AS (
    SELECT
      autorizador,
      dia,
      ts,
      status,
      LEAD(ts) OVER (
        PARTITION BY autorizador, dia
        ORDER BY ts
      ) AS next_ts
    FROM timeline
  ),

  -- 3) Compute each segment’s duration in minutes,
  --    capping the last one at 23:59:59
  durations AS (
    SELECT
      autorizador,
      dia,
      status,
      (JULIANDAY(
         COALESCE(next_ts, DATETIME(dia || ' 23:59:59'))
       ) - JULIANDAY(ts)
      ) * 24 * 60 AS minutes
    FROM ordered
  )

-- 4) Aggregate “verde” vs total minutes → SLA %
SELECT
  autorizador,
  dia,
  ROUND(SUM(CASE WHEN status = 'verde' THEN minutes ELSE 0 END), 2) AS minutos_verde,
  ROUND(SUM(minutes), 2)                                  AS minutos_total,
  ROUND(
    100.0 * SUM(CASE WHEN status = 'verde' THEN minutes ELSE 0 END)
    / SUM(minutes)
  , 2)                                                     AS sla_percent
FROM durations
GROUP BY autorizador, dia
ORDER BY autorizador, dia;
