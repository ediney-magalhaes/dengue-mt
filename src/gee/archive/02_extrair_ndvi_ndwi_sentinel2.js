// ============================================================
// Dengue MT — Extração NDVI e NDWI — Sentinel-2 puro
// Satélite: Sentinel-2 SR Harmonized (resolução 10m)
// Região: Cuiabá e Várzea Grande / MT
// Período: 2018–2024
// Resultado: 84 registros mensais (13 meses sem cobertura = -9999)
// ============================================================

var roi = ee.Geometry.Rectangle([-56.35, -15.75, -55.85, -15.40]);

function addIndices(image) {
  var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI');
  return image.addBands([ndvi, ndwi])
              .set('system:time_start', image.get('system:time_start'));
}

var anos = ee.List.sequence(2018, 2024);
var meses = ee.List.sequence(1, 12);

var resultados = anos.map(function(ano) {
  return meses.map(function(mes) {
    var inicio = ee.Date.fromYMD(ano, mes, 1);
    var fim = inicio.advance(1, 'month');

    var colecao = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(roi)
      .filterDate(inicio, fim)
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
      .map(addIndices);

    var tamanho = colecao.size();

    var fallback = ee.Image.constant([-9999, -9999])
                     .rename(['NDVI', 'NDWI'])
                     .toFloat();

    var media = ee.Algorithms.If(
      tamanho.gt(0),
      colecao.mean().select(['NDVI','NDWI']),
      fallback
    );

    var stats = ee.Image(media).reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: roi,
      scale: 100,
      maxPixels: 1e9
    });

    return ee.Feature(null, {
      'ano': ano,
      'mes': mes,
      'data': inicio.format('YYYY-MM'),
      'ndvi_medio': stats.get('NDVI'),
      'ndwi_medio': stats.get('NDWI'),
      'n_imagens': tamanho
    });
  });
}).flatten();

var fc = ee.FeatureCollection(resultados);
print('Total de registros:', fc.size());
print('Amostra:', fc.limit(5));

Export.table.toDrive({
  collection: fc,
  description: 'dengue_mt_ndvi_ndwi_2018_2024',
  folder: 'dengue_mt',
  fileNamePrefix: 'ndvi_ndwi_mensal_2018_2024',
  fileFormat: 'CSV'
});

print('✅ Exportação criada! Clique RUN na aba Tasks →');