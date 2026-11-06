-- Selecione o banco Movement no Query Tool do pgAdmin.
SET search_path TO movement, public;

-- Unidades e quantidade de salas.
SELECT u.name AS unidade, u.address AS endereco, count(r.id) AS salas
FROM units u LEFT JOIN rooms r ON r.unit_id = u.id
GROUP BY u.id, u.name, u.address ORDER BY u.name;

-- Inventário: aparelhos de cada sala, por unidade.
SELECT u.name AS unidade, r.name AS sala, a.name AS aparelho, a.kind AS tipo, a.capacity_btu,
       a.inverter, a.status
FROM rooms r JOIN units u ON u.id = r.unit_id
LEFT JOIN air_conditioners a ON a.room_id = r.id ORDER BY u.name, r.name, a.name;

-- Dispositivos ESP32 por sala (o token fica só como hash e não é listado).
SELECT u.name AS unidade, r.name AS sala, d.id AS dispositivo, d.enabled AS ativo
FROM devices d JOIN rooms r ON r.id = d.room_id JOIN units u ON u.id = r.unit_id
ORDER BY u.name, r.name;

-- Médias mensais consolidadas pela retenção.
SELECT r.name AS sala, m.month AS mes, m.sample_count AS amostras,
       m.avg_temp_inside, m.avg_temp_outside, m.avg_humidity_inside,
       m.avg_humidity_outside, m.avg_occupancy, m.ac_on_percent
FROM monthly_summaries m JOIN rooms r ON r.id = m.room_id ORDER BY m.month DESC, r.name;

-- Leituras detalhadas dos últimos 30 dias.
SELECT room_id, measured_at, temp_inside, temp_outside, humidity_inside, occupancy, ac_on
FROM sensor_readings WHERE measured_at >= now() - interval '30 days'
ORDER BY measured_at DESC LIMIT 500;

-- Alertas mais recentes, no horário de São Paulo.
SELECT a.created_at AT TIME ZONE 'America/Sao_Paulo' AS quando, r.name AS sala, a.kind AS tipo,
       a.message AS mensagem, a.value AS valor
FROM alerts a JOIN rooms r ON r.id = a.room_id ORDER BY a.created_at DESC LIMIT 50;

-- Usuários cadastrados (sem o hash da senha); o administrador principal fica só no .env.
SELECT username AS login, full_name AS nome, role AS perfil, active AS ativo,
       created_at AT TIME ZONE 'America/Sao_Paulo' AS criado_em
FROM users ORDER BY role, username;

-- Catálogo do Inmetro: modelos por marca.
SELECT brand AS marca, count(*) AS modelos, min(capacity_btu) AS menor_btu,
       max(capacity_btu) AS maior_btu, count(*) FILTER (WHERE inverter) AS inverter
FROM ac_catalog GROUP BY brand ORDER BY modelos DESC, marca;
