CREATE VIEW daily_status AS
WITH
  boundaries AS (
    SELECT autorizador,
           DATE(MIN(valid_from)) AS min_day,
           DATE(MAX(COALESCE(valid_to, DATETIME('now')))) AS max_day
    FROM disponibilidade
    GROUP BY autorizador
  ),

  calendar AS (
    SELECT autorizador, min_day AS dia, max_day FROM boundaries
    UNION ALL
    SELECT autorizador, DATE(dia, '+1 day'), max_day
    FROM calendar
    WHERE DATE(dia, '+1 day') <= max_day
  ),

  first_event AS (
    SELECT autorizador, MIN(DATETIME(valid_from)) AS first_ts
    FROM disponibilidade
    GROUP BY autorizador
  ),

  events_flat AS (
    -- Optimized: Unpivot status_json in a single scan using json_each
    SELECT
      autorizador,
      DATETIME(valid_from) AS ts,
      je.key,
      je.value
    FROM disponibilidade,
         json_each(status_json) AS je
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
          AND e2.ts <= DATETIME(cal.dia || ' 00:00:00')
        ORDER BY e2.ts DESC
        LIMIT 1
      ) AS initial_value
    FROM calendar cal
    CROSS JOIN (SELECT DISTINCT key FROM events_flat) ef
  ),

  day_events AS (
    SELECT
      ef.autorizador,
      DATE(ef.ts) AS dia,
      ef.key,
      ef.ts,
      ef.value,
      ip.initial_value
    FROM events_flat ef
    JOIN initial_per_day ip
      ON ip.autorizador = ef.autorizador
     AND ip.dia = DATE(ef.ts)
     AND ip.key = ef.key
  ),

  transitions AS (
    SELECT
      autorizador,
      dia,
      key,
      printf(
        '{"from":"%s","to":"%s","when":"%sZ"}',
        LAG(value,1,initial_value) OVER (
          PARTITION BY autorizador, dia, key
          ORDER BY ts
        ),
        value,
        STRFTIME('%Y-%m-%dT%H:%M:%S', ts)
      ) AS obj
    FROM day_events
  ),

  transitions_json AS (
    SELECT autorizador, dia, key,
           '[' || GROUP_CONCAT(obj, ',') || ']' AS arr
    FROM transitions
    GROUP BY autorizador, dia, key
  ),

  transitions_grouped AS (
    SELECT autorizador, dia,
           '{' || GROUP_CONCAT('"' || key || '":' || arr, ',') || '}' AS transitions_json
    FROM transitions_json
    GROUP BY autorizador, dia
  ),

  initials_json AS (
    SELECT autorizador, dia,
           '{' || GROUP_CONCAT('"' || key || '":"' || initial_value || '"', ',') || '}' AS initial_json
    FROM initial_per_day
    GROUP BY autorizador, dia
  ),

  started_at_per_day AS (
    SELECT
      c.autorizador,
      c.dia,
      CASE
        WHEN c.dia = b.min_day THEN fe.first_ts
        ELSE STRFTIME('%Y-%m-%dT00:00:00Z', c.dia)
      END AS started_at
    FROM calendar c
    JOIN boundaries b ON c.autorizador = b.autorizador
    JOIN first_event fe ON fe.autorizador = c.autorizador
  )

SELECT
  cal.autorizador,
  cal.dia,
  COALESCE(tg.transitions_json, '{}') AS transitions,
  COALESCE(ij.initial_json, '{}') AS initial,
  sa.started_at
FROM calendar cal
LEFT JOIN transitions_grouped tg ON tg.autorizador = cal.autorizador AND tg.dia = cal.dia
LEFT JOIN initials_json ij ON ij.autorizador = cal.autorizador AND ij.dia = cal.dia
LEFT JOIN started_at_per_day sa ON sa.autorizador = cal.autorizador AND sa.dia = cal.dia
ORDER BY cal.autorizador, cal.dia;
