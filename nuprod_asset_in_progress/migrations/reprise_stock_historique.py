# -*- coding: utf-8 -*-
"""Reprise du stock historique des immobilisations en cours (23x).

Livrable SÉPARÉ, **hors flux courant** (cf. spec §8). Ce script ne fait PAS partie
de l'automatisation : il sert à traiter le stock déjà bloqué en compte 23x (~2 M€
en 232000 chez le client) que la confirmation des nouvelles immos ne touchera pas.

Caractéristiques :
- **Idempotent** : ignore les assets ayant déjà une OD (`nu_transfer_move_id`).
- **Dry-run par défaut** : produit uniquement un rapport CSV, n'écrit rien.
- **Commit explicite** : crée les OD en **brouillon** (jamais posté) pour validation
  par le Cabinet Trouillot. La décision de comptabiliser et l'exercice de
  rattachement leur appartiennent.

Usage (depuis la racine Odoo) :

    # Dry-run (rapport seul, aucune écriture) :
    odoo shell -d <DB> --addons-path=... <<'PY'
    from odoo.addons.nuprod_asset_in_progress.migrations import reprise_stock_historique as r
    r.main(env, commit=False, csv_path='/tmp/reprise_immo_en_cours.csv')
    PY

    # Comptabilisation réelle (OD en brouillon) :
    #   ... r.main(env, commit=True, csv_path='/tmp/reprise_immo_en_cours.csv')

Le flag ``commit`` est explicite : par défaut le script ne crée rien.
"""
import csv
import logging

_logger = logging.getLogger(__name__)

CSV_HEADER = [
    'asset_id', 'asset_name', 'company', 'state',
    'compte_origine', 'compte_cible', 'montant',
    'date_proposee', 'statut',
]


def _candidates(env):
    """Assets confirmés issus d'un 23x, sans OD de virement (idempotence)."""
    return env['account.asset'].search([
        ('state', 'in', ('open', 'paused', 'close')),
        ('nu_is_in_progress', '=', True),
        ('nu_transfer_move_id', '=', False),
    ])


def _build_draft_move(asset, mapping):
    """Crée l'OD de virement en BROUILLON (jamais posté) et la lie à l'asset.

    Volontairement autonome : ne dépend ni du paramètre ``auto_post`` ni du
    garde-fou de date du flux courant (ces immos sont historiques, leur
    ``prorata_date`` peut être égale à l'``acquisition_date``).
    """
    distribution = asset.analytic_distribution or False
    move = asset.env['account.move'].create({
        'move_type': 'entry',
        'journal_id': mapping.nu_journal_id.id,
        'company_id': asset.company_id.id,
        'date': asset.prorata_date,
        'ref': "Reprise mise en service [%s] %s" % (asset.id, asset.name),
        'line_ids': [
            (0, 0, {
                'account_id': mapping.nu_target_account_id.id,
                'debit': asset.original_value, 'credit': 0.0,
                'name': asset.name, 'analytic_distribution': distribution,
            }),
            (0, 0, {
                'account_id': asset.nu_in_progress_account_id.id,
                'debit': 0.0, 'credit': asset.original_value,
                'name': asset.name, 'analytic_distribution': distribution,
            }),
        ],
    })
    asset.nu_transfer_move_id = move.id
    return move


def main(env, commit=False, csv_path='/tmp/reprise_immo_en_cours.csv'):
    """Point d'entrée. Retourne la liste des lignes de rapport (dicts).

    :param env: environnement Odoo (`env` dans `odoo shell`).
    :param commit: False (défaut) = dry-run, aucune écriture. True = crée les OD
        en brouillon. Aucun post automatique dans les deux cas.
    :param csv_path: chemin du rapport CSV produit.
    """
    assets = _candidates(env)
    _logger.info("Reprise immo en-cours : %s asset(s) candidat(s) (commit=%s).",
                 len(assets), commit)

    rows = []
    for asset in assets:
        mapping = asset._nu_get_transfer_map()
        company = asset.company_id
        src_code = asset.nu_in_progress_account_id._nu_code_for_company(company)
        if not mapping:
            statut = "IGNORÉ : aucun mapping configuré"
            target_code = ''
        else:
            target_code = mapping.nu_target_account_id._nu_code_for_company(company)
            if commit:
                move = _build_draft_move(asset, mapping)
                statut = "OD brouillon créée : %s" % move.name
            else:
                statut = "À comptabiliser (dry-run)"
        rows.append({
            'asset_id': asset.id,
            'asset_name': asset.name,
            'company': company.display_name,
            'state': asset.state,
            'compte_origine': src_code,
            'compte_cible': target_code,
            'montant': asset.original_value,
            'date_proposee': asset.prorata_date,
            'statut': statut,
        })

    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    _logger.info("Rapport écrit : %s (%s lignes).", csv_path, len(rows))

    if commit:
        _logger.warning(
            "%s OD de virement créées EN BROUILLON. Aucune n'est postée : "
            "validation Cabinet Trouillot requise avant comptabilisation.",
            sum(1 for r in rows if r['statut'].startswith('OD brouillon')))
    return rows
