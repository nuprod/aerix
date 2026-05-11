# -*- coding: utf-8 -*-
{
    "name": "nuprod_account_invoice_extract_partner",
    "summary": "Force le matching OCR du fournisseur sur les factures "
               "transférées par mail, et ajoute un matching par SIREN FR.",
    "description": """
      Sur les factures fournisseurs créées via mail.alias, ne pas écrire le
      partner_id du transféreur interne pour laisser l'OCR Odoo identifier le
      vrai fournisseur. Enrichit le pipeline de matching natif avec un
      fallback par SIREN dérivé de la VAT française. Fournit un mécanisme de
      rattrapage pour les factures dont le partner_id pointe encore vers un
      utilisateur interne au moment du traitement OCR.
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Accounting/Accounting",
    "version": "19.0.0.0.0",
    "depends": ["account_invoice_extract", "l10n_fr_siret"],
    "data": [],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
}
