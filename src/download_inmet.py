import urllib.request
import os

def download_inmet(anos=range(2018, 2025), destino="data/raw/inmet"):
    """
    Baixa os dados históricos anuais do INMET (todas as estações automáticas).
    Fonte: https://portal.inmet.gov.br/uploads/dadoshistoricos
    """
    os.makedirs(destino, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}

    print("🌡️  Iniciando download dos dados climáticos INMET\n")

    for ano in anos:
        url = f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
        dest = f"{destino}/{ano}.zip"

        if os.path.exists(dest):
            print(f"✅ {ano}.zip já existe, pulando...")
            continue

        print(f"⬇️  Baixando {ano}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
                f.write(r.read())
            print(f"✅ {ano}.zip salvo!")
        except Exception as e:
            print(f"❌ Erro ao baixar {ano}: {e}")

    print("\n🏁 Download concluído!")

if __name__ == "__main__":
    download_inmet()