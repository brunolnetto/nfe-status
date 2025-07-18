CREATE OR REPLACE VIEW vw_nfe_daily_status AS
WITH
  boundaries AS (
    SELECT autorizador,
           MIN(valid_from::date) AS min_day,
           MAX(COALESCE(valid_to, NOW()::date)) AS max_day
    FROM nfe_status_raw
    GROUP BY autorizador
  ),
  calendar AS (
    SELECT
      b.autorizador,
      gs.dia,
      b.max_day
    FROM boundaries b
    CROSS JOIN LATERAL generate_series(b.min_day, b.max_day, INTERVAL '1 day') AS gs(dia)
  ),

  first_event AS (
    SELECT autorizador, MIN(valid_from) AS first_ts
    FROM nfe_status_raw
    GROUP BY autorizador
  ),

  events_flat AS (
    SELECT
      autorizador,
      valid_from AS ts,
      je.key,
      je.value
    FROM nfe_status_raw,
         LATERAL jsonb_each(status_json::jsonb) AS je
    WHERE je.key IN (
      'status_servico4', 'autorizacao4', 'consulta_protocolo4',
      'retorno_autorizacao4', 'inutilizacao4', 'consulta_cadastro4', 'recepcao_evento4'
    )
  ),

  initial_per_day AS (
    SELECT
      cal.autorizador,
      cal.dia,
      ef.key,
      (
        SELECT e2.value
        FROM events_flat e2
        WHERE e2.autorizador = cal.autorizador
          AND e2.key = ef.key
          AND e2.ts <= (cal.dia::timestamp)
        ORDER BY e2.ts DESC
        LIMIT 1
      ) AS initial_value
    FROM calendar cal
    CROSS JOIN (SELECT DISTINCT key FROM events_flat) ef
  ),

  day_events AS (
    SELECT
      ef.autorizador,
      ef.ts::date AS dia,
      ef.key,
      ef.ts,
      ef.value,
      ip.initial_value
    FROM events_flat ef
    JOIN initial_per_day ip
      ON ip.autorizador = ef.autorizador
     AND ip.dia = ef.ts::date
     AND ip.key = ef.key
  ),

  transitions AS (
    SELECT
      autorizador,
      dia,
      key,
      jsonb_build_object(
        'from', LAG(value,1,initial_value) OVER (
          PARTITION BY autorizador, dia, key
          ORDER BY ts
        ),
        'to', value,
        'when', to_char(ts, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      ) AS obj
    FROM day_events
  ),

  transitions_json AS (
    SELECT autorizador, dia, key,
           jsonb_agg(obj) AS arr
    FROM transitions
    GROUP BY autorizador, dia, key
  ),

  transitions_grouped AS (
    SELECT autorizador, dia,
           jsonb_object_agg(key, arr) AS transitions_json
    FROM transitions_json
    GROUP BY autorizador, dia
  ),

  initials_json AS (
    SELECT autorizador, dia,
           jsonb_object_agg(key, initial_value) AS initial_json
    FROM initial_per_day
    GROUP BY autorizador, dia
  ),

  started_at_per_day AS (
    SELECT
      c.autorizador,
      c.dia,
      CASE
        WHEN c.dia = b.min_day THEN fe.first_ts
        ELSE (c.dia::timestamp AT TIME ZONE 'UTC')
      END AS started_at
    FROM calendar c
    JOIN boundaries b ON c.autorizador = b.autorizador
    JOIN first_event fe ON fe.autorizador = c.autorizador
  )

SELECT
  cal.autorizador,
  cal.dia,
  COALESCE(tg.transitions_json, '{}'::jsonb) AS transitions,
  COALESCE(ij.initial_json, '{}'::jsonb) AS initial,
  sa.started_at
FROM calendar cal
LEFT JOIN transitions_grouped tg ON tg.autorizador = cal.autorizador AND tg.dia = cal.dia
LEFT JOIN initials_json ij ON ij.autorizador = cal.autorizador AND ij.dia = cal.dia
LEFT JOIN started_at_per_day sa ON sa.autorizador = cal.autorizador AND sa.dia = cal.dia
ORDER BY cal.autorizador, cal.dia;
