import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.core.paginator import Paginator
from django.db.models import Min, Max
from django.http import HttpResponseRedirect, \
    HttpResponseForbidden, HttpResponse, JsonResponse, response
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from forumapp.forms import ThreadCreateModelForm, ThreadResponseModelForm, \
    ThreadResponseDeleteForm, ThreadDeleteForm, LikeDislikeForm, BanUserForm, \
    PinThreadForm, StylizedUserCreationForm
from forumapp.permissions import IsNotBanned
from forumapp.serializers import ForumSerializer, ThreadSerializer
from .models import Thread, ForumSection, ThreadResponse, Forum, LikeDislike, \
    ForumUser
from rest_framework import viewsets, renderers, permissions


class ForumViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Forum.objects.all()
    serializer_class = ForumSerializer


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.all()
    serializer_class = ThreadSerializer

    permission_classes = (
        permissions.IsAuthenticatedOrReadOnly,
        IsNotBanned
    )


def signup_rest(request):
    pass


def signup(request):
    if request.method == 'POST':
        # form = UserCreationForm(request.POST)
        form = StylizedUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(
                username=username,
                password=raw_password
            )
            ForumUser(user=user).save()
            login(request, user)
            return redirect('index')
    else:
        form = StylizedUserCreationForm()
    return render(
        request,
        'registration/signup.html',
        {'form': form}
    )


def index(request):
    users_count = User.objects.count()
    threads_count = Thread.objects.count()

    responses_count = ThreadResponse.objects.exclude(
        thread__isnull=True
    ).count()

    responses_count -= threads_count

    return render(
        request,
        'forumapp/index.html',
        context={
            'users_count': users_count,
            'threads_count': threads_count,
            'responses_count': responses_count
        }
    )


def forums(request):
    sections = ForumSection.objects.all()
    return render(
        request,
        'forumapp/forums.html',
        context={
            'sections': sections,
        }
    )


def forum(request, pk):
    thread_list = Thread.objects.filter(
        forum=pk
    ).annotate(
        last_response=Max('threadresponse__created_datetime')
    ).order_by(
        '-pinned',
        '-last_response'
    )

    thread_paginator = Paginator(thread_list, 10)
    page = request.GET.get('page')
    thread_list = thread_paginator.get_page(page)

    return render(
        request,
        'forumapp/thread_list.html',
        context={
            'thread_list': thread_list,
            'forum': Forum.objects.get(id=pk)
        }
    )


@login_required
@permission_required('forumapp.can_pin_threads')
def pin_thread(request, fpk, tpk):
    form = PinThreadForm()
    if request.method == "POST":
        form = PinThreadForm(request.POST)
        if form.is_valid():
            thread = Thread.objects.get(pk=tpk)
            thread.pinned = form.cleaned_data['pinned']
            thread.save()

            messages.success(request, message='Post successfully pinned!')
            return HttpResponseRedirect(
                reverse('forum', kwargs={'pk': fpk})
            )
    else:
        return render(
            request,
            'forumapp/pin_thread.html',
            {'form': form}
        )


def thread_view(request, fpk, tpk):
    thread = Thread.objects.get(id=tpk)
    parent_forum = Forum.objects.get(id=fpk)
    response_list = ThreadResponse.objects.filter(
        thread=tpk,
        thread__forum=fpk
    ).order_by(
        'created_datetime'
    )
    can_delete_thread = response_list[0].responder == request.user or \
                        request.user.has_perm("forumapp.can_remove_any_thread")

    response_paginator = Paginator(
        response_list,
        10
    )

    page = request.GET.get('page')
    response_list = response_paginator.get_page(page)

    return render(
        request,
        'forumapp/thread.html',
        context={
            'thread': thread,
            'response_list': response_list,
            'forum': parent_forum,
            'can_delete_thread': can_delete_thread,
            # 'like_dislike_forms': like_dislike_forms
        }
    )


