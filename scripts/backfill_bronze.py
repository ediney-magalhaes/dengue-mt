"""
Backfill histórico Bronze — 2018→2025
Chama os módulos de ingestão para popular o Bronze completo
Roda UMA VEZ manualmente — pipeline semanal complementa automaticamente
"""
from src.ingestion.infodengue import ingerir_bronze as ingerir_infodengue
from src.ingestion.nasa_power import ingerir_bronze as ingerir_nasa_power
from src.ingestion.oni import ingerir_bronze as ingerir_oni
from src.ingestion.trends import ingerir_bronze as ingerir_trends

if __name__ == '__main__':
    print('=== BACKFILL BRONZE 2018→2025 ===')
    
    print('\n1. InfoDengue...')
    ingerir_infodengue(ano_inicio=2018)
    
    print('\n2. NASA POWER...')
    ingerir_nasa_power(data_inicio=2018)
    
    print('\n3. ONI Index...')
    ingerir_oni()
    
    print('\n4. Google Trends...')
    ingerir_trends()
    
    print('\n=== BACKFILL CONCLUÍDO ===')