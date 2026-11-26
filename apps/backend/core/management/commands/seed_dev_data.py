"""
Comando de seed para ambiente de desenvolvimento.

Uso:
    python manage.py seed_dev_data           # cria 20 seeds
    python manage.py seed_dev_data --purge   # apaga seeds antigos e recria

NUNCA é chamado automaticamente. Não inclua em migrações nem em Dockerfile.
Seeds são identificados pelo e-mail '@seed.spiritblossom.dev'.
"""

import random

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

User = get_user_model()

SEED_EMAIL_SUFFIX = "@seed.spiritblossom.dev"
SEED_EMAIL_SUFFIX_LEGACY = "@seed.spiritblossom.local"
TARGET_USERNAME = "adasdsadasdasdas"

SEEDS = [
    {
        "username": "lunasilva",
        "display_name": "Luna Silva",
        "bio": "Fotógrafa urbana e viajante compulsiva | São Paulo",
        "password": "SeedPass#2026!",
    },
    {
        "username": "felipetrilha",
        "display_name": "Felipe Moraes",
        "bio": "Trilheiro de fim de semana e fã de café artesanal",
        "password": "SeedPass#2026!",
    },
    {
        "username": "helenaflores",
        "display_name": "Helena Carvalho",
        "bio": "Botânica amadora | Jardim, leitura e um bom vinho",
        "password": "SeedPass#2026!",
    },
    {
        "username": "brunoskate",
        "display_name": "Bruno Martins",
        "bio": "Skatista desde os 12. Street art lover | Rio de Janeiro",
        "password": "SeedPass#2026!",
    },
    {
        "username": "camilamoda",
        "display_name": "Camila Azevedo",
        "bio": "Estilista independente & criadora de conteúdo de moda lenta",
        "password": "SeedPass#2026!",
    },
    {
        "username": "matheuschef",
        "display_name": "Matheus Lima",
        "bio": "Chef experimental | Receitas autorais e viagens gastronômicas",
        "password": "SeedPass#2026!",
    },
    {
        "username": "gabrieltech",
        "display_name": "Gabriel Santos",
        "bio": "Dev full-stack fã de open source e café | beta tester",
        "password": "SeedPass#2026!",
    },
    {
        "username": "juliadesign",
        "display_name": "Julia Ferreira",
        "bio": "UX designer & ilustradora. Pixel art e chá de ervas",
        "password": "SeedPass#2026!",
    },
    {
        "username": "rafaelcosta",
        "display_name": "Rafael Costa",
        "bio": "Jornalista cultural | Música, cinema e literatura",
        "password": "SeedPass#2026!",
    },
    {
        "username": "amandafit",
        "display_name": "Amanda Rocha",
        "bio": "Personal trainer e nutricionista | Saúde sem neuras",
        "password": "SeedPass#2026!",
    },
    {
        "username": "pedrogames",
        "display_name": "Pedro Alves",
        "bio": "Game dev indie e speedrunner nas horas vagas | Switch / PC",
        "password": "SeedPass#2026!",
    },
    {
        "username": "thiagosom",
        "display_name": "Thiago Oliveira",
        "bio": "Produtor musical e DJ de fim de semana | Belo Horizonte",
        "password": "SeedPass#2026!",
    },
    {
        "username": "sofiacafe",
        "display_name": "Sofia Mendes",
        "bio": "Barista e sommelier de cafés especiais | Curitiba",
        "password": "SeedPass#2026!",
    },
    {
        "username": "lucasmovies",
        "display_name": "Lucas Ribeiro",
        "bio": "Cinéfilo assumido | Crítica e teoria do cinema",
        "password": "SeedPass#2026!",
    },
    {
        "username": "bialivros",
        "display_name": "Beatriz Nunes",
        "bio": "Escritora em construção e leitora voraz",
        "password": "SeedPass#2026!",
    },
    {
        "username": "marcosdev",
        "display_name": "Marcos Pereira",
        "bio": "Arquiteto de software & entusiasta de Rust | Open source",
        "password": "SeedPass#2026!",
    },
    {
        "username": "lauraviagem",
        "display_name": "Laura Gomes",
        "bio": "Nômade digital | 42 países visitados, próximo: Japão",
        "password": "SeedPass#2026!",
    },
    {
        "username": "claraarte",
        "display_name": "Clara Dias",
        "bio": "Artista plástica e tatuadora | Aquarela e grafite",
        "password": "SeedPass#2026!",
    },
    {
        "username": "diegoretro",
        "display_name": "Diego Souza",
        "bio": "Colecionador de vinis e fã de sintetizadores analógicos",
        "password": "SeedPass#2026!",
    },
    {
        "username": "valentinaink",
        "display_name": "Valentina Cruz",
        "bio": "Tatuadora e artista gráfica | Blackwork e fineline",
        "password": "SeedPass#2026!",
    },
]

