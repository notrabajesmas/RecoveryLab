# RecoveryLab — Work Log

---
Task ID: 2
Agent: Main
Task: Strategy Crossover Curve — H2 and H3

Work Log:
- Reframed H2: "Existe una frontera observable donde la estrategia óptima cambia según el estado del medio"
- Created H3: "No existe una estrategia de recuperación universalmente óptima"
- Built crossover_curve.py: progressive MFT degradation (0%→100%) with 3 strategies
  - 21 data points, 5 repetitions per point, statistical analysis (CI, p-value, Cohen's d)
  - Visualization with 4 panels: Recovery Rate, Delta, Significance, Effect Size
- Ran crossover curve experiment
  - Crossover at 95% MFT damage (gradual)
  - Carving is constant at 6.7% (doesn't depend on MFT)
  - MFT-First degrades linearly with MFT damage
  - At 100% MFT damage, Carving wins (6.7% vs 0.0%)
- H3 is now SUPPORTED (1S/0R): MFT-First doesn't win everywhere, Carving doesn't win everywhere
- H2 is INCONCLUSIVE (2S/1R): Frontier exists but crossover is at 95% (too high for practical use)

Stage Summary:
- Key finding: Carving is constant (6.7%) regardless of MFT damage — this is the "floor" of recovery
- MFT-First degrades linearly — it crosses the Carving floor at 95% damage
- The crossover exists but is at a very high damage level
- Problem: Carving only recovers files with detectable signatures (JPEG, PNG, PDF)
- Files without signatures (TXT, EXE, DLL, AVI, CR2, NEF, MOV, JSON) are invisible to Carving
- This means the crossover curve is dominated by the "invisible files" problem
- Next step: Need to separate the crossover by FILE TYPE (JPEG vs PDF vs TXT)
