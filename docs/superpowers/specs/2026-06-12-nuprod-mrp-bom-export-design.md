# nuprod_mrp — Export Excel de la nomenclature

Date : 2026-06-12
Statut : validé

## Objectif

Permettre l'export Excel d'une nomenclature (`mrp.bom`) au format
`(niveau, réf interne, désignation, quantité, unité, coût)`, en explosant
récursivement les sous-nomenclatures et en numérotant le niveau de chaque ligne.

## Emplacement & dépendances

- Module : `custom/aerix/nuprod_mrp/`
- Dépend de : `mrp`
- Librairie : `xlsxwriter` (3.2.0, déjà installée)

## Déclencheur

Bouton **« Export Excel »** ajouté dans la barre de boutons du formulaire
`mrp.bom`, via héritage de la vue `mrp.mrp_bom_form_view`.

## Logique d'explosion (récursive, multi-niveaux)

Méthode `_collect_export_lines(factor, level, visited)` sur `mrp.bom` :

- **Niveau 0** : ligne d'en-tête = produit fini de la BOM (qté = `product_qty`
  de la BOM, ramenée à l'unité de référence).
- **Niveau 1** : composants directs (`bom_line_ids`).
- **Niveau 2+** : pour chaque composant possédant sa propre nomenclature
  (`_bom_find`), descente récursive.
- **Quantités cumulées** : chaque ligne porte `factor × line.product_qty`,
  où `factor` est le produit des quantités des parents — soit le besoin réel
  pour produire 1 unité (en réalité `product_qty` unités) du produit fini.
- **Garde-fou anti-boucle** : un `set` des IDs de BOM déjà visités dans la
  branche courante empêche toute récursion infinie (BOM auto-référencée).

## Colonnes du fichier Excel

| Niveau | Réf. interne | Désignation | Quantité | Unité | Coût unitaire | Coût ligne |
|--------|--------------|-------------|----------|-------|---------------|------------|

- **Réf. interne** : `product.default_code`
- **Désignation** : `product.display_name` (ou `name`)
- **Quantité** : quantité cumulée
- **Unité** : `uom_id.name`
- **Coût unitaire** : `product.standard_price`
- **Coût ligne** : coût unitaire × quantité cumulée

Mise en forme :
- En-têtes en gras avec fond.
- Indentation visuelle de la désignation selon le niveau.
- Ligne de total des coûts en bas.
- Colonnes monétaires formatées.

## Livraison du fichier

1. Le bouton appelle `action_export_bom_xlsx`.
2. La méthode génère le `.xlsx` en mémoire avec `xlsxwriter` (BytesIO).
3. Création d'un `ir.attachment` (nom `Nomenclature_<ref>.xlsx`).
4. Retour d'une `ir.actions.act_url` vers `/web/content/<id>?download=true`
   → téléchargement immédiat, sans wizard intermédiaire.

## Structure des fichiers

```
nuprod_mrp/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── mrp_bom.py
├── views/
│   └── mrp_bom_views.xml
└── static/description/icon.png
```

## Hors périmètre (YAGNI)

- Pas de wizard de configuration (options de colonnes, etc.).
- Pas d'export multi-BOM en lot.
- Pas de gestion des variantes au-delà de ce que `_bom_find` retourne.
