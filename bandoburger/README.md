# BandoBurger (cog Red)

Cogs [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) (3.5+).

## BandoBurger

Tableau « qui prend quoi » pour le BandoBurger. Tout le monde clique sur un ingrédient pour le prendre, et l'image du burger se monte couche par couche.

- ⬜ bouton gris = libre · 🟦 bleu = pris
- Cliquer sur un ingrédient → tu te mets dessus, même si quelqu'un l'a déjà (on peut partager le steak à plusieurs, chacun avec sa quantité)
- Recliquer sur le tien → menu privé : **Quantité**, **Je lâche**
- Le bouton affiche ×2, ×3… quand plusieurs personnes sont dessus

### Installation

```
[p]load downloader
[p]repo add red-bot https://github.com/mr-biggles/Red-bot
[p]cog install red-bot bandoburger
[p]load bandoburger
```

Puis dans le salon voulu :

```
[p]burger start
```

Le bot a besoin de : Envoyer des messages, Intégrer des liens, Joindre des fichiers.

Slash commands (optionnel) :

```
[p]slash enable burger
[p]slash sync
```

### Commandes

| Commande | Qui | Effet |
|---|---|---|
| `burger` / `/burger tableau` | tous | Affiche le tableau (sans boutons) |
| `burger prend <ingrédient> [quantité]` | tous | Se met sur un ingrédient (ou change sa quantité) |
| `burger lache <ingrédient> [membre]` | tous (modo : peut retirer quelqu'un) | Se retire d'un ingrédient |
| `burger quantite <ingrédient> <quantité>` | tous | Change la quantité |
| `burger start [vider]` | modo | Poste le tableau interactif dans ce salon |
| `burger assigne <ingrédient> <membre> [quantité]` | modo | Ajoute quelqu'un sur un ingrédient |
| `burger reset` | modo | Vide la répartition |

Le nom d'ingrédient peut être partiel et sans accents : `oign`, `ched`, `pain`…
Ingrédients : pain brioché, steak, cheddar, oignon frit, bacon, salade, cornichons, sauce.
Un seul tableau actif par serveur. Il garde ses boutons après un redémarrage du bot.
