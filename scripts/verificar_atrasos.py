# ============================================================
# Dengue MT — Verificar atraso real de cada fonte de dados
# ============================================================

import requests
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

hoje = datetime.now()
print(f"Hoje: {hoje.strftime('%Y-%m-%d')}")
print("=" * 50)

# 1. NASA POWER — qual o último dia disponível?
print("\nNASA POWER:")
url = "https://power.larc.nasa.gov/api/temporal/daily/point"
for dias_atras in [1, 3, 7, 14]:
    data_teste = (hoje - timedelta(days=dias_atras)).strftime("%Y%m%d")
    r = requests.get(url, params={
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": -56.1,
        "latitude": -15.6,
        "start": data_teste,
        "end": data_teste,
        "format": "JSON"
    }, timeout=15)
    if r.status_code == 200:
        data = r.json()
        valor = list(data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"].values())[0]
        status = "OK" if valor != -999 else "SEM DADO"
        print(f"  {dias_atras:2d}d atrás ({data_teste}): {status} — valor={valor:.2f}")

# 2. ONI Index — qual o último mês disponível?
print("\nONI Index NOAA:")
r = requests.get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", timeout=15)
linhas = r.text.strip().split("\n")
ultima = linhas[-1].split()
print(f"  Último registro: {ultima}")
# Formato real: SEAS YR ANOM (ex: DJF 2026 0.5)
try:
    ano = int(ultima[1])
    print(f"  Último ano: {ano}")
    atraso_meses = (hoje.year - ano) * 12 + (hoje.month - 1)
    print(f"  Atraso estimado: ~{atraso_meses} meses")
except Exception as e:
    print(f"  Formato inesperado: {e}")

# 3. Google Trends — qual o último dado?
print("\nGoogle Trends:")
try:
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl="pt-BR", tz=-240)
    pytrends.build_payload(["dengue"], timeframe="today 3-m", geo="BR-MT")
    df = pytrends.interest_over_time()
    if not df.empty:
        ultimo = df.index.max()
        atraso = (hoje - ultimo).days
        print(f"  Último dado: {ultimo.strftime('%Y-%m-%d')}")
        print(f"  Atraso: {atraso} dias")
except Exception as e:
    print(f"  Erro: {e}")

# 4. Gold dataset — última data disponível
print("\nGold Dataset:")
gold_path = Path("data/gold/dataset_features_v4.parquet")
if gold_path.exists():
    df_gold = pd.read_parquet(gold_path)
    df_gold["data"] = pd.to_datetime(df_gold["data"])
    ultima_data = df_gold["data"].max()
    atraso = (hoje - ultima_data).days
    print(f"  Última data: {ultima_data.strftime('%Y-%m-%d')}")
    print(f"  Atraso atual: {atraso} dias")
    print(f"  Registros: {len(df_gold)}")

# 5. INMET Silver — última data disponível
print("\nINMET Silver:")
inmet_path = Path("data/silver/inmet/inmet_cuiaba_2018_2024.parquet")
if inmet_path.exists():
    df_inmet = pd.read_parquet(inmet_path)
    if "data" in df_inmet.columns:
        df_inmet["data"] = pd.to_datetime(df_inmet["data"])
        ultima_data = df_inmet["data"].max()
    else:
        ultima_data = pd.to_datetime(df_inmet.index.max())
    atraso = (hoje - ultima_data).days
    print(f"  Última data: {ultima_data.strftime('%Y-%m-%d')}")
    print(f"  Atraso atual: {atraso} dias")
else:
    print("  Arquivo não encontrado localmente")

print("\n" + "=" * 50)
print("RESUMO DE ATRASOS — usar para definir DATA_CORTE")
print("=" * 50)