from django.test import TestCase
from rest_framework.test import APIClient

from .models import User

LOGIN_URL = "/api/auth/login"
REGISTER_URL = "/api/auth/register"
LOGOUT_URL = "/api/auth/logout"
ME_URL = "/api/auth/me"


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="demo@msoa.shop",
            password="demo123",
            name="Demo Customer",
            id="user-1",
        )

    def login(self, email="demo@msoa.shop", password="demo123"):
        return self.client.post(
            LOGIN_URL, {"email": email, "password": password}, format="json"
        )

    def authenticate(self):
        token = self.login().data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return token

    # ---------- login ----------

    def test_login_success_returns_user_and_token(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertEqual(
            response.data["user"],
            {
                "id": "user-1",
                "name": "Demo Customer",
                "email": "demo@msoa.shop",
                "role": "CUSTOMER",
            },
        )
        self.assertNotIn("password", response.data["user"])

    def test_login_ignores_case_and_spaces_in_email(self):
        response = self.login(email="  DEMO@msoa.shop ")
        self.assertEqual(response.status_code, 200)

    def test_login_wrong_password_returns_401(self):
        response = self.login(password="faux")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["message"], "Invalid email or password.")

    def test_login_unknown_email_returns_401(self):
        response = self.login(email="nobody@msoa.shop")
        self.assertEqual(response.status_code, 401)

    def test_error_contains_message_and_error_keys(self):
        response = self.login(password="faux")
        self.assertIn("message", response.data)
        self.assertIn("error", response.data)

    # ---------- register ----------

    def test_register_success_returns_user_without_token(self):
        response = self.client.post(
            REGISTER_URL,
            {"name": "Test User", "email": "test@msoa.shop", "password": "test123"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("token", response.data)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["email"], "test@msoa.shop")
        self.assertEqual(response.data["role"], "CUSTOMER")
        self.assertIsInstance(response.data["id"], str)

    def test_register_stores_a_hashed_password(self):
        self.client.post(
            REGISTER_URL,
            {"name": "Test User", "email": "test@msoa.shop", "password": "test123"},
            format="json",
        )
        created = User.objects.get(email="test@msoa.shop")
        self.assertNotEqual(created.password, "test123")
        self.assertTrue(created.check_password("test123"))

    def test_register_missing_field_returns_400(self):
        response = self.client.post(
            REGISTER_URL, {"name": "", "email": "x@msoa.shop", "password": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message"], "All fields are required.")

    def test_register_duplicate_email_returns_409(self):
        response = self.client.post(
            REGISTER_URL,
            {"name": "Other", "email": "demo@msoa.shop", "password": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["message"], "Email already registered.")

    def test_new_account_can_log_in(self):
        self.client.post(
            REGISTER_URL,
            {"name": "Test User", "email": "test@msoa.shop", "password": "test123"},
            format="json",
        )
        response = self.login(email="test@msoa.shop", password="test123")
        self.assertEqual(response.status_code, 200)

    # ---------- me ----------

    def test_me_with_token_returns_user(self):
        self.authenticate()
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], "user-1")
        self.assertEqual(response.data["email"], "demo@msoa.shop")
        self.assertNotIn("user", response.data)

    def test_me_without_token_returns_401(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, 401)
        self.assertIn("message", response.data)

    def test_me_with_invalid_token_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, 401)

    # ---------- logout ----------

    def test_logout_with_token_returns_204(self):
        self.authenticate()
        response = self.client.post(LOGOUT_URL)
        self.assertEqual(response.status_code, 204)

    def test_logout_without_token_returns_401(self):
        response = self.client.post(LOGOUT_URL)
        self.assertEqual(response.status_code, 401)