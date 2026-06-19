==================================================
Nuprod — Immobilisations en cours (mise en service)
==================================================

Automatise le virement comptable **immobilisation en cours (23x) →
immobilisation définitive (21x / 205x)** lors de la mise en service d'un bien,
étape du Plan Comptable Général français absente d'Odoo standard et du module
OCA ``account_asset_management``.

Fonctionnement
==============

1. **Détection** — un ``account.asset`` dont le compte d'origine
   (``account_asset_id``, calculé depuis les lignes d'écriture d'origine) a un
   code commençant par ``23`` est marqué ``nu_is_in_progress``.
2. **Configuration** — un mapping *(société, compte 23x) → (compte définitif,
   journal d'OD)* est défini dans **Comptabilité → Configuration →
   Immobilisations en cours**.
3. **Mise en service** — à la confirmation de la fiche (méthode ``validate``,
   bouton « Confirm »), une **OD de virement** ``débit 21x/205x / crédit 23x``
   du montant ``original_value`` est générée et liée à la fiche
   (``nu_transfer_move_id``).
4. **Idempotence** — un asset déjà pourvu d'une OD n'en reçoit jamais une seconde.

Paramétrage
===========

- ``nuprod_asset_in_progress.auto_post`` (``ir.config_parameter``) :

  - ``False`` (**défaut**) : l'OD est créée en **brouillon** (relecture/post par
    le comptable).
  - ``True`` : l'OD est **postée automatiquement** à la mise en service.

Garde-fou de date
=================

La mise en service exige une **Date de prorata = date de mise en service**. Si
``prorata_date`` est égale à ``acquisition_date`` (l'utilisateur n'a rien saisi),
la confirmation est **bloquée** par un message explicite. Le champ ``prorata_date``
(NOT NULL) n'est **jamais** vidé.

Dérogation : cocher **« Forcer la mise en service »** (``nu_is_force_in_service``)
autorise la confirmation lorsque la mise en service a effectivement lieu le jour
de l'acquisition.

Accès au code comptable (note technique)
========================================

En Odoo 17+/19, ``account.account.code`` n'est **pas** un champ stocké : c'est un
*computed* dépendant du contexte société (``code_store``, jsonb indexé par root
company). Le module ne lit **jamais** le jsonb à la main et n'utilise aucune clé
codée en dur : tout passe par ``account.account._nu_code_for_company(company)``
(= ``with_company(company).code``), couvert par un test anti-régression.

Reprise du stock historique
===========================

Le module ne traite que les **nouvelles** mises en service. Le stock déjà bloqué
en 23x se reprend via le script séparé
``migrations/reprise_stock_historique.py``, **hors flux courant** :

- **dry-run par défaut** (rapport CSV seul, aucune écriture) ;
- mode ``commit=True`` : crée les OD **en brouillon** (jamais postées), pour
  validation par le Cabinet Trouillot avant comptabilisation.

Voir l'en-tête du script pour l'usage en ``odoo shell``.

À FAIRE à l'installation : désactiver les 3 server actions existantes
=====================================================================

Ce module **remplace** trois ``ir.actions.server`` bricolées en base, toutes
cassées ou fragiles. Elles doivent être **désactivées** (Paramètres →
Technique → Actions → Actions serveur) pour éviter tout double traitement :

1. *« vide ``prorata_date`` si compte 23x »* — écrit ``False`` sur un champ NOT
   NULL → violation non déterministe. Remplacée par le garde-fou de date.
2. *« garde-fou confirmation »* — teste ``state == 'open'`` pour bloquer le
   passage *vers* ``open`` (logique inversée). Remplacée par le garde-fou intégré.
3. *« bascule 23x → 21x »* — teste ``original_account.code`` (champ inexistant en
   v19) et ne tourne jamais. Remplacée par le virement automatique de ce module.

Tests
=====

Suite ``tests/`` (``TransactionCase`` sur ``TestAccountAssetCommon``) couvrant :
accès code par société, détection, garde-fou date + dérogation, génération et
équilibre de l'OD, idempotence, mapping manquant, mode posté/brouillon,
distribution analytique, contrainte compte 23x.

Licence : LGPL-3 · Auteur : Nuprod
