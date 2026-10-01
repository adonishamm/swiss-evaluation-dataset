# testset/ : ce qu'il y a dedans

Trois choses, rien d'autre.

## 1. `cases_100.jsonl` : les 100 arrêts

Une ligne par arrêt du Tribunal fédéral. C'est la matière première. Chaque ligne contient :

- l'identité du cas (numéro, date, langue, domaine : AI, AA, LAMal, LPP, AVS/PC ou LCA),
- les **faits** tels que le tribunal les raconte,
- les **considérants** (le raisonnement du tribunal),
- le **dispositif** (le verdict) et l'étiquette `approval` / `partial_approval` / `dismissal`,
- les articles de loi et les arrêts de principe que le tribunal cite.

Ce fichier ne se donne jamais tel quel à un modèle : il contient la réponse.

## 2. `dossiers/<cas>.json` : le dossier fabriqué d'un cas

Le tribunal ne publie pas les pièces du dossier, seulement son arrêt. Donc on **fabrique** les pièces à partir des faits : la demande, le rapport d'enquête, la décision de l'assureur, le recours, l'arrêt cantonal. Ce sont des textes générés par Claude, qui ne disent rien de plus que les faits.

On y ajoute **5 pièges** générés exprès, étiquetés dans `ground_truth` :

| Piège | Exemple |
|---|---|
| T1 futur | un document daté après le moment où on se trouve |
| T2 périmé | une ancienne version d'un rapport, remplacée depuis |
| T3 non envoyé | un recours rédigé mais jamais déposé |
| T4 mauvaise personne | un certificat médical pour le frère de l'assuré |
| T5 mauvaise version de loi | l'article dans sa version actuelle, pas celle en vigueur à l'époque |
| T6 hors sujet | une lettre du médecin sur une allergie |

Plus un **document manquant** (`absent_document`) : la pièce décisive que personne n'a produite.

Pour l'instant : 5 cas pilotes. Les 95 autres se génèrent avec `scripts/07_generate_dossier.py --all`.

## 3. `questions/<cas>.jsonl` : ce qu'on demande à l'agent

Une ligne par étape de la procédure. À chaque étape, l'agent reçoit le dossier tel qu'il existe à ce moment-là (documents réels + pièges, en ordre aléatoire) et doit répondre :

1. quelle est la prochaine action et dans quel délai,
2. quels documents utiliser, lesquels écarter, lequel manque,
3. sur quels articles de loi, dans quelle version.

Le champ `prompt` est ce que l'agent voit. Le champ `gold` est la réponse attendue, dérivée du dossier et de ce qui s'est vraiment passé.

---

Tout le reste (listes de candidats, tableaux intermédiaires, fichiers pour la tâche simple "admis ou rejeté") est dans `data/work/`, régénérable par les scripts, et hors git.
