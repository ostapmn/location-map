from rest_framework import serializers

from .models import Review, ReviewVote


class ReviewSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    likes = serializers.IntegerField(read_only=True)
    dislikes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "location", "author", "author_username", "rating", "comment",
            "likes", "dislikes", "created_at", "updated_at",
        ]
        read_only_fields = ["location", "author", "created_at", "updated_at"]


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=[ReviewVote.LIKE, ReviewVote.DISLIKE])
