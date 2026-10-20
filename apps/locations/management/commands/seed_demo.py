"""Fill the database with demo data: users, categories, 30 locations, reviews, votes and views."""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.locations.cache import invalidate_list_cache
from apps.locations.models import Category, Location, LocationView
from apps.reviews.models import Review, ReviewVote

User = get_user_model()

PASSWORD = "Demo-pass-123"
USERNAMES = ["anna", "oleh", "iryna", "taras", "maria"]
CATEGORIES = ["Парки", "Кафе", "Музеї", "Оглядові майданчики", "Ресторани"]

# (title, category, city, latitude, longitude)
LOCATIONS = [
    ("Маріїнський парк", "Парки", "Київ", 50.4472, 30.5368),
    ("Ботанічний сад імені Фоміна", "Парки", "Київ", 50.4435, 30.5075),
    ("Парк Шевченка", "Парки", "Харків", 49.9996, 36.2330),
    ("Стрийський парк", "Парки", "Львів", 49.8227, 24.0345),
    ("Софіївка", "Парки", "Умань", 48.7595, 30.2292),
    ("Шевченківський гай", "Парки", "Львів", 49.8485, 24.0590),
    ("Кав'ярня «Копальня кави»", "Кафе", "Львів", 49.8419, 24.0315),
    ("Кафе «Львівська копальня»", "Кафе", "Львів", 49.8412, 24.0340),
    ("Кав'ярня «Лавка»", "Кафе", "Київ", 50.4501, 30.5234),
    ("Кафе «Бабусі»", "Кафе", "Одеса", 46.4846, 30.7326),
    ("Кав'ярня біля Оперного", "Кафе", "Одеса", 46.4859, 30.7413),
    ("Кафе «Старе місто»", "Кафе", "Івано-Франківськ", 48.9226, 24.7111),
    ("Національний музей історії України", "Музеї", "Київ", 50.4590, 30.5170),
    ("Музей Ханенків", "Музеї", "Київ", 50.4448, 30.5169),
    ("Львівська національна галерея мистецтв", "Музеї", "Львів", 49.8393, 24.0301),
    ("Одеський художній музей", "Музеї", "Одеса", 46.4871, 30.7388),
    ("Чернівецький краєзнавчий музей", "Музеї", "Чернівці", 48.2915, 25.9358),
    ("Високий замок", "Оглядові майданчики", "Львів", 49.8480, 24.0376),
    ("Володимирська гірка", "Оглядові майданчики", "Київ", 50.4570, 30.5290),
    ("Оглядовий майданчик на Лисій горі", "Оглядові майданчики", "Київ", 50.3980, 30.6040),
    ("Потьомкінські сходи", "Оглядові майданчики", "Одеса", 46.4893, 30.7415),
    ("Говерла", "Оглядові майданчики", "Карпати", 48.1601, 24.5004),
    ("Ресторан «Криївка»", "Ресторани", "Львів", 49.8416, 24.0322),
    ("Ресторан «Канапа»", "Ресторани", "Львів", 49.8423, 24.0310),
    ("Ресторан «Пузата хата»", "Ресторани", "Київ", 50.4467, 30.5222),
    ("Ресторан «Гуцульщина»", "Ресторани", "Івано-Франківськ", 48.9230, 24.7090),
    ("Ресторан «Дача»", "Ресторани", "Харків", 50.0040, 36.2310),
    ("Бульвар Шевченка", "Парки", "Київ", 50.4442, 30.5000),
    ("Дендропарк «Олександрія»", "Парки", "Біла Церква", 49.7860, 30.0920),
    ("Парк «Нивки»", "Парки", "Київ", 50.4630, 30.4090),
]

COMMENTS = [
    "Чудове місце, обов'язково повернуся.",
    "Нормально, але багато людей.",
    "Дуже сподобалось, раджу всім.",
    "Не вразило, очікував більшого.",
    "Гарна атмосфера і приємний персонал.",
    "Варто відвідати хоча б раз.",
    "Затишно та красиво.",
    "Ціни завищені, але місце цікаве.",
    "",
]


class Command(BaseCommand):
    help = "Create demo data (30 locations with reviews, votes and views). Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete previously seeded data and recreate it")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username__in=USERNAMES).exists():
            if not options["reset"]:
                self.stdout.write("Demo data already exists. Use --reset to recreate it.")
                return
            self.reset()

        rng = random.Random(42)  # deterministic demo data
        users = [User.objects.create_user(name, f"{name}@example.com", PASSWORD) for name in USERNAMES]
        categories = {name: Category.objects.get_or_create(name=name)[0] for name in CATEGORIES}

        locations = [
            Location.objects.create(
                title=title, category=categories[category], address=f"{city}", latitude=lat, longitude=lng,
                description=f"{title}: цікаве місце ({city}) для відвідування.", author=rng.choice(users),
            )
            for title, category, city, lat, lng in LOCATIONS
        ]

        reviews = []
        for location in locations:
            for author in rng.sample(users, rng.randint(0, len(users))):
                rating = rng.choices([1, 2, 3, 4, 5], weights=[1, 1, 2, 4, 5])[0]
                reviews.append(
                    Review.objects.create(location=location, author=author, rating=rating, comment=rng.choice(COMMENTS))
                )

        votes = [
            ReviewVote(review=review, user=voter, value=rng.choice([1, 1, 1, -1]))
            for review in reviews
            for voter in rng.sample(users, rng.randint(0, len(users)))
        ]
        ReviewVote.objects.bulk_create(votes)

        now = timezone.now()
        views = [LocationView(location=location) for location in locations for _ in range(rng.choice([0, 3, 10, 25, 40]))]
        LocationView.objects.bulk_create(views)  # auto_now_add stamps "now" ...
        for view in views:  # ... so spread them over the last 14 days (some fall outside the 7-day window)
            view.created_at = now - timedelta(days=rng.uniform(0, 14))
        LocationView.objects.bulk_update(views, ["created_at"])

        invalidate_list_cache()  # bulk inserts bypass the signals
        self.stdout.write(self.style.SUCCESS(
            f"Created {len(users)} users, {len(categories)} categories, {len(locations)} locations, "
            f"{len(reviews)} reviews, {len(votes)} votes, {len(views)} views. "
            f"Users: {', '.join(USERNAMES)} / password: {PASSWORD}"
        ))

    def reset(self):
        # deleting the users cascades to their locations, reviews, votes and views
        User.objects.filter(username__in=USERNAMES).delete()
        Category.objects.filter(name__in=CATEGORIES, locations__isnull=True).delete()
        invalidate_list_cache()
