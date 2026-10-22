# Format principal des logs

Le MVP commence avec un format texte simple :

```text
TIMESTAMP LEVEL SERVICE [COMPONENT] MESSAGE
```

Exemple :

```text
2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused
```

Le parser devra conserver :

- le numéro de ligne original ;
- la ligne brute complète ;
- le timestamp lorsqu'il est valide ;
- le niveau (`INFO`, `WARNING`, `ERROR` ou valeur inconnue) ;
- le service ;
- le message ;
- les métadonnées disponibles ;
- le statut du parsing (`valid`, `partial` ou `invalid`).

Les informations absentes ne doivent pas être inventées.

