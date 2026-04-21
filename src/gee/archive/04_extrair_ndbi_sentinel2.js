// ============================================================
// Dengue MT — NDBI (Normalized Difference Built-up Index)
// Índice de urbanização via Sentinel-2
// NDBI = (SWIR - NIR) / (SWIR + NIR) = (B11 - B8) / (B11 + B8)
// Referência: Zha et al. (2003) Int. J. Remote Sensing
// ============================================================

var roi = ee.Geometry.Rectangle([-56.35, -15.75, -55.85, -15.40]);
var anos = ee.List.sequence(2018, 2024);
var meses = ee.List.sequence(1, 12);

var resultados = anos.map(function(ano) {
  return meses.map(function(mes) {
    var inicio = ee.Date.fromYMD(ano, mes, 1);
    var fim = inicio.advance(1, 'month');

    function addIndices(image) {
      var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
      var ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI');
      var ndbi = image.normalizedDifference(['B11', 'B8']).rename('NDBI');
      return image.addBands([ndvi, ndwi, ndbi]);
    }

    var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(roi)
      .filterDate(inicio, fim)
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
      .map(addIndices);

    var s2_size = s2.size();

    var stats = ee.Algorithms.If(
      s2_size.gt(0),
      s2.mean().select(['NDVI', 'NDWI', 'NDBI']).reduceRegion({
        reducer: ee.Reducer.mean(),
        geometry: roi,
        scale: 100,
        maxPixels: 1e9
      }),
      null
    );

    var ndbi_val = ee.Algorithms.If(
      s2_size.gt(0),
      ee.Dictionary(stats).get('NDBI'),
      null
    );

    var ndvi_val = ee.Algorithms.If(
      s2_size.gt(0),
      ee.Dictionary(stats).get('NDVI'),
      null
    );

    return ee.Feature(null, {
      'ano': ano,
      'mes': mes,
      'data': inicio.format('YYYY-MM'),
      'ndbi': ndbi_val,
      'ndvi': ndvi_val,
      'n_imagens': s2_size
    });
  });
}).flatten();

var fc = ee.FeatureCollection(resultados);
print('Total registros:', fc.size());
print('Amostra:', fc.limit(6));

Export.table.toDrive({
  collection: fc,
  description: 'dengue_mt_ndbi_2018_2024',
  folder: 'dengue_mt',
  fileNamePrefix: 'ndbi_2018_2024',
  fileFormat: 'CSV'
});

print('Exportação criada! Clique RUN na aba Tasks →');