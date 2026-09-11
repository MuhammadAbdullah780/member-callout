from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CrewLinkTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the actor's role and local to the token payload and login response."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['local_id'] = user.local_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['local_id'] = self.user.local_id
        return data
