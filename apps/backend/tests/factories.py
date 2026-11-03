"""
Factory-boy factories para os testes.
"""
import datetime
import factory
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from posts.models import Post
from social.models import Block, Follow

User = get_user_model()


class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory("tests.factories.UserFactory")
    birth_date = datetime.date(1990, 1, 1)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

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

    @factory.post_generation
    def profile(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return
        try:
            if hasattr(self, "profile"):
                return
        except UserProfile.DoesNotExist:
            pass
        UserProfile.objects.create(
            user=self,
            birth_date=datetime.date(1990, 1, 1),
        )


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
