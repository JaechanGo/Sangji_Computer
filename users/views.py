from django.conf import settings
from django.utils.datastructures import MultiValueDictKeyError
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .decorators import login_message_required, admin_required, logout_message_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect, get_object_or_404
# from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, FormView, TemplateView
from django.views.generic import View
# from django.contrib.auth.views import PasswordResetConfirmView
from .models import User
from free.models import Free, Comment
from anonymous.models import Anonymous, AnonymousComment
from notice.models import Notice
from calender.models import Calender
from django.core.exceptions import ValidationError
from .forms import CsRegisterForm, RegisterForm, LoginForm, CustomUserChangeForm, CustomCsUserChangeForm, CheckPasswordForm, RecoveryIdForm, RecoveryPwForm, CustomSetPasswordForm, CustomPasswordChangeForm
from django.http import HttpResponse
import json
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from .helper import send_mail, email_auth_num
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, Http404
from django.forms.utils import ErrorList
from django.views.decorators.http import require_GET, require_POST
from django.core.exceptions import PermissionDenied

from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_text
from django.contrib.auth.tokens import default_token_generator
from datetime import datetime
# from ipware.ip import get_ip


# ????????????(????????? ???)
def index(request):
    # ip = get_ip(request)
    # if ip is not None:
    #     print (ip)
    # else:
    #     print ("IP FIND ERROR")

    return render(request, 'users/index.html')


# ????????????(????????? ???)
@login_message_required
def main_view(request):
    return render(request, 'users/main.html')


# ?????????
@method_decorator(logout_message_required, name='dispatch')
class LoginView(FormView):
    template_name = 'users/login.html'
    form_class = LoginForm
    success_url = '/users/main/'

    def form_valid(self, form):
        user_id = form.cleaned_data.get("user_id")
        password = form.cleaned_data.get("password")

        user = authenticate(self.request, username=user_id, password=password)
        if user is not None:
            self.request.session['user_id'] = user_id
            login(self.request, user)

            # Session Maintain Test

            remember_session = self.request.POST.get('remember_session', False)
            if remember_session:
                settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = False

            # try:
            #     remember_session = self.request.POST['remember_session']
            #     if remember_session:
            #         settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = False
            # except MultiValueDictKeyError:
            #     settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = True
            
        return super().form_valid(form)


# ????????????
def logout_view(request):
    logout(request)
    return redirect('/')


# ???????????? ????????????
@method_decorator(logout_message_required, name='dispatch')
class AgreementView(View):
    def get(self, request, *args, **kwargs):
        request.session['agreement'] = False
        return render(request, 'users/agreement.html')

    def post(self, request, *args, **kwarg):
        if request.POST.get('agreement1', False) and request.POST.get('agreement2', False):
            request.session['agreement'] = True
            if request.POST.get('csregister') == 'csregister':       
                return redirect('/users/csregister/')
            else:
                return redirect('/users/register/')
        else:
            messages.info(request, "????????? ?????? ??????????????????.")
            return render(request, 'users/agreement.html')   


# ???????????? ???????????? ?????? ?????? ???
def register_success(request):
    if not request.session.get('register_auth', False):
        raise PermissionDenied
    request.session['register_auth'] = False

    return render(request, 'users/register_success.html')


# ?????? ???????????? 
class CsRegisterView(CreateView):
    model = User
    template_name = 'users/register_cs.html'
    form_class = CsRegisterForm

    def get(self, request, *args, **kwargs):
        if not request.session.get('agreement', False):
            raise PermissionDenied
        request.session['agreement'] = False

        url = settings.LOGIN_REDIRECT_URL
        if request.user.is_authenticated:
            return HttpResponseRedirect(url)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        # messages.success(self.request, "???????????? ??????.")
        self.request.session['register_auth'] = True
        messages.success(self.request, '???????????? ????????? Email ????????? ?????? ????????? ?????????????????????. ?????? ??? ???????????? ???????????????.')
        # return settings.LOGIN_URL
        return reverse('users:register_success')

    def form_valid(self, form):
        self.object = form.save()

        # ???????????? ?????? ?????? ??????
        # ISSUE - https ???????????? -> http ???????????? ??????
        send_mail(
            '[??????????????? ?????????????????? RE:BORN] {}?????? ???????????? ???????????? ?????????.'.format(self.object.user_id),
            [self.object.email],
            html=render_to_string('users/register_email.html', {
                'user': self.object,
                'uid': urlsafe_base64_encode(force_bytes(self.object.pk)).encode().decode(),
                'domain': self.request.META['HTTP_HOST'],
                'token': default_token_generator.make_token(self.object),
            }),
        )
        return redirect(self.get_success_url())


# ?????? ????????????
class RegisterView(CsRegisterView):
    template_name = 'users/register.html'
    form_class = RegisterForm


# ????????? ?????? ?????????
def activate(request, uid64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uid64))
        current_user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
        messages.error(request, '?????? ????????? ??????????????????.')
        return redirect('users:login')

    if default_token_generator.check_token(current_user, token):
        current_user.is_active = True
        current_user.save()

        messages.info(request, '?????? ????????? ?????? ???????????????. ??????????????? ??????????????????!')
        return redirect('users:login')

    messages.error(request, '?????? ????????? ??????????????????.')
    return redirect('users:login')


# ????????? ??????
@login_message_required
def profile_view(request):
    if request.method == 'GET':
        return render(request, 'users/profile.html')


