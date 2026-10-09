from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, force_authenticate

from ..models import CrossForm


class CrossFormTests(TestCase):
    """This class defines the test suite for CrossForm model."""

    databases = {"default", "runes_db"}

    def setUp(self):
        self.crossForm_name = "A1"
        self.crossForm_group = 1
        self.crossForm = CrossForm(name=self.crossForm_name, group_id=self.crossForm_group)

    def test_can_create_instance(self):
        old_count = CrossForm.objects.count()
        self.crossForm.save()
        new_count = CrossForm.objects.count()
        self.assertNotEqual(old_count, new_count)


class ViewTestCase(TestCase):
    """Test suite for the api views."""

    def setUp(self):
        """Define the test client and other test variables."""
        self.user = User.objects.create_user("test_user", "test@user.com", password="12345", is_superuser=True)
        self.user.save()
        # self.user = User.objects.get(username='test_user')

        self.client = APIClient(enforce_csrf_checks=False)
        self.client.login(username="test_user", password="12345")
        self.client.force_authenticate(user=self.user)
        self.data = {"name": "A1", "group_id": 1}
        self.url = reverse("crossform-list")
        self.response = self.client.post(self.url, self.data, format="json")

        # def test_api_can_create_a_crossform(self):
        """Test the api has bucket creation capability."""
        # self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        # self.client.logout()
        # self.assertEqual(len(Group.objects.all()), 1)