SEED_POSTS = [
    "Acabei de descobrir um café incrível aqui em SP. #cafe #sp #lumen",
    "Alguém mais viciado em trilha sonora de série enquanto trabalha? #playlist #foco",
    "Mais um final de semana de produção intensa. Valeu a pena! #criatividade #processo",
    "Tô lendo um livro que mudou minha perspectiva sobre tecnologia. #leitura #tech",
    "Pôr do sol na cidade tem uma beleza subestimada #fotografiaurbana",
    "Fizeram uma coisa genial no último episódio da série que tô assistindo #cinema #serie",
    "Dica pro dia: hidrate-se. Simples assim. #saude #bemestar",
    "Novo projeto em desenvolvimento. Não posso contar ainda, mas fica ligado! #dev #hint",
    "Fim de expediente. Hora do chá e do livro #rotina #paz",
    "Beleza em coisas simples: sol pela janela pela manhã #gratidao",
    "Se você nunca foi num show ao vivo desse artista, tá perdendo #musica #show",
    "Aprendi mais nos últimos 3 meses do que em 1 ano. Nunca pare de estudar. #aprendizado",
    "Recebendo feedback construtivo hoje. Dói, mas é necessário. #crescimento #profissional",
    "Comida caseira sempre vence qualquer restaurante #cozinha #caseiro",
    "Galera de SP, qual o melhor rolê cultural do momento? Precisando de dicas! #sp #cultura",
]

CROSS_MENTION_POSTS = [
    "Bora marcar aquele café no centro @sofiacafe e @lunasilva? #cafe #sp",
    "Recomendo demais a playlist nova do @thiagosom pra codar! @marcosdev vai curtir #musica #dev",
    "Adorei as últimas fotos do @brunoskate, estética absurda #fotografia #arte",
    "Alguém já testou a receita nova do @matheuschef? Ficou absurda! #cozinha",
    "Discussão boa ontem sobre cinema com @lucasmovies e @rafaelcosta #cinema #cultura",
]

CROSS_COMMENTS = [
    "Concordo demais com isso!",
    "Muito bom, salvando aqui pra ver depois.",
    "Haha, exatamente minha rotina dessa semana.",
    "Curti muito a ideia, conta mais depois!",
    "Top demais! #lumen",
]

MENTION_POST_TEMPLATES = [
    "Dando boas-vindas oficiais para @{target} na timeline! #bemvindo #lumen",
    "Recomendo todo mundo dar uma olhada no perfil do @{target} por aqui! #sugestao",
    "Trocando ideias sobre novos projetos com @{target} hoje. #lumen #tecnologia",
    "Descobri o Spirit Blossom pelo @{target}. Que plataforma incrível! #spiritblossom #novidades",
    "Boa sorte pra @{target} nos próximos projetos! Vai chegar longe #motivacao",
]

COMMENT_TEMPLATES = [
    ("Adorei essa publicação! Continua assim", False),
    ("Que conteúdo incrível! Muito a ver com o que ando pensando ultimamente", False),
    ("Concordo totalmente! Obrigado por compartilhar essa perspectiva", False),
    ("Minha reação ao ver esse post:", "gif_reaction_1"),
    ("Exatamente o que eu precisava ler hoje", "gif_reaction_2"),
]


