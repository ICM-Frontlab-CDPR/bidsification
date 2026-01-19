Petite pipeline de bidsfication semie-automatique basée sur une interaction cadrée user-LLM agent.

Attention a checker que le LLM n'a pas le droit de lire les donnees pour ne pas les diffuser aux serveurx tiers

SOTA a checker ! + retour de tous ceux qui acauiert de la donnees ICM + NS + autres ?

1. Analyse des donnees RAW
2. Definition des outils et de l'environnement **-- validation utilisateur**
3. Construction de la pipeline en s'appuyant sur une strcture deja existante :
   1. Reformation du tree-BIDS (correct path and name)
   2. check de l'utilisation de tous les files (ajout des fichiers) + le nombre de sujets/sessions etc **--validation utilisateur**
   3. bids-validation et recueil des erreurs au sein des fichiers  ( pypi.org/project/bids-validator/ ...setup docker pour validation et log correct des erreurs ... ou passer par du online ?)
   4. retravaille sur des scripts de modifications internes au fichier avec l'utilisateur
