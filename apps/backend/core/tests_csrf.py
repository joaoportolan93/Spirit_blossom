"""
Testes de CSRF com enforce_csrf_checks=True.
Garante que o CookieJWTAuthentication e _enforce_csrf funcionam corretamente.
"""

import pytest
from rest_framework import status

from conftest import get_csrf_token, inject_access, inject_refresh, make_csrf_client
from core.factories import PostFactory, UserFactory


@pytest.mark.django_db
class TestCSRFPosts:
    def test_get_posts_sem_csrf_retorna_200(self):
        """GET é método seguro — não requer CSRF."""
        client = make_csrf_client()
        user = UserFactory()
        inject_access(client, user)
        response = client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK

    def test_post_sem_csrf_retorna_403(self):
        """POST sem X-CSRFToken → 403 Forbidden."""
        client = make_csrf_client()
        user = UserFactory()
        inject_access(client, user)
        response = client.post(
            "/api/posts/",
            {"content_text": "Olá mundo", "visibility": "public"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_post_com_csrf_retorna_201(self):
        """POST com X-CSRFToken válido → 201 Created."""
        client = make_csrf_client()
        user = UserFactory()
        inject_access(client, user)
        csrf = get_csrf_token(client)
        response = client.post(
            "/api/posts/",
            {"content_text": "Olá mundo com CSRF", "visibility": "public"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_delete_sem_csrf_retorna_403(self):
        """DELETE sem X-CSRFToken → 403 Forbidden."""
        client = make_csrf_client()
        user = UserFactory()
        inject_access(client, user)
        post = PostFactory(author=user)
        response = client.delete(f"/api/posts/{post.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCSRFRefresh:
    def test_refresh_sem_csrf_retorna_403(self):
        """POST /refresh/ sem CSRF → 403."""
        client = make_csrf_client()
        user = UserFactory()
        inject_refresh(client, user)
        get_csrf_token(client)
        response = client.post("/api/auth/refresh/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_refresh_com_csrf_retorna_200_e_rotaciona_cookies(self):
        """POST /refresh/ com CSRF e cookie de refresh válido → 200 + cookies rotacionados."""
        client = make_csrf_client()
        user = UserFactory()
        inject_refresh(client, user)
        csrf = get_csrf_token(client)
        response = client.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    def test_refresh_reutilizado_retorna_401(self):
        """Segundo uso do mesmo refresh token → 401 (blacklist de rotação)."""
        client = make_csrf_client()
        user = UserFactory()
        refresh = inject_refresh(client, user)
        csrf = get_csrf_token(client)
        r1 = client.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf)
        assert r1.status_code == status.HTTP_200_OK
        client2 = make_csrf_client()
        client2.cookies["refresh_token"] = str(refresh)
        csrf2 = get_csrf_token(client2)
        r2 = client2.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf2)
        assert r2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_conta_suspensa_retorna_401(self):
        """Refresh com user.status=suspended → 401."""
        client = make_csrf_client()
        user = UserFactory()
        inject_refresh(client, user)
        csrf = get_csrf_token(client)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.filter(pk=user.pk).update(status="suspended")
        response = client.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCSRFLogout:
    def test_logout_sem_csrf_retorna_403(self):
        """POST /logout/ sem CSRF → 403."""
        client = make_csrf_client()
        user = UserFactory()
        inject_refresh(client, user)
        get_csrf_token(client)
        response = client.post("/api/auth/logout/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_com_csrf_seta_cookies_com_maxage_zero(self):
        """POST /logout/ com CSRF → 200 e cookies com max-age=0 explicitamente."""
        client = make_csrf_client()
        user = UserFactory()
        inject_refresh(client, user)
        csrf = get_csrf_token(client)
        response = client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == status.HTTP_200_OK
        access_cookie = response.cookies.get("access_token")
        refresh_cookie = response.cookies.get("refresh_token")
        assert access_cookie is not None, "Cookie access_token não veio na resposta"
        assert refresh_cookie is not None, "Cookie refresh_token não veio na resposta"
        assert (
            access_cookie.get("max-age", 1) in (0, "0", "", None)
            or access_cookie["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
        )

    def test_refresh_apos_logout_retorna_401(self):
        """Após logout, tentativa de refresh → 401."""
        client = make_csrf_client()
        user = UserFactory()
        refresh = inject_refresh(client, user)
        csrf = get_csrf_token(client)
        r_logout = client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=csrf)
        assert r_logout.status_code == status.HTTP_200_OK
        client2 = make_csrf_client()
        client2.cookies["refresh_token"] = str(refresh)
        csrf2 = get_csrf_token(client2)
        r_refresh = client2.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf2)
        assert r_refresh.status_code == status.HTTP_401_UNAUTHORIZED
