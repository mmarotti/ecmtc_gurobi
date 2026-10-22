# ECMTC com gurobipy

## Instalação

```bash
pip install -r requirements.txt
```

Requer licença do Gurobi instalada (ex.: acadêmica).

## Uso

```bash
python ecmtc_gurobi.py paper_example.json
python ecmtc_gurobi.py paper_example.json -o result.json --verbose
```

Opções: `--eps` (degradação relativa permitida na energia, padrão 1e-9), `--time-limit`,
`--threads`, `--verbose` (log do Gurobi).

## Formato da instância

```json
{
  "name": "texto livre",
  "T": 6,
  "D": 15.0,
  "resources": [
    {"id": 1, "A": [0, 1, 2], "P": [0, 2.0, 4.0], "E": [0, 3.5, 6.5]}
  ]
}
```

`P[k]` e `E[k]` são o tempo e a energia para `A[k]` tarefas.

## Modelo

Variáveis: $y_{ij} \in \lbrace 0,1 \rbrace$ (recurso $i$ recebe $j$ tarefas), para todo $j \in A_i$,
e $C_{\max} \ge 0$.

```math
\begin{aligned}
\text{lex min} \quad & \left( \sum_{i \in \mathcal{R}} \sum_{j \in A_i} E_{ij})\, y_{ij}\ ,\ \ C_{\max} \right) \\
\text{s.a.} \quad & \sum_{j \in A_i} y_{ij} = 1 && \forall i \in \mathcal{R} \\
& \sum_{i \in \mathcal{R}} \sum_{j \in A_i} j \, y_{ij} = T \\
& C_{\max} \ge \sum_{j \in A_i} P_{ij}\, y_{ij} && \forall i \in \mathcal{R} \\
& C_{\max} \le D \\
& y_{ij} \in \{0,1\} && \forall i \in \mathcal{R},\ j \in A_i \\
& C_{\max} \ge 0
\end{aligned}
```

A ordem lexicográfica é resolvida com objetivos hierárquicos do Gurobi (`setObjectiveN`):
energia com prioridade 2 e makespan com prioridade 1. Ao otimizar o makespan, a energia
pode piorar no máximo `reltol = eps` (relativo).
