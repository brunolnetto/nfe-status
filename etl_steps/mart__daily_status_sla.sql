CREATE OR REPLACE VIEW vw_nfe_daily_sla AS

WITH
  -- 1) Build the timeline per day: start‑of‑day event + each status_servico4 transition
  timeline AS (
    -- anchor at actual start‑of‑day (first event timestamp for first day, else midnight)
    SELECT
      autorizador,
      dia,
      started_at::timestamp            AS ts,
      initial::jsonb ->> 'status_servico4' AS status
    FROM vw_nfe_daily_status

    UNION ALL

    -- each status_servico4 transition
    SELECT
      autorizador,
      dia,
      -- strip the trailing Z and convert to timestamp
      to_timestamp(
        regexp_replace((value->>'when'), 'T', ' '), 'YYYY-MM-DD HH24:MI:SS'
      ) AS ts,
      value->>'to' AS status
    FROM vw_nfe_daily_status,
         LATERAL jsonb_array_elements(transitions::jsonb -> 'status_servico4') AS value
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
      (EXTRACT(EPOCH FROM (
         COALESCE(next_ts, (dia::timestamp + INTERVAL '23:59:59')) - ts
      )) / 60.0) AS minutes
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
    / NULLIF(SUM(minutes), 0)
  , 2)                                                     AS sla_percent
FROM durations
GROUP BY autorizador, dia
ORDER BY autorizador, dia;
