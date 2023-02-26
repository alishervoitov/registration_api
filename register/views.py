from xml.dom import ValidationErr

import jwt
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.shortcuts import render
from django.utils.encoding import smart_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from register.models import CustomerUser
from register.renderers import UserRenderer
from register.serializers import RegistrationSerializer, UserLoginSerializer, UserProfileSerializer, \
    ChangePasswordSerializer, EditProfileSerializer, VerifySerializer
from rest_framework.response import Response

from register.utils import Util


def get_tokens_for_user(user):

    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
class RegistrationAPIView(generics.GenericAPIView):

    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request, format=None):

        data = request.data
        username = data['username']
        full_name = data['full_name']
        email = data['email']
        password = data['password']
        password1 = data['password1']
        country = data['country']
        company_name = data['company_name']
        user_type = data['user_type']
        phone_number = data['phone_number']
        corporate_number = data['corporate_number']

        if CustomerUser.objects.filter(email=email).exists():
            return Response({'Error': 'email already exists'}, status=status.HTTP_400_BAD_REQUEST)
        if password != password1:
            return Response({'Error': 'Passwords arent match'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = CustomerUser.objects.create_user(
                username=username,
                full_name=full_name,
                email=email,
                password=password,
                country=country,
                company_name=company_name,
                user_type=user_type,
                phone_number=phone_number,
                corporate_number=corporate_number
            )
            user.set_password(password)
            user.save()
            from django.utils.encoding import force_bytes
            uid = urlsafe_base64_encode(force_bytes(user.id))
            token = PasswordResetTokenGenerator().make_token(user)
            link = 'http://127.0.0.1:8000/auth/verify/' + uid + '/' + token + '/'
            print(link)
            body = 'Use link below to verify your email ' + link
            data = {
                'subject': 'Your verify link',
                'body': body,
                'to_email': user.email,
            }
            Util.send_email(data)

            return Response({
                'token': get_tokens_for_user(user),
                'Message': request.data,
                'Msg': 'We send link to your email for verify',
            },
                status=status.HTTP_200_OK
            )

class UserLoginView(generics.GenericAPIView):

    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request):

        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.data.get('email')
            password = serializer.data.get('password')
            user = authenticate(email=email, password=password)
            if user and user.is_verified:
                token = get_tokens_for_user(user)
                return Response({
                    'token': token,
                    'Message': serializer.data},
                    status=status.HTTP_200_OK
                )
            else:
                return Response({'Errors': {'non_field_errors': ['Email or Password is not valid or your account is not active ']}}, status=status.HTTP_404_NOT_FOUND)

class VerificationView(generics.GenericAPIView):

    serializer_class = VerifySerializer
    permission_classes = [permissions.AllowAny]
    renderer_classes = [UserRenderer]
    token_param_config = openapi.Parameter('token', in_=openapi.IN_QUERY, description='Description', type=openapi.TYPE_STRING)
    @swagger_auto_schema(manual_parameters=[token_param_config])
    def get(self, request, token, uid):
        try:
            id = smart_str(urlsafe_base64_decode(uid))
            user = CustomerUser.objects.get(id=id)
            if not PasswordResetTokenGenerator().check_token(user, token):
                raise ValidationErr('Token is not valid or expired')
            user.is_verified = True
            user.save()
            return Response(
                {'Message': 'User activated succesfully'},
                status=status.HTTP_200_OK
            )
        except jwt.ExpiredSignatureError as identifier:
            return Response(
                {'error': 'Activation expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except jwt.exceptions.DecodeError as identifier:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
class UserProfileView(generics.GenericAPIView):

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [UserRenderer]

    def get(self, request, format=None):

        serializer = UserProfileSerializer(request.user)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

class ChangePasswordView(generics.UpdateAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = ChangePasswordSerializer
    renderer_classes = [UserRenderer]

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def post(self, request, *args, **kwargs):

        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)
        data = request.data
        new_password = data['new_password']

        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get('password')):
                return Response({"password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            self.object.set_password(new_password)
            self.object.save()
            return Response({
                'Message': request.data,
                'Msg': 'Password changed succesfully'
            },
                status=status.HTTP_200_OK,
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class EditProfileView(generics.GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = EditProfileSerializer
    queryset = CustomerUser.objects.all()
    renderer_classes = [UserRenderer]

    def put(self, request, *args, **kwargs):

        pk = kwargs.get('pk', None)
        if not pk:
            return Response({'error': 'Method put not allowed'})
        try:
            instance = CustomerUser.objects.get(pk=pk)
        except:
            return Response({'error': 'Object does not exists'})
        serializer = EditProfileSerializer(data=request.data, instance=instance)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'Message': request.data,
                'Msg': 'Your profile updated succesfully'
            },
            status=status.HTTP_400_BAD_REQUEST
        )