# ????????? ??????
@login_message_required
def profile_update_view(request):
    if request.method == 'POST':
        if request.user.department == '??????????????????':
            user_change_form = CustomCsUserChangeForm(request.POST, instance = request.user)
        else:   
            user_change_form = CustomUserChangeForm(request.POST, instance = request.user)

        if user_change_form.is_valid():
            user_change_form.save()
            messages.success(request, '??????????????? ?????????????????????.')
            return render(request, 'users/profile.html')
    else:
        if request.user.department == '??????????????????':
            user_change_form = CustomCsUserChangeForm(instance = request.user)
        else:   
            user_change_form = CustomUserChangeForm(instance = request.user)

        return render(request, 'users/profile_update.html', {'user_change_form':user_change_form})


# ????????????
@login_message_required
def profile_delete_view(request):
    if request.method == 'POST':
        password_form = CheckPasswordForm(request.user, request.POST)
        
        if password_form.is_valid():
            request.user.delete()
            logout(request)
            messages.success(request, "??????????????? ?????????????????????.")
            return redirect('/')
    else:
        password_form = CheckPasswordForm(request.user)

    return render(request, 'users/profile_delete.html', {'password_form':password_form})


# ???????????? ??????
@login_message_required
def password_edit_view(request):
    if request.method == 'POST':
        password_change_form = CustomPasswordChangeForm(request.user, request.POST)
        if password_change_form.is_valid():
            user = password_change_form.save()
            update_session_auth_hash(request, user)
            # logout(request)
            messages.success(request, "??????????????? ??????????????? ?????????????????????.")
            return redirect('users:profile')
    else:
        password_change_form = CustomPasswordChangeForm(request.user)

    return render(request, 'users/profile_password.html', {'password_change_form':password_change_form})


# ???????????????
@method_decorator(logout_message_required, name='dispatch')
class RecoveryIdView(View):
    template_name = 'users/recovery_id.html'
    recovery_id = RecoveryIdForm

    def get(self, request):
        if request.method=='GET':
            form_id = self.recovery_id(None)
        return render(request, self.template_name, { 'form_id':form_id, })


# ??????????????????
@method_decorator(logout_message_required, name='dispatch')
class RecoveryPwView(View):
    template_name = 'users/recovery_pw.html'
    recovery_pw = RecoveryPwForm

    def get(self, request):
        if request.method=='GET':
            form_pw = self.recovery_pw(None)
            return render(request, self.template_name, { 'form_pw':form_pw, })


# ??????????????? AJAX ??????
def ajax_find_id_view(request):
    name = request.POST.get('name')
    email = request.POST.get('email')
    result_id = User.objects.get(name=name, email=email)
       
    return HttpResponse(json.dumps({"result_id": result_id.user_id}, cls=DjangoJSONEncoder), content_type = "application/json")    


# ?????????????????? AJAX ??????
def ajax_find_pw_view(request):
    user_id = request.POST.get('user_id')
    name = request.POST.get('name')
    email = request.POST.get('email')
    result_pw = User.objects.get(user_id=user_id, name=name, email=email)

    if result_pw:
        auth_num = email_auth_num()
        result_pw.auth = auth_num 
        result_pw.save()

        send_mail(
            '[??????????????? ?????????????????? RE:BORN] ???????????? ?????? ?????????????????????.',
            [email],
            html=render_to_string('users/recovery_email.html', {
                'auth_num': auth_num,
            }),
        )
    # print(auth_num)
    return HttpResponse(json.dumps({"result": result_pw.user_id}, cls=DjangoJSONEncoder), content_type = "application/json")


# ?????????????????? ???????????? ??????
def auth_confirm_view(request):
    # if request.method=='POST' and 'auth_confirm' in request.POST:
    user_id = request.POST.get('user_id')
    input_auth_num = request.POST.get('input_auth_num')
    user = User.objects.get(user_id=user_id, auth=input_auth_num)
    # login(request, user)
    user.auth = ""
    user.save()
    request.session['auth'] = user.user_id  
    
    return HttpResponse(json.dumps({"result": user.user_id}, cls=DjangoJSONEncoder), content_type = "application/json")

        
# ?????????????????? ??????????????? ??????
@logout_message_required
def auth_pw_reset_view(request):
    if request.method == 'GET':
        if not request.session.get('auth', False):
            raise PermissionDenied

    if request.method == 'POST':
        session_user = request.session['auth']
        current_user = User.objects.get(user_id=session_user)
        # del(request.session['auth'])
        login(request, current_user)

        reset_password_form = CustomSetPasswordForm(request.user, request.POST)
        
        if reset_password_form.is_valid():
            user = reset_password_form.save()
            messages.success(request, "???????????? ????????????! ????????? ??????????????? ??????????????????.")
            logout(request)
            return redirect('users:login')
        else:
            logout(request)
            request.session['auth'] = session_user
    else:
        reset_password_form = CustomSetPasswordForm(request.user)

    return render(request, 'users/password_reset.html', {'form':reset_password_form})


# ?????? ??? ??? ??????
@login_message_required
@require_GET
def profile_post_view(request):
    free_list = Free.objects.filter(writer=request.user.id).order_by('-registered_date')
    anonymous_list = Anonymous.objects.filter(writer=request.user.id).order_by('-registered_date')
    context = {
        'free_list': free_list,
        'anonymous_list': anonymous_list,
    }
    if request.user.level == '0' or request.user.level == '1' :
        notice_list = Notice.objects.filter(writer=request.user.id).order_by('-registered_date')
        context['notice_list'] = notice_list

    return render(request, 'users/profile_post.html', context)


# ?????? ??? ??? ??????
@login_message_required
@require_GET
def profile_comment_view(request):
    comment_list = Comment.objects.select_related('post').filter(writer=request.user).exclude(deleted=True).order_by('-created')
    anonymous_comment_list = AnonymousComment.objects.select_related('post').filter(writer=request.user).exclude(deleted=True).order_by('-created')
    context = {
        'comment_list': comment_list,
        'anonymous_comment_list': anonymous_comment_list,
    }
    return render(request, 'users/profile_comment.html', context)