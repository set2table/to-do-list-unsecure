import os
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from tasks.models import Task
from tasks.forms import TaskForm


class TaskModelTest(TestCase):
    """Tests liés au modèle Task"""

    def test_task_creation_defaults(self):
        task = Task.objects.create(title="Test task")

        self.assertEqual(task.title, "Test task")
        self.assertFalse(task.complete)
        self.assertIsNotNone(task.created)

    def test_task_str_representation(self):
        task = Task.objects.create(title="Ma tâche")
        self.assertEqual(str(task), "Ma tâche")


class TaskFormTest(TestCase):
    """Tests du formulaire TaskForm"""

    def test_task_form_valid(self):
        form = TaskForm(data={
            "title": "Nouvelle tâche",
            "complete": False
        })
        self.assertTrue(form.is_valid())

    def test_task_form_invalid_without_title(self):
        form = TaskForm(data={
            "complete": False
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)


class TaskUrlsTest(TestCase):
    """Tests de résolution des URLs"""

    def test_index_url_accessible(self):
        response = self.client.get(reverse("list"))
        self.assertEqual(response.status_code, 200)


class TaskViewsTest(TestCase):
    """Tests des vues"""

    def setUp(self):
        self.task = Task.objects.create(title="Task initiale")

    def test_index_view_lists_tasks(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_create_task_via_post(self):
        response = self.client.post("/", {
            "title": "Task POST",
            "complete": False
        })

        self.assertEqual(Task.objects.count(), 2)
        self.assertRedirects(response, "/")

    def test_update_task_get(self):
        response = self.client.get(f"/update_task/{self.task.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_update_task_post(self):
        response = self.client.post(
            f"/update_task/{self.task.id}/",
            {
                "title": "Task modifiée",
                "complete": True
            }
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Task modifiée")
        self.assertTrue(self.task.complete)
        self.assertRedirects(response, "/")

    def test_delete_task_get(self):
        response = self.client.get(f"/delete_task/{self.task.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task initiale")

    def test_delete_task_post(self):
        response = self.client.post(f"/delete_task/{self.task.id}/")

        self.assertEqual(Task.objects.count(), 0)
        self.assertRedirects(response, "/")


class TaskSecurityTest(TestCase):
    """Tests des corrections de securite"""

    def setUp(self):
        self.task = Task.objects.create(title="<script>alert(1)</script>")

    def test_title_is_escaped_in_list(self):
        response = self.client.get("/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_search_uses_orm_and_escapes(self):
        response = self.client.get("/search/", {"q": "script"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")

    def test_search_sql_injection_returns_nothing(self):
        response = self.client.get("/search/", {"q": "' OR '1'='1"})
        self.assertEqual(response.content, b"<ul></ul>")

    def test_unknown_task_returns_404(self):
        self.assertEqual(self.client.get("/update_task/9999/").status_code, 404)
        self.assertEqual(self.client.post("/delete_task/9999/").status_code, 404)

    def test_delete_rejects_open_redirect(self):
        response = self.client.post(
            f"/delete_task/{self.task.id}/?next=https://evil.example.com/"
        )
        self.assertRedirects(response, "/")

    def test_delete_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(f"/delete_task/{self.task.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Task.objects.count(), 1)

    def test_invalid_update_does_not_save(self):
        response = self.client.post(f"/update_task/{self.task.id}/", {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "<script>alert(1)</script>")

    def test_invalid_create_shows_form_again(self):
        response = self.client.post("/", {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 1)


class AdminPanelTest(TestCase):
    """Le mot de passe admin vient de l'environnement, plus du code"""

    @patch.dict(os.environ, {"TODOLIST_ADMIN_PASSWORD": "mot-de-passe-de-test"})
    def test_admin_panel_ok_with_env_password(self):
        response = self.client.post("/admin_panel/", {"pwd": "mot-de-passe-de-test"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET_KEY")

    @patch.dict(os.environ, {"TODOLIST_ADMIN_PASSWORD": "mot-de-passe-de-test"})
    def test_admin_panel_refused_with_wrong_password(self):
        response = self.client.post("/admin_panel/", {"pwd": "mauvais-mot-de-passe"})
        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"TODOLIST_ADMIN_PASSWORD": ""})
    def test_admin_panel_refused_when_not_configured(self):
        response = self.client.post("/admin_panel/", {"pwd": ""})
        self.assertEqual(response.status_code, 403)

    def test_admin_panel_get_not_allowed(self):
        self.assertEqual(self.client.get("/admin_panel/").status_code, 405)
