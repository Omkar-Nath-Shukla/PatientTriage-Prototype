# PatientTriage.ai : Prototype

Accenture Innovation Challenge 2026, Round 2 prototype.
Implements a hybrid ESI (Emergency Severity Index) triage engine with
age-adjusted thresholds, escalation-bias safety design, the 90/10 bed
buffer rule from our Round 1 proposal, waiting-queue monitoring, and
clinician override with a full audit trail.

## Files

| File | Purpose |
|---|---|
| `models.py` | Data schema reference - every input/output field documented, plus shared constants (danger zones, keywords, wait thresholds) |
| `generate_patients.py` | Synthetic patient generator, includes mandatory edge cases (ambiguous, pediatric, geriatric, zero-history, subjective-urgency-mismatch, pregnancy-high-risk, immunosuppressed-rapid-onset) |
| `triage_engine.py` | Core ESI decision-tree engine: life-threat -> high-risk -> resource prediction -> vitals danger-zone, plus confidence scoring and escalation bias |
| `bed_management.py` | 90/10 buffer rule bed allocation |
| `queue_monitor.py` | Waiting-queue monitoring, wait-time estimate adjusted by doctors on duty, automatic reassessment triggers |
| `override_log.py` | Clinician override capture + audit trail (DPDP Act 2023 / DPDP Rules 2025 aligned) |
| `main.py` | Runs the full pipeline end-to-end and prints a demo-ready summary |

## How to run

```bash
python3 main.py
```

This will:
1. Generate 20 synthetic patients and triage them, allocating beds under the 90/10 rule
2. Run a 3x surge simulation and compare against a no-buffer baseline
3. Monitor the waiting queue and flag patients who exceeded their safe wait threshold
4. Log a sample clinician override to `audit_log.json`

Individual modules can also be run standalone for focused testing, e.g.
`python3 triage_engine.py` or `python3 bed_management.py`.

## Design principles implemented

- **Explainability**: every ESI decision carries a `decision_trace` showing exactly which rule fired
- **Escalation bias**: when confidence < 60%, the system escalates one ESI level, never downgrades
- **Age-adjusted safety**: pediatric/adult/geriatric vitals use different danger-zone thresholds
- **Hybrid ESI**: combines structured vitals with unstructured symptom-text keyword scanning
- **Broader clinical context**: body weight (pediatric extreme-weight risk), symptom onset timing
  (rapid onset = higher risk for the same complaint), chronic illness burden (immunosuppressed/COPD/
  CKD/cancer patients get extra resource weighting), and pregnancy status (pregnancy-specific red-flag
  complaints and symptoms trigger automatic high-risk classification)
- **90/10 buffer rule**: 10% of beds reserved exclusively for ESI 1-2, demonstrated to rescue
  critical patients during a simulated surge who would otherwise be waitlisted
- **DPDP-aligned audit trail**: every override records who, when, original vs new value, and why
