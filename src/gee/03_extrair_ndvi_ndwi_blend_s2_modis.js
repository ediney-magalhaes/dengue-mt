// ============================================================
// Dengue MT — MODIS como complemento ao Sentinel-2
// Preencher meses sem cobertura Sentinel-2
// ============================================================

var roi = ee.Geometry.Rectangle([-56.35, -15.75, -55.85, -15.40]);

var anos = ee.List.sequence(2018, 2024);
var meses = ee.List.sequence(1, 12);

var resultados = anos.map(function(ano) {
  return meses.map(function(mes) {
    var inicio = ee.Date.fromYMD(ano, mes, 1);
    var fim = inicio.advance(1, 'month');

    // --- Sentinel-2 ---
    function addIndicesS2(image) {
      var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
      var ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI');
      return image.addBands([ndvi, ndwi]);
    }

    var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(roi).filterDate(inicio, fim)
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
      .map(addIndicesS2);

    var s2_size = s2.size();

    var s2_stats = ee.Algorithms.If(
      s2_size.gt(0),
      s2.mean().select(['NDVI','NDWI']).reduceRegion({
        reducer: ee.Reducer.mean(), geometry: roi,
        scale: 100, maxPixels: 1e9
      }),
      null
    );

    // --- MODIS ---
    var modis = ee.ImageCollection('MODIS/061/MOD13A3')
      .filterBounds(roi).filterDate(inicio, fim)
      .select(['NDVI']);

    var modis_size = modis.size();

    var modis_ndvi = ee.Algorithms.If(
      modis_size.gt(0),
      modis.mean().multiply(0.0001).reduceRegion({
        reducer: ee.Reducer.mean(), geometry: roi,
        scale: 500, maxPixels: 1e9
      }),
      null
    );

    // --- Decidir fonte ---
    // Prioridade: Sentinel-2 > MODIS > null
    var fonte = ee.Algorithms.If(s2_size.gt(0), 'sentinel2',
                  ee.Algorithms.If(modis_size.gt(0), 'modis', 'ausente'));

    var ndvi_final = ee.Algorithms.If(
      s2_size.gt(0),
      ee.Dictionary(s2_stats).get('NDVI'),
      ee.Algorithms.If(
        modis_size.gt(0),
        ee.Dictionary(modis_ndvi).get('NDVI'),
        null
      )
    );

    var ndwi_final = ee.Algorithms.If(
      s2_size.gt(0),
      ee.Dictionary(s2_stats).get('NDWI'),
      null  // MODIS não tem NDWI — será imputado sazonalmente
    );

    return ee.Feature(null, {
      'ano': ano, 'mes': mes,
      'data': inicio.format('YYYY-MM'),
      'ndvi_final': ndvi_final,
      'ndwi_final': ndwi_final,
      'fonte': fonte,
      'n_s2': s2_size,
      'n_modis': modis_size
    });
  });
}).flatten();

var fc = ee.FeatureCollection(resultados);
print('Total registros:', fc.size());
print('Amostra:', fc.limit(6));

Export.table.toDrive({
  collection: fc,
  description: 'dengue_mt_ndvi_ndwi_blend_2018_2024',
  folder: 'dengue_mt',
  fileNamePrefix: 'ndvi_ndwi_blend_2018_2024',
  fileFormat: 'CSV'
});

print('✅ Exportação criada! Clique RUN na aba Tasks →');