@permission_required('forumapp.can_ban_users')
def ban_user(request, pk):
    ban_user_form = BanUserForm(
        initial={
            'user': ForumUser.objects.get(pk=pk)
        }
    )

    if request.method == "POST":
        ban_user_form = BanUserForm(request.POST)
        if ban_user_form.is_valid():
            forum_user = ForumUser.objects.get(user=pk)
            forum_user.banned_until = ban_user_form.cleaned_data['banned_until']
            forum_user.save()
            return HttpResponse("Ban date changed successfully!")

    return render(
        request,
        'forumapp/ban_user.html',
        {
            'form': ban_user_form
        }
    )


@login_required
@ensure_csrf_cookie
def like_dislike_post(request, fpk, tpk, ppk, upvote):
    """
    This view is responsible for liking/disliking a response
    :param request request
    :param fpk: forum primary key
    :param tpk: thread primary key
    :param ppk: post primary key
    :param upvote: 0 or 1 - like or dislike
    """
    if request.method == 'POST':
        try:
            like_dislike_obj = LikeDislike.objects.get(
                response=ThreadResponse.objects.get(id=ppk),
                user=request.user
            )

            if like_dislike_obj.like == upvote:
                like_dislike_obj.delete()
                return JsonResponse({
                    'pk': ppk,
                    'upvote': upvote
                }, status=202)
            else:
                like_dislike_obj.like = upvote
                like_dislike_obj.save()
                return JsonResponse({
                    'to': upvote,
                    'pk': ppk
                }, status=200)

        except LikeDislike.DoesNotExist:
            like_dislike_obj = LikeDislike.objects.create(
                response=ThreadResponse.objects.get(id=ppk),
                user=request.user
            )
            like_dislike_obj.like = upvote
            like_dislike_obj.save()

            return JsonResponse({
                'like': upvote,
                'pk': ppk
            }, status=201)


