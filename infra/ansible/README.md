# Infra todolist (Ansible)

| Playbook | Cible | Role |
|---|---|---|
| `jenkins.yml` | groupe `ci` (VM jenkins) | Jenkins, plugins, jobs (`jobs/*.xml.j2`), gitleaks, SonarQube (docker), durcissement |
| `deploy_app.yml` | groupe `apps` (app-dev, app-prod1) | Durcissement + deploiement de la todolist |

## Deployer

Le deploiement normal passe par Jenkins (`todolist-ci`). A la main, depuis WSL :

```bash
export TODOLIST_SECRET_KEY='...'      # >= 32 caracteres
export TODOLIST_ADMIN_PASSWORD='...'  # >= 12 caracteres
ansible-playbook deploy_app.yml --limit app-dev -e app_version=ma-branche
```

## Regle : la prod ne recoit que `main`

* `app-prod1` (`app_env: prod`) n'accepte que `app_version=main` ou le commit
  **actuel** de `main` (verifie par `git ls-remote` avant toute modification).
* La meme regle est appliquee dans les jobs `todolist-deploy` et `todolist-ci`
  (CIBLE=prod refuse toute autre branche). Deux verrous independants.
* Pour tester une branche : la deployer sur `app-dev`, puis la merger dans `main`.

## Secrets

Aucun secret dans ce depot. Les valeurs viennent de variables d'environnement
(injectees par le Credentials Store Jenkins), sont ecrites dans
`/etc/todolist/todolist.env` (root:todolist, 0640) et lues par systemd.

## Tracabilite

Chaque deploiement ecrit `/opt/todolist/DEPLOIEMENT` (commit, auteur, build Jenkins)
et une ligne `todolist-deploy` dans le journal : `journalctl -t todolist-deploy`.
