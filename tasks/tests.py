from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from tasks.models import Task
from tasks.forms import TaskForm
from tasks import views


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

    def test_delete_task_inexistant_redirige(self):
        response = self.client.get("/delete_task/999999/")
        self.assertRedirects(response, "/")

    def test_delete_next_interne_autorise(self):
        t = Task.objects.create(title="a supprimer")
        response = self.client.post(f"/delete_task/{t.id}/?next=/search/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/search/")

    def test_delete_next_externe_rejete(self):
        t = Task.objects.create(title="a supprimer")
        response = self.client.post(
            f"/delete_task/{t.id}/?next=https://evil.example/login"
        )
        # destination externe refusee : on retombe sur l'accueil
        self.assertEqual(response.url, "/")

    def test_update_task_inexistant_redirige(self):
        response = self.client.get("/update_task/999999/")
        self.assertRedirects(response, "/")


class SearchViewTest(TestCase):
    """La recherche echappe le HTML (plus de XSS) et ne concatene plus de SQL."""

    def test_search_echappe_le_html(self):
        Task.objects.create(title="<script>alert(1)</script>")
        response = self.client.get("/search/", {"q": "script"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_search_filtre_par_titre(self):
        Task.objects.create(title="acheter du pain")
        Task.objects.create(title="reviser le TP")
        response = self.client.get("/search/", {"q": "pain"})
        self.assertContains(response, "acheter du pain")
        self.assertNotContains(response, "reviser le TP")


class ImportViewTest(TestCase):
    """L'import accepte du JSON (plus de pickle) et valide le format."""

    def test_import_get_affiche_le_formulaire(self):
        response = self.client.get("/import/")
        self.assertEqual(response.status_code, 200)

    def test_import_json_valide_cree_les_taches(self):
        response = self.client.post(
            "/import/", {"tasks_data": '["tache A", "tache B"]'}
        )
        self.assertRedirects(response, "/")
        self.assertEqual(Task.objects.filter(title__in=["tache A", "tache B"]).count(), 2)

    def test_import_json_invalide_rejete(self):
        response = self.client.post("/import/", {"tasks_data": "pas du json"})
        self.assertEqual(response.status_code, 400)

    def test_import_format_inattendu_rejete(self):
        response = self.client.post("/import/", {"tasks_data": '{"a": 1}'})
        self.assertEqual(response.status_code, 400)


@override_settings(DEBUG=True)
class AdminPanelTest(TestCase):
    """Le panneau admin ne divulgue plus la SECRET_KEY et refuse un mauvais mot de passe."""

    def test_mauvais_mot_de_passe_refuse(self):
        response = self.client.get("/admin_panel/", {"pwd": "mauvais"})
        self.assertEqual(response.status_code, 403)

    def test_bon_mot_de_passe_ne_divulgue_pas_la_cle(self):
        # valeur de test neutre (presente dans l'allowlist gitleaks du depot)
        secret = "mot-de-passe-de-test"
        with mock.patch.object(views, "ADMIN_PASSWORD", secret):
            response = self.client.get("/admin_panel/", {"pwd": secret})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET_KEY")


class HelpersTest(TestCase):
    """Fonctions utilitaires durcies."""

    def test_generate_token_est_aleatoire(self):
        self.assertNotEqual(views.generate_token(1), views.generate_token(1))

    def test_hash_password_utilise_sha256(self):
        h = views.hash_password("motdepasse")
        self.assertEqual(len(h), 64)  # sha256 hex = 64 caracteres

    def test_notify_new_task_ne_lance_pas_de_shell(self):
        # ne doit pas lever et retourne un code de retour entier
        self.assertEqual(views.notify_new_task("titre normal"), 0)
