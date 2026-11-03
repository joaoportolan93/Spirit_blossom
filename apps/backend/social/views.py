"""
Views sociais: follow, unfollow, block.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Block, Follow

User = get_user_model()


class FollowView(APIView):
    """
    POST /api/social/follow/<username>/   → seguir usuário
    DELETE /api/social/follow/<username>/ → deixar de seguir
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        if target == request.user:
            return Response(
                {"detail": "Não é possível seguir a si mesmo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _, created = Follow.objects.get_or_create(
            follower=request.user,
            followed=target,
        )
        if not created:
            return Response(
                {"detail": "Já está seguindo este usuário."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Seguindo."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        deleted, _ = Follow.objects.filter(
            follower=request.user,
            followed=target,
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Não estava seguindo este usuário."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockView(APIView):
    """
    POST /api/social/block/<username>/   → bloquear usuário
    DELETE /api/social/block/<username>/ → desbloquear
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        if target == request.user:
            return Response(
                {"detail": "Não é possível bloquear a si mesmo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Bloquear remove o follow em ambas as direções
        Follow.objects.filter(follower=request.user, followed=target).delete()
        Follow.objects.filter(follower=target, followed=request.user).delete()

        _, created = Block.objects.get_or_create(
            blocker=request.user,
            blocked=target,
        )
        if not created:
            return Response(
                {"detail": "Usuário já está bloqueado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Usuário bloqueado."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        deleted, _ = Block.objects.filter(
            blocker=request.user,
            blocked=target,
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Usuário não estava bloqueado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
