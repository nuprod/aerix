# Design — Matching fournisseur OCR sur factures forwardées

**Date** : 2026-05-11
**Client** : Aerix
**Module cible** : `nuprod_account_invoice_extract_partner`
**Odoo** : 19.0 Enterprise

## 1. Contexte et objectif

Chez Aerix, la majorité (>80 %) des factures fournisseurs arrivent par transfert interne : un collaborateur forward le PDF reçu vers `achats@aerix.odoo.com`. Odoo crée alors la facture en draft avec le `partner_id` du **transféreur** (le collaborateur), et non du vrai fournisseur. L'OCR Enterprise extrait pourtant correctement le nom du fournisseur dans `extract_partner_name` et les données structurées dans `extract_prefill_data` (dont la VAT), mais ce matching n'est jamais appliqué parce que `partner_id` est déjà rempli.

### Cause racine

Dans `account_invoice_extract/models/account_invoice.py::_save_form`, le matching natif n'est appelé **que si `partner_id` est vide** :

```python
with self._get_edi_creation() as move_form:
    if not move_form.partner_id:                # bloque le matching OCR
        partner_id, created = self._get_partner(ocr_results)
        if partner_id:
            move_form.partner_id = partner_id
```

Or `mail.thread.message_new` pré-remplit `partner_id` avec le sender du mail (cf. comportement standard `mail.alias`).

### Objectif

Garantir que le `partner_id` final d'une facture fournisseur reçue par transfert interne soit le **vrai fournisseur**, identifié de la donnée la plus fiable du PDF (VAT/SIREN) — pas le transféreur.

### Succès opérationnel

- Sur les factures arrivées par `achats@aerix.odoo.com`, le `partner_id` reflète le fournisseur OCR-identifié (≥ taux actuel de bons matchs natifs + gain SIREN).
- Aucune régression sur les factures créées par d'autres canaux (drag-and-drop, API, manuel).
- Le matching natif Enterprise (VAT → previous extracts → IBAN → nom → création VIES) reste intact ; on l'enrichit et on le déverrouille.

## 2. Périmètre

### Inclusions

- Type de mouvement : `in_invoice`, `in_refund`.
- Journaux de type `purchase` pour l'override `message_new`.
- Toutes les factures pour les overrides `_save_form` / `_get_partner` (le filtre métier est dans le code, pas dans le déclencheur).

### Exclusions

- Pas d'override pour les journaux `sale` (le sender d'un mail sur l'alias ventes EST légitimement le client).
- Pas de matching par SIRET parsé du texte OCR brut (rejeté en brainstorming — fragile).
- Pas de matching par email d'origine dans un mail forwardé (rejeté — parser fragile).
- Pas de wizard de réconciliation manuelle en cas d'ambiguïté (tranchage silencieux par `supplier_rank`).

## 3. Architecture

### 3.1 Module

- **Nom** : `nuprod_account_invoice_extract_partner`
- **Version** : `19.0.0.0.0`
- **Author** : `NUprod`
- **Category** : `Accounting/Accounting`
- **Depends** : `["account_invoice_extract", "l10n_fr_siret"]`
- **Application** : `False`
- **Installable** : `True`

### 3.2 Arborescence

```
nuprod_account_invoice_extract_partner/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── account_move.py
├── tests/
│   ├── __init__.py
│   └── test_extract_partner.py
└── static/description/icon.png
```

Aucun nouveau modèle, aucune vue, aucun group, aucune ACL.

### 3.3 Flux nominal (mail forwardé)

```
1. Collaborateur forward facture-fournisseur.pdf → achats@aerix.odoo.com
2. mail.thread.message_new (override Nuprod) :
   - journal Achats détecté → check si email_from résout à res.users
     actif non-portail (share=False)
   - oui → custom_values.pop('partner_id', None)
   - facture créée en draft, partner_id vide
3. account_invoice_extract envoie le PDF à IAP (natif)
4. IAP répond → _check_status → _save_form (natif)
5. _save_form entre dans `if not move_form.partner_id:` → _get_partner
6. _get_partner (override Nuprod) tente dans cet ordre :
   a. VAT exacte (natif)
   b. SIREN dérivé de VAT FR  (NOUVEAU)
   c. previous extracts (natif)
   d. IBAN (natif)
   e. Name fuzzy (natif)
   f. Création depuis VAT via VIES (natif, si partner_autocomplete)
7. partner_id appliqué sur la facture
```

### 3.4 Flux de rattrapage

Pour les factures créées avant install ou via un autre canal qui aurait quand même réussi à mettre un user interne en `partner_id` :

```
_save_form override :
  Si move_type ∈ {in_invoice, in_refund}
  ET partner_id pointe vers un user interne (non-portail, actif)
  → on remet partner_id à False juste avant super()
  → le natif reprend la main, applique son matching
```

Si le matching ne trouve rien, `partner_id` reste vide → l'utilisateur tranche manuellement. Compromis assumé : mieux vaut un champ vide qui force la saisie qu'un mauvais `partner_id` (= transféreur) qui induit la compta en erreur.

