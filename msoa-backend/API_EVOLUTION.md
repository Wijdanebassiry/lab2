# Stratégie d'évolution des API

Un contrat d'API est un accord entre un service et ses consommateurs. Les services étant déployés
séparément, un changement de contrat ne doit jamais casser un consommateur qui n'a pas été mis à jour.

## 1. Changement compatible ou breaking ?

| Compatible (autorisé dans la même version) | Breaking (nouvelle version obligatoire) |
|---|---|
| Ajouter un champ optionnel dans une réponse | Supprimer ou renommer un champ |
| Ajouter un endpoint | Changer le **type** ou la **structure** d'un champ (ex. `price` : nombre -> objet) |
| Ajouter un paramètre de requête optionnel | Rendre obligatoire un champ ou un paramètre qui ne l'était pas |
| Ajouter un en-tête de réponse | Changer un code HTTP ou le sens d'un endpoint |

## 2. Règles de la plateforme

1. **Additif d'abord.** Les consommateurs sont *tolérants* : ils lisent les champs dont ils ont besoin et **ignorent les champs inconnus**.
2. **Un changement breaking passe par une nouvelle version** dans l'URL (`/v2/...`). L'ancienne version reste **inchangée** (« figée ») et continue d'être servie.
3. **Cycle de vie d'une version :** annonce (`CONTRACTS.md` + en-tête `Link: rel="successor-version"`), migration de chaque consommateur à son rythme, dépréciation (en-tête `Deprecation`/`Sunset`) une fois les consommateurs migrés, puis retrait quand plus aucun appel n'arrive sur l'ancienne version.
4. **Tests de contrat par version.** Chaque version a ses tests ; ceux de la version figée ne sont jamais modifiés (ex. « v1 : `price` est un nombre »). Une PR qui les fait échouer est refusée.
5. **Consommateurs déclarés.** Chaque section de `CONTRACTS.md` liste, dans « Appelants et dépendances », qui lit quels champs. Avant de modifier une réponse, on prévient ces consommateurs.
6. **Journal des changements.** Tout changement est noté dans le tableau « Historique des changements » du service, avec la mention « compatible : oui/non ».
7. **Checklist de PR** pour toute modification d'une réponse existante : est-ce additif ? Sinon, nouvelle version + prévenir les appelants.

## 3. Application : prix multi-devises du Catalog

| Version | `price` | Consommateurs |
|---|---|---|
| v1 `/products` | nombre (MAD), **inchangé** | frontend, Orders |
| v2 `/v2/products` | `{ "amount": 8499, "currency": "MAD" }`, option `?currency=EUR\|USD` | nouveaux consommateurs |

Migration prévue des consommateurs :
- **Orders** : lire `price.amount` et mémoriser `price.currency` avec la commande, puis passer à `/v2/products/:id`.
- **Frontend** : afficher `product.price.amount` avec `product.price.currency` (au lieu de « MAD » en dur), puis passer à `/v2/products`.
- Quand les deux ont migré et que les journaux ne montrent plus d'appels v1, annoncer le retrait de v1.