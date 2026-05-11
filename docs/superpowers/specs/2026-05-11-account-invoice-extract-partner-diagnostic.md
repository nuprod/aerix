# Diagnostic — pourquoi le `partner_id` du transféreur n'est-il pas filtré ?

**Contexte** : Le code natif `account.move.message_new` ([community/addons/account/models/account_move.py:6948-7001](file:///Volumes/T7/Odoo/nupo/19.0/community/addons/account/models/account_move.py#L6948)) filtre déjà les partenaires internes (ligne 6980 `partners.filtered(lambda p: not is_internal_partner(p))`). Mais en prod chez Aerix, on observe que `partner_id` reste celui du transféreur. Avant de coder le fix, il faut comprendre pourquoi.

## Hypothèses à tester

1. **H1 — Partner sans `user_ids`** : Le partenaire matché par email n'est pas linké à un `res.users`. `is_internal_partner` retourne False, le filtre natif n'agit pas. Cas courant si le contact employé a un email différent de celui du user (`jean.dupont@aerix.fr` côté contact vs `jdupont@aerix.fr` côté user).

2. **H2 — Body search retombe sur un autre partner non-interne** : Le body du mail forwardé contient l'email du vrai fournisseur, mais ce fournisseur n'est pas en base. La recherche par body retourne autre chose qu'un interne — pas filtré.

3. **H3 — Mail.alias avec alias_defaults** : L'alias est configuré avec un `partner_id` forcé. Mais le natif rebuild `values` ignorant `custom_values['partner_id']`, donc ça ne devrait pas marcher comme ça… à vérifier.

4. **H4 — Override custom externe** : Un autre module override `message_new` avant le natif et set le partner.

## Script de diagnostic

À exécuter dans **`odoo-bin shell -d <DB_NAME> --addons-path=...`**, ou comme server action one-shot. Choisis une facture problématique en base et adapte l'ID dans `target_move`.

```python
# ---- À adapter : ID d'une facture où tu observes le bug ----
TARGET_MOVE_ID = 0  # remplace par un ID réel

# Si TARGET_MOVE_ID = 0, on prend la plus récente facture draft en mail alias
if not TARGET_MOVE_ID:
    move = env['account.move'].search(
        [('move_type', '=', 'in_invoice'),
         ('state', '=', 'draft'),
         ('invoice_source_email', '!=', False)],
        order='id desc', limit=1,
    )
else:
    move = env['account.move'].browse(TARGET_MOVE_ID)

if not move:
    print("Aucune facture trouvée avec les critères.")
else:
    partner = move.partner_id
    company = move.company_id

    print(f"=== Facture {move.id} ({move.name or 'draft'}) ===")
    print(f"  move_type        : {move.move_type}")
    print(f"  journal          : {move.journal_id.name} (type={move.journal_id.type})")
    print(f"  invoice_source_email: {move.invoice_source_email!r}")
    print(f"  extract_state    : {move.extract_state}")
    print(f"  extract_partner_name: {move.extract_partner_name!r}")
    print()
    print(f"  partner_id       : {partner.id} '{partner.name}'")
    print(f"    .email         : {partner.email!r}")
    print(f"    .email_normalized: {partner.email_normalized!r}")
    print(f"    .company_id    : {partner.company_id.id if partner.company_id else None}")
    print(f"    .partner_share : {partner.partner_share}")
    print(f"    .parent_id     : {partner.parent_id.id if partner.parent_id else None}")

    users = partner.user_ids
    print(f"    .user_ids      : {len(users)} user(s)")
    for u in users:
        print(f"      - user #{u.id} login={u.login!r} active={u.active} "
              f"share={u.share} _is_internal={u._is_internal()}")
    print()

    # Reproduire le calcul natif `is_internal_partner`
    cond1 = company.partner_id in (partner | partner.parent_id)
    cond2 = bool(partner.user_ids) and all(
        u._is_internal() for u in partner.user_ids
    )
    is_internal = cond1 or cond2
    print(f"  >> Native is_internal_partner({partner.name}):")
    print(f"       cond1 (company.partner_id in partner|parent_id) = {cond1}")
    print(f"       cond2 (user_ids non-vide ET tous internes)      = {cond2}")
    print(f"       => is_internal = {is_internal}")
    print(f"     Si False, le natif NE strip PAS ce partner_id.")
    print()

    # Premier message (le forward)
    first_msg = move.message_ids.sorted('id')[:1]
    if first_msg:
        msg = first_msg[0]
        print(f"  First message #{msg.id}:")
        print(f"    email_from   : {msg.email_from!r}")
        print(f"    author_id    : "
              f"{msg.author_id.id if msg.author_id else None} "
              f"'{msg.author_id.name if msg.author_id else ''}'")
        body = msg.body or ''
        # Extraire les emails du body pour voir ce que email_re.findall ferait
        import re
        body_emails = sorted(set(re.findall(
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            body,
        )))
        print(f"    body emails  : {body_emails}")
    print()

    # Vérifier le partner trouvé par email (sans filtre)
    candidates_by_email = env['res.partner'].search([
        ('email_normalized', '=', partner.email_normalized),
    ]) if partner.email_normalized else env['res.partner']
    print(f"  Partners avec email={partner.email_normalized!r} : "
          f"{len(candidates_by_email)}")
    for p in candidates_by_email:
        print(f"    - #{p.id} '{p.name}' user_ids={len(p.user_ids)}")
    print()

    # Cherche res.users actifs non-portail avec cet email (notre check)
    if partner.email_normalized:
        nu_users = env['res.users'].sudo().search([
            ('active', '=', True),
            ('share', '=', False),
            ('partner_id.email_normalized', '=', partner.email_normalized),
        ])
        print(f"  Users actifs non-portail avec email_normalized="
              f"{partner.email_normalized!r}: {len(nu_users)}")
        for u in nu_users:
            print(f"    - user #{u.id} login={u.login!r} "
                  f"partner_id=#{u.partner_id.id} '{u.partner_id.name}'")
```

## Comment l'utiliser

1. Ouvre `odoo-bin shell` sur la base de pré-prod.
2. Trouve l'ID d'une facture où le bug se manifeste (ex. `SELECT id FROM account_move WHERE state='draft' AND move_type='in_invoice' AND invoice_source_email IS NOT NULL ORDER BY id DESC LIMIT 5;`).
3. Colle le script en remplaçant `TARGET_MOVE_ID` par l'ID. Ou laisse à 0 pour qu'il prenne la plus récente.
4. Reporte la sortie.

## Ce que la sortie nous dira

- **Si `is_internal = False` ET `user_ids = 0`** → H1 confirmée. Fix = post-process sur `partner.user_ids` (avec recherche élargie : email → user).
- **Si `is_internal = False` mais `user_ids ≥ 1`** → un user existe mais le `all(_is_internal())` retourne False (user portail mélangé, ou condition inattendue). Inspecter.
- **Si `is_internal = True`** → le natif aurait dû strip. Quelque chose d'autre intervient après `message_new` pour re-set partner_id. Inspecter la chaîne `message_ids` / `tracking_value_ids`.
- **Si la valeur de `invoice_source_email` diffère de `partner.email`** → le partner a été matché autrement.
