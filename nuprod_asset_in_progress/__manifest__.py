{
    'name': "Nuprod — Immobilisations en cours (mise en service)",
    'version': '19.0.2.0.0',
    'summary': "Virement comptable immobilisation en cours (23x) → définitive (21x/205x) à la mise en service",
    'description': """
Nuprod — Immobilisations en cours
=================================
Automatise le virement de bilan ``23x → 21x/205x`` à la mise en service d'une
immobilisation, étape du PCG français absente d'Odoo standard et d'OCA
``account_asset_management``.

- Détection automatique des ``account.asset`` issus d'un compte 23x (en-cours).
- Compte définitif cible déterminé par un mapping de configuration (par société).
- Génération d'une OD de virement ``débit 21x / crédit 23x`` à la mise en service.
- Idempotence (jamais deux OD pour le même asset).
- OD en brouillon par défaut (paramétrable vers posté).
- Garde-fou date avec dérogation explicite (ne vide jamais ``prorata_date``).
""",
    'author': "Nuprod",
    'website': 'https://www.nuprod.fr',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['account_asset'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/nu_asset_transfer_map_views.xml',
        'views/account_asset_views.xml',
    ],
    'installable': True,
    'application': False,
}