@login_required
def respond(request, fpk, tpk):
    forum_user = ForumUser.objects.get(user=request.user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        return HttpResponseForbidden("You are banned! "
                                     "Check your profile for details.")

    if request.method == "POST":
        form = ThreadResponseModelForm(
            request.POST,
        )
        if form.is_valid():
            obj_response = form.save()

            obj_response.responder = request.user
            obj_response.created_datetime = datetime.datetime.now()
            obj_response.thread = Thread.objects.get(id=tpk)
            obj_response.order_in_thread = \
                obj_response.thread.threadresponse_set.count() + 1

            obj_response.save()

            return HttpResponseRedirect(
                reverse(
                    'thread-view',
                    kwargs={
                        'fpk': fpk,
                        'tpk': tpk
                    }
                )
            )
    else:
        form = ThreadResponseModelForm()
    return render(
        request,
        'forumapp/threadresponse_form.html',
        context={
            'form': form,
            'forum': Forum.objects.get(id=fpk),
            'thread': Thread.objects.get(id=tpk)
        }
    )


@login_required
def delete_thread(request, fpk, tpk):
    if request.method == "POST":
        form = ThreadDeleteForm(request.POST)
        if form.is_valid():
            thread = Thread.objects.get(id=tpk)

            creator = thread.threadresponse_set \
                .order_by('created_datetime') \
                .first() \
                .responder
            if creator == request.user or request.user.has_perm(
                    'forumapp.can_delete_any_thread'
            ):
                thread.delete()
            else:
                return HttpResponseForbidden(
                    "You are not allowed to remove this thread."
                )
            return HttpResponseRedirect(
                reverse('forum', kwargs={'pk': fpk})
            )
    else:
        form = ThreadDeleteForm()
        return render(
            request,
            'forumapp/thread_delete.html',
            context={
                'form': form
            }
        )


def enumerate_posts(thread_pk):
    responses = Thread.objects.get(
        id=thread_pk
    ).threadresponse_set.all().order_by(
        'created_datetime'
    )

    for i, response in enumerate(responses):
        response.order_in_thread = i + 1
        response.save()


@login_required
def delete_post(request, fpk, tpk, ppk):
    """
    :param request:
    :param fpk: forum primary key
    :param tpk: thread primary key
    :param ppk: post primary key
    """
    form = ThreadResponseDeleteForm()
    if request.method == "POST":
        form = ThreadResponseDeleteForm(request.POST)
        if form.is_valid():
            response = ThreadResponse.objects.get(id=ppk)
            first_thread_response = ThreadResponse.objects.filter(
                thread=response.thread
            ).order_by('created_datetime')[0]

            if first_thread_response == response:
                return HttpResponseForbidden(
                    "Can't delete the first response!"
                )

            if request.user == response.responder or \
                    request.user.has_perm('forumapp.can_remove_any_response'):
                response.delete()
            else:
                return HttpResponseForbidden(
                    "You are not allowed to delete this post.")

            enumerate_posts(tpk)

            return HttpResponseRedirect(
                reverse(
                    'thread-view',
                    kwargs={
                        'fpk': fpk,
                        'tpk': tpk
                    }
                )
            )

    return render(
        request,
        'forumapp/response_delete.html',
        context={
            'form': form
        }
    )


@login_required
def edit_post(request, fpk, tpk, ppk):
    if request.method == "POST":
        thread_response = ThreadResponse.objects.get(id=ppk)
        if request.user == thread_response.responder:
            form = ThreadResponseModelForm(request.POST)
            if form.is_valid():
                thread_response.message = form.cleaned_data['message']
                thread_response.edited = True
                thread_response.save()
                return HttpResponseRedirect(
                    reverse(
                        'thread-view',
                        kwargs={
                            'fpk': fpk,
                            'tpk': tpk
                        }
                    )
                )
        else:
            return HttpResponseForbidden(
                "You are not allowed to remove this post."
            )

    else:
        thread_response = ThreadResponse.objects.get(id=ppk)
        form = ThreadResponseModelForm(instance=thread_response)
        return render(
            request,
            'forumapp/threadresponse_form.html',
            context={
                'form': form,
                'thread': Thread.objects.get(id=tpk),
                'forum': Forum.objects.get(id=fpk)
            }
        )


def validate_username(request):
    username = request.GET.get('username')
    data = {
        'is_taken': User.objects.filter(username__iexact=username).exists()
    }
    return JsonResponse(data)


def user_view(request, pk):
    viewed_user = User.objects.get(id=pk)
    user_responses = ThreadResponse.objects.filter(
        responder=pk
    ).exclude(thread__isnull=True)

    banned_until = None
    forum_user = ForumUser.objects.get(user=viewed_user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        banned_until = forum_user.banned_until

    can_ban = False
    if request.user.has_perm('forumapp.can_ban_users'):
        can_ban = True

    return render(
        request,
        'forumapp/user_view.html',
        context={
            'viewed_user': viewed_user,
            'user_responses': user_responses,
            'banned_until': banned_until,
            'can_ban': can_ban
        }
    )


@login_required
def new_thread(request, pk):
    forum_user = ForumUser.objects.get(user=request.user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        return HttpResponseForbidden("You are banned! "
                                     "Check your profile for details.")

    if request.method == "POST":
        form_thread = ThreadCreateModelForm(
            request.POST,
            prefix='form_thread'
        )
        if form_thread.is_valid():
            thread_obj = form_thread.save()
            form_response = ThreadResponseModelForm(
                request.POST,
                prefix='form_response',
            )

            if form_response.is_valid():
                obj_response = form_response.save()

                obj_response.thread = thread_obj
                obj_response.responder = request.user
                obj_response.created_datetime = datetime.datetime.now()

                obj_response.save()

                return HttpResponseRedirect(
                    reverse(
                        'thread-view',
                        kwargs={
                            'fpk': thread_obj.forum.id,
                            'tpk': thread_obj.id
                        }
                    )
                )
            else:  # response not valid
                thread_obj.delete()
    else:
        form_thread = ThreadCreateModelForm(prefix='form_thread')
        form_response = ThreadResponseModelForm(prefix='form_response')
        form_thread.initial['forum'] = pk
        return render(
            request,
            'forumapp/thread_form.html',
            context={
                'form_thread': form_thread,
                'form_response': form_response,
                'forum': pk
            }
        )
