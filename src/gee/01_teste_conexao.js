// ============================================================
// Dengue MT — Teste de conexão GEE
// Verifica se o projeto está ativo e centraliza em Cuiabá
// ============================================================

var cuiaba = ee.Geometry.Point([-56.0974, -15.5961]);
Map.centerObject(cuiaba, 10);
Map.addLayer(cuiaba, {color: 'red'}, 'Cuiabá');
print('✅ GEE funcionando! Projeto:', 'meu-projeto-analytics');