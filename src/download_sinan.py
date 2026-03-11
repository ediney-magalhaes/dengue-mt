import httpx
import os
from pathlib import Path

# Pasta de destino
DESTINO = Path("data/raw/sinan")
DESTINO.mkdir(parents=True, exist_ok=True)

# URLs dos arquivos .dbc no FTP do DATASUS
BASE_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/dengue"

anos = range(2018, 2025)

arquivos = [f"DENGBR{str(ano)[2:]}.dbc" for ano in anos]

print("🦟 Iniciando download dos dados SINAN - Dengue MT\n")

for arquivo in arquivos:
    destino_arquivo = DESTINO / arquivo
    
    if destino_arquivo.exists():
        print(f"✅ {arquivo} já existe, pulando...")
        continue
    
    url = f"{BASE_URL}/{arquivo}"
    print(f"⬇️  Baixando {arquivo}...")
    
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
            if r.status_code == 200:
                with open(destino_arquivo, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ {arquivo} salvo com sucesso!")
            else:
                print(f"❌ {arquivo} não encontrado (status {r.status_code})")
    except Exception as e:
        print(f"❌ Erro ao baixar {arquivo}: {e}")

print("\n🏁 Download concluído!")