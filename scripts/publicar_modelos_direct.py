"""
Publica 12 modelos Direct CQR + metadata no HF Hub.

ATENÇÃO: Este script é utilitário para publicação manual de emergência.
Em operação normal, a publicação acontece automaticamente via pipeline_prefect.py
após aprovação do gate Champion-Challenger (ADR-035).

Use este script apenas quando:
  - O pipeline automático falhou na publicação (não no gate)
  - Você confirmou manualmente que os modelos locais passaram pelo gate
  - Há autorização explícita para bypass do pipeline automático
"""
from huggingface_hub import HfApi
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Confirmação explícita de bypass
print("=" * 60)
print("PUBLICAÇÃO MANUAL — BYPASS DO PIPELINE AUTOMÁTICO")
print("ADR-035: Em operação normal use pipeline_prefect.py")
print("=" * 60)
resposta = input("Confirma publicação manual? (sim/não): ").strip().lower()
if resposta != 'sim':
    print("Cancelado.")
    exit(0)

api   = HfApi()
token = os.environ['HF_TOKEN']
repo  = 'edyestatistica/dengue-mt-medallion'

models_dir = Path('models')
arquivos   = sorted(models_dir.glob('lgbm_h*_q*_latest.pkl'))
arquivos.append(models_dir / 'direct_cqr_metadata.json')

for arq in arquivos:
    if arq.exists():
        path_hf = f'models/{arq.name}'
        print(f'Publicando {arq.name}...')
        api.upload_file(
            path_or_fileobj=str(arq),
            path_in_repo=path_hf,
            repo_id=repo,
            repo_type='dataset',
            token=token,
        )

print(f'\nTotal: {len(arquivos)} arquivos publicados')