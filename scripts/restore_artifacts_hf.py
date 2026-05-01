# ============================================================
# Dengue MT — Restore de Artefatos do HF Hub
# ============================================================
# Uso:
#   python scripts/restore_artifacts_hf.py --gold --modelo
#   python scripts/restore_artifacts_hf.py --gold --modelo --schema --bronze
#
# Flags:
#   --gold    → data/gold/dataset_features_latest.parquet
#   --modelo  → models/lgbm_producao_latest.pkl
#   --schema  → models/lgbm_feature_schema_latest.json
#   --bronze  → data/bronze/**/*.parquet (todos os arquivos)
#
# Qualquer flag que falhar encerra com exit(1)
# ============================================================

import os
import sys
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

HF_REPO_ID = 'edyestatistica/dengue-mt-medallion'
HF_TOKEN   = os.environ.get('HF_TOKEN')
ROOT_DIR   = Path(__file__).parent.parent


def restore_arquivo(hf_hub_download, path_hf: str, path_local: Path) -> bool:
    """Baixa um arquivo do HF Hub para path_local. Retorna True se ok."""
    try:
        path_local.parent.mkdir(parents=True, exist_ok=True)
        downloaded = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=path_hf,
            repo_type='dataset',
            token=HF_TOKEN,
        )
        shutil.copy(downloaded, path_local)
        print(f'  OK: {path_local}')
        return True
    except Exception as e:
        print(f'  ERRO: {path_hf} — {e}')
        return False


def restore_bronze(hf_hub_download, HfApi) -> bool:
    """
    Baixa todos os arquivos Bronze do HF Hub.
    Retorna True se todos os arquivos foram restaurados com sucesso.
    """
    api = HfApi()
    print('Buscando arquivos Bronze no HF Hub...')

    try:
        items = list(api.list_repo_tree(
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            path_in_repo='bronze',
            recursive=True,
            token=HF_TOKEN,
        ))
        arquivos = [
            i.path for i in items
            if hasattr(i, 'lfs') and i.lfs
            and i.path.endswith('.parquet')
        ]

        if not arquivos:
            print('  ERRO: Nenhum arquivo Bronze encontrado no HF Hub')
            return False

        print(f'  Encontrados: {len(arquivos)} arquivos Bronze')

        falhas = []
        for path_hf in arquivos:
            path_local = ROOT_DIR / 'data' / path_hf
            if not restore_arquivo(hf_hub_download, path_hf, path_local):
                falhas.append(path_hf)

        if falhas:
            print(f'  ERRO: {len(falhas)} arquivos Bronze não restaurados:')
            for f in falhas:
                print(f'    - {f}')
            return False

        print(f'  Bronze restaurado: {len(arquivos)}/{len(arquivos)} arquivos')
        return True

    except Exception as e:
        print(f'  ERRO: Restore Bronze falhou — {e}')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Restaura artefatos do HF Hub para execução local ou CI'
    )
    parser.add_argument('--gold',   action='store_true', help='Restaurar Gold latest')
    parser.add_argument('--modelo', action='store_true', help='Restaurar modelo latest')
    parser.add_argument('--schema', action='store_true', help='Restaurar feature schema latest')
    parser.add_argument('--bronze', action='store_true', help='Restaurar Bronze completo')
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(1)

    try:
        from huggingface_hub import hf_hub_download, HfApi
    except ImportError:
        print('ERRO: huggingface_hub não instalado — pip install huggingface_hub')
        sys.exit(1)

    if not HF_TOKEN:
        print('WARN: HF_TOKEN não definido — repositório público, tentando sem token')

    print(f'\n{"="*50}')
    print('Restore Artefatos — HF Hub')
    print(f'Repo: {HF_REPO_ID}')
    print(f'{"="*50}\n')

    falhas = []

    # Gold
    if args.gold:
        print('→ Gold latest')
        if not restore_arquivo(
            hf_hub_download,
            'gold/dataset_features_latest.parquet',
            ROOT_DIR / 'data' / 'gold' / 'dataset_features_latest.parquet',
        ):
            falhas.append('gold')

    # Modelo
    if args.modelo:
        print('→ Modelo latest')
        if not restore_arquivo(
            hf_hub_download,
            'models/lgbm_producao_latest.pkl',
            ROOT_DIR / 'models' / 'lgbm_producao_latest.pkl',
        ):
            falhas.append('modelo')

    # Schema
    if args.schema:
        print('→ Feature schema latest')
        if not restore_arquivo(
            hf_hub_download,
            'models/lgbm_feature_schema_latest.json',
            ROOT_DIR / 'models' / 'lgbm_feature_schema_latest.json',
        ):
            falhas.append('schema')

    # Bronze
    if args.bronze:
        print('→ Bronze completo')
        if not restore_bronze(hf_hub_download, HfApi):
            falhas.append('bronze')

    # Resumo
    print(f'\n{"="*50}')
    if falhas:
        print(f'ERRO: Falha ao restaurar: {", ".join(falhas)}')
        print(f'{"="*50}\n')
        sys.exit(1)
    else:
        print('Todos os artefatos restaurados com sucesso')
        print(f'{"="*50}\n')


if __name__ == '__main__':
    main()