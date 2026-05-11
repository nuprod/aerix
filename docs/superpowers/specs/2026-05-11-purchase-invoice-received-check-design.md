# Design — Blocage de validation de facture fournisseur sans réception

**Date** : 2026-05-11
**Client** : Aerix
**Module cible** : `nuprod_purchase_invoice_received_check`
**Odoo** : 19.0

## 1. Contexte et objectif

Le client Aerix souhaite garantir qu'une facture fournisseur ne soit jamais validée pour des quantités supérieures à ce qui a été effectivement reçu, sur le modèle du flux côté ventes où seule la marchandise expédiée est facturable.

Cas à gérer :

- Facture fournisseur **avec** ligne(s) liée(s) à un PO → contrôler que la quantité facturée n'excède pas la quantité reçue.
- Facture fournisseur **sans** ligne liée à un PO (saisie manuelle, frais annexes) → laisser valider normalement.
- Réception **partielle** → bloquer la validation, l'utilisateur ajuste lui-même les quantités sur la facture ou attend la réception.
- **Cumul** des factures précédentes pris en compte (pas de sur-facturation par splitting de facture).

## 2. Périmètre

### Exclusions du contrôle

- Lignes de facture sans `purchase_line_id` (aucune réception possible à comparer).
- Produits de type `service` (pas de réception physique pertinente).
- Factures de type `in_refund` (avoirs fournisseurs : la logique « pas reçu, pas facturé » ne s'applique pas en sens inverse).

### Inclusions

- Type de mouvement comptable : `in_invoice` uniquement.
- Tous les autres produits (consommables, stockables) reliés à un PO.

## 3. Architecture

### 3.1 Module

- **Nom** : `nuprod_purchase_invoice_received_check`
- **Version** : `19.0.0.0.0`
- **Author** : `NUprod`
- **Category** : `Accounting/Purchase`
- **Depends** : `["purchase_stock"]` (tire `purchase`, `stock`, `account` en transitif)
- **Application** : `False`
- **Installable** : `True`

### 3.2 Arborescence

```
nuprod_purchase_invoice_received_check/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── account_move.py
├── security/
│   └── security.xml
├── views/
│   └── account_move_views.xml
├── tests/
│   ├── __init__.py
│   └── test_invoice_received_check.py
└── static/description/icon.png
```

### 3.3 Approche technique retenue

Override de `account.move._post()` **+** champs computed pour un warning proactif affiché en draft (approche « C » : combine blocage strict et UX informative).

## 4. Modèle de données

Héritage pur de `account.move`. Aucun nouveau modèle custom.

| Champ | Type | Stocké | Rôle |
|---|---|---|---|
| `nu_has_invoice_over_received` | `Boolean` (computed) | Non | True si au moins une ligne facturée dépasse le reçu. |
| `nu_invoice_over_received_warning` | `Char` (computed) | Non | Texte du message affiché dans le bandeau d'alerte. |

**Dépendances du compute** :
- `invoice_line_ids`
- `invoice_line_ids.quantity`
- `invoice_line_ids.purchase_line_id`
- `invoice_line_ids.purchase_line_id.qty_received`
- `invoice_line_ids.purchase_line_id.qty_invoiced`
- `invoice_line_ids.product_id.type`
- `state`
- `move_type`

Non stocké → aucune migration, aucun coût SQL résiduel, recalcul à la volée à chaque ouverture.

## 5. Logique de contrôle

### 5.1 Méthode partagée

Une seule méthode `_nu_get_invoice_received_excesses()` sur `account.move` est appelée à la fois par le compute (warning) et par `_post()` (blocage), pour garantir l'équivalence stricte entre ce qui est affiché et ce qui bloque.

**Signature** :

```python
def _nu_get_invoice_received_excesses(self):
    """Pour chaque move, retourne la liste des dépassements détectés,
    agrégés par purchase.order.line.

    Returns:
        list[tuple]: [(purchase_line, qty_invoiced_total, qty_received), ...]
        où purchase_line est une purchase.order.line, qty_invoiced_total
        la somme prévue si la facture est validée, qty_received la quantité
        reçue sur cette PO line. Liste vide si aucun dépassement.
    """
```

### 5.2 Critères d'inclusion d'une ligne dans le contrôle

Une ligne est évaluée si **toutes** les conditions sont remplies :

1. `move.move_type == 'in_invoice'`
2. `line.purchase_line_id` est renseigné
3. `line.product_id.type != 'service'`

### 5.3 Règle de comparaison (cumul global)

Pour chaque `purchase.order.line` référencée par les lignes de la facture courante :

```
qty_already_other = purchase_line.qty_invoiced
                    - somme(quantité des lignes de CETTE facture qui pointent sur ce purchase_line)
qty_total_if_validated = qty_already_other + somme(lignes_courantes)
excess = qty_total_if_validated - purchase_line.qty_received
```

Si `excess > 1e-6` (tolérance flottants) : la ligne est en dépassement.

**Justification de la soustraction** : `purchase_line.qty_invoiced` inclut déjà les quantités de la facture courante (Odoo recalcule sur tous les `invoice_line_ids` non-cancelled liés, y compris la facture en draft). On retranche pour isoler le « déjà facturé sur d'autres factures », puis on ré-ajoute la quantité courante.

### 5.4 Override `_post`

```python
def _post(self, soft=True):
    for move in self:
        if move.move_type != 'in_invoice':
            continue
        if self.env.user.has_group(
            'nuprod_purchase_invoice_received_check.group_force_invoice_without_reception'
        ):
            continue
        excesses = move._nu_get_invoice_received_excesses()
        if excesses:
            details = "\n".join(
                "  - %s : facturé %s / reçu %s" % (po_line.product_id.display_name, total, recv)
                for po_line, total, recv in excesses
            )
            raise UserError(_(
                "Impossible de valider cette facture : les quantités facturées "
                "dépassent les quantités reçues pour :\n%s",
                details,
            ))
    return super()._post(soft=soft)
```

### 5.5 Compute du warning

```python
@api.depends(
    'move_type', 'state', 'invoice_line_ids',
    'invoice_line_ids.quantity',
    'invoice_line_ids.purchase_line_id',
    'invoice_line_ids.purchase_line_id.qty_received',
    'invoice_line_ids.purchase_line_id.qty_invoiced',
    'invoice_line_ids.product_id.type',
)
def _compute_nu_invoice_over_received(self):
    for move in self:
        excesses = (
            move._nu_get_invoice_received_excesses()
            if move.move_type == 'in_invoice' else []
        )
        move.nu_has_invoice_over_received = bool(excesses)
        if excesses:
            move.nu_invoice_over_received_warning = _(
                "Quantités facturées supérieures aux quantités reçues :\n%s",
                "\n".join(
                    "• %s : %s facturé / %s reçu" % (
                        po_line.product_id.display_name, total, recv,
                    )
                    for po_line, total, recv in excesses
                ),
            )
        else:
            move.nu_invoice_over_received_warning = False
```

## 6. Sécurité

### 6.1 Groupe de bypass

**Fichier** : `security/security.xml`

```xml
<odoo>
    <record id="group_force_invoice_without_reception" model="res.groups">
        <field name="name">Forcer la validation de facture sans réception</field>
        <field name="category_id" ref="base.module_category_accounting_accounting"/>
        <field name="comment">
            Permet de valider une facture fournisseur même si les quantités
            facturées dépassent les quantités reçues.
        </field>
    </record>
</odoo>
```

### 6.2 Décisions

- **Pas d'`implied_ids`** : groupe indépendant, à attribuer explicitement. Évite qu'un Account Manager ou Purchase Manager bypass par accident.
- **Pas d'ACL** (`ir.model.access.csv` absent) : aucun nouveau modèle.

## 7. Vues

### 7.1 Vue héritée du formulaire facture

**Fichier** : `views/account_move_views.xml`

```xml
<odoo>
    <record id="nu_account_move_form_inherit" model="ir.ui.view">
        <field name="name">account.move.form.nu.invoice.received.check</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <xpath expr="//sheet" position="before">
                <div class="alert alert-warning" role="alert"
                     invisible="not nu_has_invoice_over_received or state != 'draft' or move_type != 'in_invoice'">
                    <field name="nu_invoice_over_received_warning" readonly="1" nolabel="1"/>
                </div>
                <field name="nu_has_invoice_over_received" invisible="1"/>
            </xpath>
        </field>
    </record>
</odoo>
```

### 7.2 Décisions UX

- Bandeau visible **uniquement** sur `in_invoice` en `draft` avec dépassement → silencieux dans tous les autres cas.
- `nu_has_invoice_over_received` rendu en `invisible="1"` car les expressions `invisible` du client Odoo 17+ ne peuvent lire que des champs présents dans le formulaire.
- Bandeau d'avertissement (`alert-warning`) et non d'erreur (`alert-danger`) car la facture reste éditable.

## 8. Conventions Nuprod appliquées

Vérifié contre la skill `check-odoo-structure` :

| Règle | Application |
|---|---|
| Préfixe `nuprod_` du dossier | `nuprod_purchase_invoice_received_check` |
| Nom de fichier modèle hérité | `account_move.py` (= `account.move` avec `.` → `_`) |
| Classe Python (héritage pur) | `AccountMove` (CamelCase libre, pas de préfixe `Nu` obligatoire) |
| Préfixe `nu_` sur champs ajoutés | `nu_has_invoice_over_received`, `nu_invoice_over_received_warning` |
| Préfixe boolean `nu_has_` | `nu_has_invoice_over_received` ✓ |
| Préfixe `nu_` sur IDs XML | `nu_account_move_form_inherit` |
| `static/description/icon.png` | Présent |

## 9. Tests

**Fichier** : `tests/test_invoice_received_check.py`

| # | Test | Setup | Assertion attendue |
|---|---|---|---|
| 1 | `test_invoice_no_purchase` | Facture saisie manuelle, sans `purchase_line_id` | `_post()` passe, `nu_has_invoice_over_received` False |
| 2 | `test_invoice_fully_received` | PO 10, reçu 10, facture 10 | `_post()` passe, pas de warning |
| 3 | `test_invoice_partially_received_blocks` | PO 10, reçu 4, facture 10 | `_post()` lève `UserError`, warning mentionne 10/4 |
| 4 | `test_invoice_partially_received_at_received_qty` | PO 10, reçu 4, facture 4 | `_post()` passe |
| 5 | `test_service_line_always_allowed` | PO produit type `service`, reçu 0, facture 10 | `_post()` passe |
| 6 | `test_refund_always_allowed` | `in_refund` avec ligne PO non reçue | `_post()` passe |
| 7 | `test_cumulative_invoicing_blocks` | PO 10, reçu 6, 1re facture 6 validée, 2e facture 4 | 2e `_post()` lève `UserError` (cumul 10 > reçu 6) |
| 8 | `test_cumulative_invoicing_within_received` | PO 10, reçu 8, 1re facture 5 validée, 2e facture 3 | 2e `_post()` passe (cumul 8 = reçu 8) |
| 9 | `test_mixed_line_only_po_lines_checked` | 1 ligne PO non reçue + 1 ligne libre | `_post()` lève `UserError` mentionnant uniquement la ligne PO |
| 10 | `test_bypass_group_allows_validation` | Idem #3 mais user dans `group_force_invoice_without_reception` | `_post()` passe |
| 11 | `test_warning_recomputed_on_quantity_change` | Facture draft avec dépassement, modif quantité sous le reçu | `nu_has_invoice_over_received` repasse à False |
| 12 | `test_multiple_invoice_lines_same_po_line` | 2 lignes facture sur même `purchase_line_id`, somme > reçu | `_post()` lève `UserError` |

## 10. Hors périmètre (YAGNI)

- Pas de gestion du split automatique de facture en cas de partiel.
- Pas d'ajustement automatique des quantités à la validation.
- Pas d'écran de saisie de justification au bypass (un simple groupe suffit, traçabilité par `write_uid` sur la facture).
- Pas de configuration par société ou par type de produit (règle globale).
- Pas de logique inverse sur les avoirs fournisseurs.
