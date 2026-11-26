# BandoBurger (cog Red)

Cogs [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) (3.5+).

## BandoBurger

Tableau « qui prend quoi » pour le BandoBurger. Tout le monde clique sur un ingrédient pour le prendre, et l'image du burger se monte couche par couche.

- ⬜ bouton gris = libre · 🟦 bleu = pris
- Cliquer sur un ingrédient libre → tu le prends
- Recliquer sur le tien → menu privé : **Quantité**, **Je lâche**
- Cliquer sur celui d'un autre → on te dit qui l'a pris

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
| `burger prend <ingrédient> [quantité]` | tous | Prend un ingrédient |
| `burger lache <ingrédient>` | tous (modo : n'importe lequel) | Libère un ingrédient |
| `burger quantite <ingrédient> <quantité>` | tous | Change la quantité |
| `burger start [vider]` | modo | Poste le tableau interactif dans ce salon |
| `burger assigne <ingrédient> <membre> [quantité]` | modo | Donne un ingrédient à quelqu'un |
| `burger reset` | modo | Vide la répartition |

Le nom d'ingrédient peut être partiel et sans accents : `oign`, `ched`, `pain`…
Ingrédients : pain brioché, steak, cheddar, oignon frit, bacon, salade, cornichons, sauce.
Un seul tableau actif par serveur. Il garde ses boutons après un redémarrage du bot.