def _build_seed_gif(label: str, palette_index: int):
    """Gera um GIF animado em memória via Pillow (sem dependência de rede externa)."""
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image, ImageDraw

    palettes = [
        [(236, 72, 153), (168, 85, 247), (59, 130, 246)],
        [(16, 185, 129), (245, 158, 11), (244, 63, 94)],
    ]
    colors = palettes[palette_index % len(palettes)]
    frames = []
    for idx, color in enumerate(colors):
        img = Image.new("RGBA", (320, 180), (24, 24, 27, 255))
        draw = ImageDraw.Draw(img)
        radius = 28 + idx * 14
        cx, cy = 160, 82
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
        draw.text((16, 146), f"Spirit Blossom • {label}", fill=(250, 250, 250, 255))
        frames.append(img)

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=220,
        loop=0,
    )
    return SimpleUploadedFile(f"seed_{palette_index}.gif", buf.getvalue(), content_type="image/gif")


class Command(BaseCommand):
    help = "Cria seeds de desenvolvimento (20 usuários falsos com interações realistas)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Remove todos os seeds existentes antes de criar novos.",
        )
        parser.add_argument(
            "--target",
            default=TARGET_USERNAME,
            help="Username da conta alvo que receberá seguidores, curtidas e menções.",
        )

    def handle(self, *args, **options):
        from comments.services import create_comment
        from core.models import UserProfile
        from core.services.posts import create_post, like_post, list_posts_for_export
        from core.services.social import follow_user

        # Em dev não há broker Celery rodando — força modo síncrono para evitar
        # ConnectionRefusedError no hook pós-commit de notificações push.
        django_settings.CELERY_TASK_ALWAYS_EAGER = True
        django_settings.CELERY_ALWAYS_EAGER = True

        if options["purge"]:
            self._purge_seeds()

        target_username = options.get("target") or TARGET_USERNAME
        try:
            target_user = User.objects.get(username__iexact=target_username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"Usuário @{target_username} não encontrado. Crie a conta antes do seed."
            ) from exc

        self.stdout.write(f"Usuário alvo: @{target_user.username}")

        target_post = list_posts_for_export(author=target_user).first()
        if not target_post:
            raise CommandError(
                f"@{target_username} não tem nenhum post. Crie um post antes de rodar o seed."
            )
        self.stdout.write(f"Post alvo: '{target_post.content_text[:50]}...'")

        def _safe_follow(follower, followed):
            try:
                follow_user(follower=follower, target_user=followed)
                return True
            except ValueError:
                return False

        created_users = []
        seed_posts = []

        with transaction.atomic():
            # 1. Cria os 20 seeds
            for seed_data in SEEDS:
                user, created = User.objects.get_or_create(
                    username=seed_data["username"],
                    defaults={
                        "email": f"{seed_data['username']}{SEED_EMAIL_SUFFIX}",
                    },
                )
                if created:
                    user.set_password(seed_data["password"])
                    user.save()
                    self.stdout.write(f"  [ok] Criado @{user.username}")
                else:
                    self.stdout.write(f"  [skip] @{user.username} já existe, usando existente")

                if not user.email.endswith(SEED_EMAIL_SUFFIX):
                    user.email = f"{seed_data['username']}{SEED_EMAIL_SUFFIX}"
                    user.save(update_fields=["email"])

                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.display_name = seed_data["display_name"]
                profile.bio = seed_data["bio"]
                profile.save(update_fields=["display_name", "bio"])
                created_users.append(user)

            # 2. Cada seed cria 1-2 posts genéricos
            for user in created_users:
                if list_posts_for_export(author=user).exists():
                    continue
                n_posts = random.randint(1, 2)
                pool = random.sample(SEED_POSTS, min(n_posts, len(SEED_POSTS)))
                for text in pool:
                    post = create_post(author=user, content_text=text, visibility="public")
                    seed_posts.append(post)

            # Posts cruzados mencionando outros seeds
            for i, text in enumerate(CROSS_MENTION_POSTS):
                author = created_users[(10 + i) % len(created_users)]
                post = create_post(author=author, content_text=text, visibility="public")
                seed_posts.append(post)

            # Comentários e follows cruzados entre seeds
            for i, post in enumerate(seed_posts[:8]):
                commenter = created_users[(i + 3) % len(created_users)]
                if commenter != post.author:
                    create_comment(
                        author=commenter,
                        post=post,
                        content_text=CROSS_COMMENTS[i % len(CROSS_COMMENTS)],
                    )
                    _safe_follow(commenter, post.author)

            self.stdout.write(f"Posts e interações cruzadas criados ({len(seed_posts)} posts)")

            # 3. 5 seeds seguem @target
            for user in created_users[:5]:
                if _safe_follow(user, target_user):
                    self.stdout.write(f"  + @{user.username} seguiu @{target_user.username}")

            # 4. 5 seeds curtem o post do @target
            for user in created_users[:5]:
                like_post(user=user, post_id=target_post.id)
                self.stdout.write(f"  [like] @{user.username} curtiu o post")

            # 5. 5 seeds comentam no post do @target (2 com GIF animado real)
            for i, user in enumerate(created_users[:5]):
                comment_text, meme_tag = COMMENT_TEMPLATES[i % len(COMMENT_TEMPLATES)]
                gif_file = _build_seed_gif(meme_tag, i) if meme_tag else None
                create_comment(
                    author=user,
                    post=target_post,
                    content_text=comment_text,
                    image=gif_file,
                )
                tag = "(+GIF)" if gif_file else ""
                self.stdout.write(f"  [comment] @{user.username} comentou {tag}".strip())

            # 6. 5 seeds mencionam @target em posts próprios
            for i, user in enumerate(created_users[5:10]):
                text = MENTION_POST_TEMPLATES[i % len(MENTION_POST_TEMPLATES)].format(
                    target=target_user.username
                )
                create_post(author=user, content_text=text, visibility="public")
                self.stdout.write(f"  [mention] @{user.username} mencionou @{target_user.username}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed concluído com sucesso!\n"
                f"  - 20 usuários seed ativos\n"
                f"  - 5 seguidores novos para @{target_user.username}\n"
                f"  - 5 curtidas no post '{target_post.content_text[:30]}...'\n"
                f"  - 5 comentários (2 com GIF/meme)\n"
                f"  - 5 menções em posts de outros seeds\n"
            )
        )

    def _purge_seeds(self):
        """Remove seeds antigos, comentários órfãos e notificações antigas de seeds."""
        from comments.models import Comment
        from core.models import Notification
        from core.services.posts import resync_all_post_counters

        seeds_qs = User.objects.filter(
            Q(email__endswith=SEED_EMAIL_SUFFIX) | Q(email__endswith=SEED_EMAIL_SUFFIX_LEGACY)
        )
        seed_ids = list(seeds_qs.values_list("id", flat=True))
        usernames = list(seeds_qs.values_list("username", flat=True))

        # Remove notificações enviadas por seeds ou órfãs (sender=None após purge prévio)
        Notification.objects.filter(
            Q(sender_id__in=seed_ids) | Q(recipient_id__in=seed_ids) | Q(sender__isnull=True)
        ).delete()

        # Remove comentários dos seeds e comentários órfãos (author SET_NULL)
        Comment.objects.filter(
            Q(author_id__in=seed_ids) | Q(author__isnull=True, is_deleted=False)
        ).delete()

        count = len(seed_ids)
        if count > 0:
            seeds_qs.delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Removidos {count} seeds: {', '.join(f'@{u}' for u in usernames)}"
                )
            )
        else:
            self.stdout.write("[info] Nenhum seed antigo para remover.")

        resync_all_post_counters()
