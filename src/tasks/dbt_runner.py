# ============================================================
# Dengue MT — Task: dbt Runner
# ============================================================
# Responsabilidade ÚNICA: executar dbt run + dbt test
# Substitui build_gold_dataset na arquitetura v2.0
#
# Fluxo:
# Bronze (Parquet) → dbt run → Silver → Intermediate → Gold
#                 → dbt test → validação declarativa
# ============================================================

import subprocess
import logging
from pathlib import Path
from prefect import task, get_run_logger

logger = logging.getLogger('dengue-mt.dbt_runner')

# Caminho absoluto do projeto dbt
DBT_PROJECT_DIR = Path(__file__).resolve().parents[2] / 'dengue_mt_dbt'


def _executar_dbt(comando: list[str], logger) -> dict:
    """
    Executa um comando dbt via subprocess e retorna resultado.
    Sempre roda a partir do diretório do projeto dbt.
    """
    try:
        resultado = subprocess.run(
            comando,
            cwd=DBT_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos máximo
        )

        stdout = resultado.stdout.strip()
        stderr = resultado.stderr.strip()

        if stdout:
            logger.info(f"dbt output:\n{stdout}")
        if stderr:
            logger.warning(f"dbt stderr:\n{stderr}")

        sucesso = resultado.returncode == 0
        return {
            'sucesso':    sucesso,
            'returncode': resultado.returncode,
            'stdout':     stdout,
            'stderr':     stderr
        }

    except subprocess.TimeoutExpired:
        logger.error("dbt timeout após 10 minutos")
        return {'sucesso': False, 'returncode': -1,
                'stdout': '', 'stderr': 'timeout'}

    except Exception as e:
        logger.error(f"dbt erro inesperado: {e}")
        return {'sucesso': False, 'returncode': -1,
                'stdout': '', 'stderr': str(e)}


@task(name="dbt_run", retries=1, retry_delay_seconds=30)
def executar_dbt_run():
    """
    Executa dbt run — Bronze → Silver → Intermediate → Gold.
    Falha explicitamente se qualquer modelo falhar.
    """
    logger = get_run_logger()
    logger.info("Iniciando dbt run — Bronze → Silver → Intermediate → Gold...")

    resultado = _executar_dbt(['dbt', 'run'], logger)

    if not resultado['sucesso']:
        logger.error(f"dbt run falhou — returncode: {resultado['returncode']}")
        return {
            'status':     'erro',
            'returncode': resultado['returncode'],
            'detalhe':    resultado['stderr'] or resultado['stdout']
        }

    # Extrai resumo do output do dbt
    linhas = resultado['stdout'].split('\n')
    resumo = next((l for l in linhas if 'of' in l and ('OK' in l or 'ERROR' in l
                   or 'PASS' in l)), resultado['stdout'][-200:])

    logger.info(f"dbt run concluído com sucesso")
    return {
        'status':     'ok',
        'returncode': 0,
        'resumo':     resumo
    }


@task(name="dbt_test", retries=0)
def executar_dbt_test():
    """
    Executa dbt test — valida qualidade dos dados em todas as camadas.
    Registra falhas mas não bloqueia o pipeline (warn, não erro crítico).
    """
    logger = get_run_logger()
    logger.info("Iniciando dbt test — validação declarativa...")

    resultado = _executar_dbt(['dbt', 'test'], logger)

    # Extrai contagem de PASS/FAIL da linha de resumo final do dbt
    # Formato: Done. PASS=59 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=59
    import re
    stdout = resultado['stdout']
    resumo_match = re.search(
        r'PASS=(\d+).*?ERROR=(\d+)',
        stdout
    )
    if resumo_match:
        pass_count = int(resumo_match.group(1))
        fail_count = int(resumo_match.group(2))
    else:
        # Fallback: conta ocorrências brutas
        pass_count = stdout.count('PASS')
        fail_count = stdout.count('FAIL') + stdout.count('ERROR')

    if not resultado['sucesso']:
        logger.warning(f"dbt test — {fail_count} falhas detectadas")
        return {
            'status':     'warn',
            'pass':       pass_count,
            'fail':       fail_count,
            'returncode': resultado['returncode'],
            'detalhe':    stdout[-500:]
        }

    logger.info(f"dbt test concluído — PASS={pass_count} FAIL={fail_count}")
    return {
        'status':     'ok',
        'pass':       pass_count,
        'fail':       fail_count,
        'returncode': 0
    }