## 4. Modèle de données

Héritage pur de `account.move`. **Aucun champ ajouté**, aucune migration, aucune ACL.

Tout le comportement est du code (overrides de méthodes).

## 5. Logique

### 5.1 Détection sender interne

Méthode partagée, utilisée par `message_new` et `_save_form` :

```python
def _nu_is_internal_sender(self, email_from):
    """True si email_from correspond à un employé interne
    (res.users actif, non-portail)."""
    if not email_from:
        return False
    parsed = tools.email_normalize(email_from)
    if not parsed:
        return False
    user = self.env['res.users'].sudo().search(
        [('active', '=', True),
         ('share', '=', False),
         ('partner_id.email_normalized', '=', parsed)],
        limit=1,
    )
    return bool(user)
```

Choix de design :

- `sudo()` ciblé sur `res.users` uniquement (les contributeurs sur l'alias mail n'ont pas forcément le droit de lire `res.users`).
- `email_normalize` : tolérant aux variantes "Prenom Nom <mail@...>" et à la casse.
- `share=False` : exclut les users portail (un fournisseur ayant un accès portail doit être traité comme externe).
- `active=True` : un user désactivé est traité comme externe (acceptable — un ancien employé qui revient sur un vieux mail forwardé ne doit pas court-circuiter le matching).

### 5.2 Override `message_new` (amont)

```python
@api.model
def message_new(self, msg_dict, custom_values=None):
    custom_values = dict(custom_values or {})
    journal_id = (
        custom_values.get('journal_id')
        or self.env.context.get('default_journal_id')
    )
    journal = (
        self.env['account.journal'].browse(journal_id)
        if journal_id else self.env['account.journal']
    )
    if (
        journal.type == 'purchase'
        and self._nu_is_internal_sender(msg_dict.get('email_from'))
    ):
        custom_values.pop('partner_id', None)
    return super().message_new(msg_dict, custom_values=custom_values)
```

Conservation de la traçabilité : on ne touche pas à `email_from` ni au `mail.message` créé par `mail.thread` — la trace du transféreur reste dans le chatter de la facture.

### 5.3 Matching enrichi par SIREN

```python
SIREN_FROM_VAT_FR_RE = re.compile(r'^FR[0-9A-Z]{2}([0-9]{9})$')

def _nu_find_partner_by_siren_from_vat(self, vat_number_ocr):
    """Si la VAT OCR est française, extrait le SIREN (9 derniers chiffres)
    et cherche un res.partner.siret qui commence par ce SIREN."""
    if not vat_number_ocr:
        return False
    cleaned = re.sub(r'\s', '', vat_number_ocr.upper())
    match = SIREN_FROM_VAT_FR_RE.match(cleaned)
    if not match:
        return False
    siren = match.group(1)
    return self.env['res.partner'].search(
        [*self.env['res.partner']._check_company_domain(self.company_id),
         ('siret', '=like', f'{siren}%')],
        order='supplier_rank desc', limit=1,
    )
```

Justification :

- `=like` parce que `partner.siret` est sur 14 chiffres (SIREN + NIC), et la VAT FR ne contient que le SIREN du siège.
- Tri `supplier_rank desc` pour privilégier les fournisseurs historiques en cas de multi-établissements.
- Format VAT FR : `FR` + 2 caractères de clé (chiffres ou lettres pour la clé numérique alphanumérique) + 9 chiffres SIREN.

### 5.4 Override `_get_partner`

```python
def _get_partner(self, ocr_results):
    vat_number_ocr = self._get_ocr_selected_value(
        ocr_results, 'VAT_Number', "",
    )
    if vat_number_ocr:
        partner_vat = self._find_partner_id_with_vat(vat_number_ocr)
        if partner_vat:
            return partner_vat, False
        partner_siren = self._nu_find_partner_by_siren_from_vat(
            vat_number_ocr,
        )
        if partner_siren:
            return partner_siren, False
    return super()._get_partner(ocr_results)
```

Insertion du SIREN **juste après** le VAT match (qui aurait reconnu une VAT identique en base) et **avant** previous extracts / IBAN / nom (plus faillibles). Ordre de fiabilité respecté.

### 5.5 Override `_save_form` (rattrapage)

```python
def _save_form(self, ocr_results):
    needs_override = (
        self.move_type in ('in_invoice', 'in_refund')
        and self.partner_id
        and self._nu_is_internal_sender(self.partner_id.email)
    )
    if needs_override:
        self.partner_id = False
    return super()._save_form(ocr_results)
```

Minimaliste : on déverrouille la branche `if not move_form.partner_id:` du natif, qui fait tout le reste.

## 6. Sécurité

- **Pas de groupe de bypass** : le module n'introduit pas de blocage, juste un meilleur matching. Un mauvais résultat reste éditable manuellement.
- **`sudo()` ciblé** sur la recherche `res.users` dans `_nu_is_internal_sender` uniquement.
- **Pas d'ACL** : aucun nouveau modèle.

## 7. Conventions Nuprod appliquées

Vérifié contre la skill `check-odoo-structure` :

