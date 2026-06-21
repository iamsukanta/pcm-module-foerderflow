"""seeds — system reference data + demo/pilot org seeds (ported from scripts/seed-*.ts).

Modules
-------
system_data : Kostenbereiche (SKR42) + TVöD-D 2025 tariff table (org_id IS NULL).
demo        : demo org "Zukunft für Kinder" — full dataset. Supports DEMO_RESET=1.
pilot_fam   : pilot org "Freunde alter Menschen e.V." — master data + booking rules,
              with --reset-rules / --reset-transactions / --reset-all CLI flags.
reset       : FK-aware reset_org_data / reset_transactions / reset_rules helpers.
"""
