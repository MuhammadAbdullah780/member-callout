from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import CrewLinkTokenObtainPairSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ - exchange username/password for a JWT pair."""

    serializer_class = CrewLinkTokenObtainPairSerializer
