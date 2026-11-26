# BandoBurger (cog Red)

Cogs [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) (3.5+).

## BandoBurger

Tableau « qui achète quoi » pour le BandoBurger. Tout le monde clique sur un ingrédient pour le prendre, et l'image du burger se monte couche par couche.

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

**Un tableau par salon** : `burger start` dans un autre salon crée un nouveau tableau, sans toucher aux autres.
Celui qui lance le tableau en est l'**organisateur**.
Tant qu'il manque des ingrédients, le tableau redescend tout seul en bas du salon tous les 6 messages environ. Une fois complet, il ne bouge plus.

| Commande | Qui | Effet |
|---|---|---|
| `burger start` | tous | Lance un tableau dans ce salon (ou le reposte en bas s'il existe déjà) |
| `burger start True` | organisateur / modo | Relance le tableau de ce salon à zéro |
| `burger` / `/burger tableau` | tous | Affiche le tableau de ce salon (sans boutons) |
| `burger prend <ingrédient> [quantité]` | tous | Se met sur un ingrédient (ou change sa quantité) |
| `burger lache <ingrédient> [membre]` | tous (organisateur / modo : peut retirer quelqu'un) | Se retire d'un ingrédient |
| `burger quantite <ingrédient> <quantité>` | tous | Change sa quantité |
| `burger assigne <ingrédient> <membre> [quantité]` | organisateur / modo | Ajoute quelqu'un sur un ingrédient |
| `burger reset` | organisateur / modo | Vide la répartition de ce salon |
| `burger collant` | organisateur / modo | Active / désactive la redescente automatique du tableau |
| `burger stop` | organisateur / modo | Clôture le tableau de ce salon (le message reste) |
| `burger actifs` | tous | Liste les tableaux en cours sur le serveur |

Le nom d'ingrédient peut être partiel et sans accents : `oign`, `ched`, `pain`…
Ingrédients : pain brioché, steak haché à l'oignon, cheddar, oignons frits, bacon, salade, cornichons, sauce burger, sauce BBQ.
Les tableaux gardent leurs boutons après un redémarrage du bot.
