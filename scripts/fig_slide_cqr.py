"""
fig_slide_cqr.py — Replot da Figura CQR otimizado para slide (fonte grande)
Não retreina nada — lê o CSV já salvo por 02_intervalos_confianca.py
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

MESES_PT = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

def formatar_mes_pt(x, pos):
    data = mdates.num2date(x)
    return f"{MESES_PT[data.month]}/{data.year}"

REPORTS_DIR = Path("reports/intervalos")

# 1. Carregar dados já calculados (zero retreino)
df = pd.read_csv(REPORTS_DIR / "previsoes_com_intervalos.csv", parse_dates=["data_se"])
df = df[(df["alpha"] == 0.10) & (df["fase"] == "avaliacao")].sort_values("data_se")

# 2. Fontes grandes para leitura em telão
plt.rcParams.update({
    "font.size": 16,
    "axes.labelsize": 12,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 18,
})

fig, ax = plt.subplots(figsize=(8, 5.5))

ax.fill_between(
    df["data_se"], df["lower_calibrado"], df["upper_calibrado"],
    alpha=0.30, color="#2196F3", label="Intervalo CQR (90%)",
)
ax.plot(df["data_se"], df["y_real"], "k-", linewidth=2.5, label="Casos reais")
ax.plot(df["data_se"], df["y_pred"], "--", color="#1565C0", linewidth=2, label="Previsão (mediana)")
ax.margins(y=0.08)

ax.set_xlabel("Semana Epidemiológica")
ax.set_ylabel("Casos confirmados/semana")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, fontsize=13, frameon=True)
ax.xaxis.set_major_formatter(plt.FuncFormatter(formatar_mes_pt))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
plt.xticks(rotation=40, ha="right")
plt.subplots_adjust(top=0.80, bottom=0.28)

path = REPORTS_DIR / "fig_slide_cqr_90pct.png"
fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.3)
print(f"Salvo: {path}")