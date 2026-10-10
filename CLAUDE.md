# Working rules for this repo

- Don't write or edit code unless I explicitly ask for it.
- Ask before adding a dependency or changing project structure.
- Keep code simple and readable over clever.
- Don't add features or handle cases beyond what was asked.
- Python 3.12, type hints, pytest.

## Menu CSV (data/menu.csv)

144 items, 1728 rows (one row per item × option_group × option, flattened), 12 categories, 4 branches.

- Item-level columns repeat on every row of that item: `item_id`, names (ar/en), category, `base_price_sar`, 4 `available_<branch>` flags.
- Option-row columns: `option_group_id` (required, min/max select), `option_id`, `option_price_delta_sar`, `item_price_with_option_sar` (= base + *this one* delta only — never a multi-option total; sum deltas yourself).
- Availability is per-dish, not per-option. Branches don't vary price, only availability.
- 17 option groups, scoped per category (e.g. pizza has size/crust/toppings/spice_level; sandwiches have bread/meal/extras/spice_level — `meal` is the "make it a meal" upsell, +12 SAR).
- Arabic labels aren't unique keys: `portion`/`size` both show as "الحجم"; `extras`/`toppings` both show as "إضافات". Don't match on the Arabic label text.
- Item Arabic names include transliterated English loanwords (`برجر` = burger, `بيتزا` = pizza), not translations.

