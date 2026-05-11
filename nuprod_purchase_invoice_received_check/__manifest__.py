# -*- coding: utf-8 -*-
{
    "name": "nuprod_purchase_invoice_received_check",
    "summary": "Bloque la validation d'une facture fournisseur si la réception "
               "liée n'est pas réalisée.",
    "description": """
      Bloque la validation d'une facture fournisseur dont les quantités
      facturées dépassent les quantités reçues sur les lignes d'achat liées.
      Les factures sans achat lié, les lignes de service et les avoirs
      fournisseurs sont exclus du contrôle. Un groupe dédié permet de forcer
      la validation.
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Accounting/Purchase",
    "version": "19.0.0.0.0",
    "depends": ["purchase_stock"],
    "data": [
        "security/security.xml",
        "views/account_move_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
}