| Règle | Application |
|---|---|
| Préfixe `nuprod_` du dossier | `nuprod_account_invoice_extract_partner` |
| Nom de fichier modèle hérité | `account_move.py` (= `account.move` avec `.` → `_`) |
| Classe Python (héritage pur) | `AccountMove` |
| Préfixe `_nu_` sur méthodes ajoutées | `_nu_is_internal_sender`, `_nu_find_partner_by_siren_from_vat` |
| Pas de champ ajouté | n/a (rien à préfixer en `nu_`) |
| `static/description/icon.png` | À fournir |

## 8. Edge cases

| Cas | Comportement |
|---|---|
| Sender = vrai fournisseur externe (forward direct) | `_nu_is_internal_sender` retourne False → `partner_id` conservé. |
| Sender = user portail (share=True) | Idem : traité comme externe. |
| Sender interne sur journal Ventes | Pas de pop, comportement natif intact. |
| `email_from` absent (création API, drag-and-drop) | `message_new` non concerné. Rattrapage `_save_form` non déclenché (pas de user interne en partner_id). |
| VAT OCR non-FR (ex. `BE0123456789`) | Regex SIREN ne match pas → fallback natif. |
| VAT FR mais aucun SIRET en base | `_nu_find_partner_by_siren_from_vat` retourne False → fallback natif. |
| Multi-établissements même SIREN | Choix du `supplier_rank` le plus élevé. |
| OCR sans VAT/IBAN/nom | `partner_id` reste vide (natif inchangé). |
| Facture créée avant install | Au prochain passage OCR : rattrapage `_save_form` si `partner_id` = user interne. |
| User interne désactivé entre-temps | Considéré comme externe (compromis assumé). |
| VAT mal OCR-isée | SIREN dérivé faux → ne matche rien → fallback nom. Pas de faux positif. |

## 9. Tests

**Fichier** : `tests/test_extract_partner.py`
**Base** : `TestAccountInvoiceExtractCommon` si réutilisable depuis `account_invoice_extract`, sinon `AccountTestInvoicingCommon` + mock IAP.

| # | Test | Setup | Assertion |
|---|---|---|---|
| 1 | `test_internal_sender_partner_id_dropped_on_purchase` | Journal Achats + `message_new` avec `email_from` d'un user interne | facture créée, `partner_id` vide |
| 2 | `test_external_sender_partner_id_kept_on_purchase` | Journal Achats + `email_from` inconnu en base | `partner_id` set (mécanisme natif) |
| 3 | `test_portal_user_treated_as_external` | Journal Achats + `email_from` d'un user `share=True` | `partner_id` set (pas droppé) |
| 4 | `test_internal_sender_on_sale_journal_kept` | Journal Ventes + user interne | `partner_id` non droppé |
| 5 | `test_inactive_user_treated_as_external` | User interne mais `active=False` | `partner_id` non droppé |
| 6 | `test_get_partner_matches_by_vat_first` | OCR VAT exacte d'un partner existant | retourne ce partner, SIREN non interrogé |
| 7 | `test_get_partner_matches_by_siren_fallback` | OCR VAT FR jamais vue, mais SIRET en base avec ce SIREN | retourne le partner SIREN |
| 8 | `test_siren_match_picks_highest_supplier_rank` | 2 établissements même SIREN, rank différents | retourne celui avec `supplier_rank` le plus élevé |
| 9 | `test_siren_no_match_falls_back_to_native` | VAT FR sans SIRET correspondant | `super()._get_partner` appelé |
| 10 | `test_non_french_vat_skips_siren` | VAT belge (`BE0XXXXXXXX`) | SIREN non tenté, super() direct |
| 11 | `test_malformed_vat_skips_siren` | VAT avec caractères impossibles | regex ne match pas, super() direct |
| 12 | `test_save_form_overrides_internal_partner` | Facture avec `partner_id` = user interne + OCR retourne VAT d'un fournisseur réel | `partner_id` réécrit |
| 13 | `test_save_form_keeps_external_partner` | Facture avec `partner_id` = vrai partenaire externe + OCR | `partner_id` conservé |
| 14 | `test_save_form_internal_partner_no_ocr_match` | `partner_id` = user interne, OCR sans match | `partner_id` reste vide |

## 10. Hors périmètre (YAGNI)

- Pas de matching par SIRET parsé du texte OCR brut.
- Pas de parsing de l'email d'origine dans un mail forwardé.
- Pas de matching IBAN enrichi (le natif suffit).
- Pas d'UI de configuration.
- Pas de wizard de réconciliation manuelle sur multi-match.
- Pas de suppression de l'automation rule existante côté Aerix : le user pourra la désactiver après validation en pré-prod.

## 11. Migration / déploiement

- Module à installer puis tester en pré-prod sur quelques factures de chaque cas (mail forwardé interne, mail direct fournisseur, drag-and-drop, manuel).
- Une fois validé : désactiver la server action + automation rule existantes (le module les remplace).
- Pas de migration de données : aucun champ ajouté, aucun récalcul nécessaire.
