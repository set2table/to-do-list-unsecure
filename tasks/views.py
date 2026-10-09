import hmac
import logging
import os

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html_join
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from .forms import TaskForm
from .models import Task

logger = logging.getLogger(__name__)

LIST_URL = "/"


@require_http_methods(["GET", "POST"])
def index(request):
    form = TaskForm()

    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            logger.info("Tache ajoutee : id=%s", task.id)
            return redirect(LIST_URL)

    context = {"tasks": Task.objects.all(), "form": form}
    return render(request, "tasks/list.html", context)


@require_http_methods(["GET", "POST"])
def update_task(request, pk):
    task = get_object_or_404(Task, id=pk)
    form = TaskForm(instance=task)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            logger.info("Tache modifiee : id=%s", task.id)
            return redirect(LIST_URL)

    return render(request, "tasks/update_task.html", {"form": form})


@require_http_methods(["GET", "POST"])
def delete_task(request, pk):
    item = get_object_or_404(Task, id=pk)

    if request.method == "POST":
        item.delete()
        logger.info("Tache supprimee : id=%s", pk)
        next_url = request.GET.get("next", LIST_URL)
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            next_url = LIST_URL
        return redirect(next_url)

    return render(request, "tasks/delete.html", {"item": item})


@require_GET
def search_tasks(request):
    query = request.GET.get("q", "")
    tasks = Task.objects.filter(title__icontains=query)
    items = format_html_join("", "<li>{}</li>", ((t.title,) for t in tasks))
    return HttpResponse(format_html_join("", "<ul>{}</ul>", [(items,)]))


@require_http_methods(["POST"])
def admin_panel(request):
    expected = os.environ.get("TODOLIST_ADMIN_PASSWORD", "")
    provided = request.POST.get("pwd", "")
    if expected and hmac.compare_digest(provided.encode(), expected.encode()):
        return HttpResponse("Bienvenue admin !")
    return HttpResponseForbidden("Acces refuse")
