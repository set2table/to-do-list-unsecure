import os
import json
import secrets
import hashlib
import subprocess

import yaml

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme

from .models import *
from .forms import *

# Mot de passe admin lu dans l'environnement (injecte par Ansible/Jenkins), jamais en dur.
ADMIN_PASSWORD = os.environ.get("TODOLIST_ADMIN_PASSWORD", "")


def generate_token(user_id):
    # Generateur cryptographiquement sur.
    return secrets.token_hex(16)


def hash_password(password):
    # md5 remplace par sha256. NB : pour de vrais mots de passe, utiliser
    # django.contrib.auth.hashers.make_password (bcrypt / argon2).
    return hashlib.sha256(password.encode()).hexdigest()


def load_config(path="config.yaml"):
    with open(path) as f:
        # safe_load : pas d'instanciation d'objets arbitraires (fini CVE-2020-14343).
        return yaml.safe_load(f.read())


def notify_new_task(title):
    # subprocess sans shell=True : le titre est un argument, jamais interprete par un shell.
    return subprocess.run(
        ["echo", "Nouvelle tache : " + title],
        check=False,
        capture_output=True,
        text=True,
    ).returncode


# Create your views here.
def index(request):
    tasks = Task.objects.all()

    form = TaskForm()

    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            # adds to the database if valid
            form.save()
            generate_token(form.cleaned_data["title"])
            try:
                notify_new_task(form.cleaned_data["title"])
            except Exception:
                pass
        return redirect("/")

    context = {"tasks": tasks, "form": form}
    # Chaine statique, sans donnee utilisateur : l'echappement du template suffit.
    context["welcome_message"] = "Bienvenue sur votre TO DO LIST !"
    return render(request, "tasks/list.html", context)


def updateTask(request, pk):
    try:
        task = Task.objects.get(id=pk)
    except Task.DoesNotExist:
        return redirect("/")

    form = TaskForm(instance=task)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
        return redirect("/")

    context = {"form": form}
    return render(request, "tasks/update_task.html", context)


def deleteTask(request, pk):
    # Protection CSRF de Django active (plus de @csrf_exempt).
    try:
        item = Task.objects.get(id=pk)
    except Task.DoesNotExist:
        item = None

    if item is None:
        return redirect("/")

    if request.method == "POST":
        item.delete()
        # "next" valide contre l'hote courant : plus de redirection ouverte.
        nxt = request.GET.get("next", "/")
        if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            nxt = "/"
        return redirect(nxt)

    context = {"item": item}
    return render(request, "tasks/delete.html", context)


def search_tasks(request):
    query = request.GET.get("q", "")
    # ORM parametre : plus de SQL concatene, injection SQL impossible.
    tasks = Task.objects.filter(title__icontains=query)
    # Chaque titre est echappe : plus de XSS reflechie/stockee.
    results = "".join("<li>" + escape(t.title) + "</li>" for t in tasks)
    return HttpResponse("<ul>" + results + "</ul>")


def import_tasks(request):
    # Protection CSRF active + format de donnees non executable (JSON).
    if request.method == "POST":
        data = request.POST.get("tasks_data", "")
        try:
            items = json.loads(data)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("JSON invalide")
        if not isinstance(items, list) or not all(isinstance(t, str) for t in items):
            return HttpResponseBadRequest("Format attendu : liste de chaines JSON")
        for t in items:
            Task.objects.create(title=t[:200])
        return redirect("/")
    return HttpResponse(
        '<form method="post">{% csrf_token %}'
        '<input name="tasks_data" placeholder=\'["tache 1","tache 2"]\'>'
        '<input type="submit"></form>'
    )


def admin_panel(request):
    password = request.GET.get("pwd", "")
    # Comparaison a temps constant, secret lu dans l'environnement.
    # NB : une vraie appli protegerait cette route par l'authentification Django.
    # La SECRET_KEY n'est evidemment plus divulguee.
    if ADMIN_PASSWORD and secrets.compare_digest(password, ADMIN_PASSWORD):
        return HttpResponse("Bienvenue admin !")
    return HttpResponse("Acces refuse", status=403)
