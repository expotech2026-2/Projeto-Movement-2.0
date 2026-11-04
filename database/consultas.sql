-- Selecione o banco Movement no Query Tool do pgAdmin.
SET search_path TO movement, public;

SELECT r.name AS sala, a.name AS aparelho, a.kind AS tipo, a.capacity_btu, a.inverter, a.status
FROM rooms r LEFT JOIN air_conditioners a ON a.room_id = r.id ORDER BY r.name, a.name;

SELECT r.name AS sala, m.month AS mes, m.sample_count AS amostras,
       m.avg_temp_inside, m.avg_temp_outside, m.avg_humidity_inside,
       m.avg_humidity_outside, m.avg_occupancy, m.ac_on_percent
FROM monthly_summaries m JOIN rooms r ON r.id = m.room_id ORDER BY m.month DESC, r.name;

SELECT room_id, measured_at, temp_inside, temp_outside, humidity_inside, occupancy, ac_on
FROM sensor_readings WHERE measured_at >= now() - interval '30 days'
ORDER BY measured_at DESC LIMIT 500;
