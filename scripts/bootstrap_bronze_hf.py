# ============================================================
# Dengue MT — Bootstrap: publicar Bronze completo no HF Hub
# ============================================================
# Execução única (ou re-execução segura — idempotente)
# Uso: python scripts/bootstrap_bronze_hf.py
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()

ROOT_DIR   = Path(__file__).parent.parent
BRONZE_DIR = ROOT_DIR / 'data' / 'bronze'
HF_REPO_ID = 'edyestatistica/dengue-mt-medallion'
HF_TOKEN   = os.environ.get('HF_TOKEN')

def main():
    api     = HfApi()
    arquivos = sorted(BRONZE_DIR.rglob('*.parquet'))

    print(f"Encontrados {len(arquivos)} arquivos Bronze para publicar\n")

    ok    = []
    falha = []

    for path_local in arquivos:
        # Caminho relativo a partir de data/ → bronze/fonte/arquivo.parquet
        path_hf = 'bronze/' + '/'.join(path_local.relative_to(BRONZE_DIR).parts)

        try:
            api.upload_file(
                path_or_fileobj=str(path_local),
                path_in_repo=path_hf,
                repo_id=HF_REPO_ID,
                repo_type='dataset',
                token=HF_TOKEN,
            )
            print(f"  ✅ {path_hf}")
            ok.append(path_hf)
        except Exception as e:
            print(f"  ❌ {path_hf} — {e}")
            falha.append(path_hf)

    print(f"\n{'='*50}")
    print(f"Publicados : {len(ok)}")
    print(f"Falhas     : {len(falha)}")
    if falha:
        print("\nArquivos com falha:")
        for f in falha:
            print(f"  {f}")

if __name__ == '__main__':
    main()