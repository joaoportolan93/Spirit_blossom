"""
Factory-boy factories para os testes.
"""
import factory
from django.contrib.auth import get_user_model

from posts.models import Post
from social.models import Block, Follow

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    status = User.Status.ACTIVE
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        user = model_class(**kwargs)
        user.set_password(password)
        user.save()
        return user


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    author = factory.SubFactory(UserFactory)
    content_text = factory.Sequence(lambda n: f"Conteúdo do post número {n}.")
    visibility = Post.Visibility.PUBLIC


class FollowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory(UserFactory)
    followed = factory.SubFactory(UserFactory)


class BlockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Block

    blocker = factory.SubFactory(UserFactory)
    blocked = factory.SubFactory(UserFactory)
