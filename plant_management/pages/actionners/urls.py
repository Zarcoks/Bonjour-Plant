from django.urls import path

from . import views

urlpatterns = [
    path("", views.ActionnerList.as_view(), name="actionners"),
    path("create/", views.ActionnerCreate.as_view(), name="create_actionner"),
    path("warnings/", views.ActionnerWarnings.as_view(), name="actionner_warnings"),
    path("<int:actionner_id>/warnings/dismiss/", views.DismissActionnerWarning.as_view(),
         name="dismiss_actionner_warning"),
    path("<int:actionner_id>/", views.ActionnerDetail.as_view(), name="actionner_detail"),
    path("<int:actionner_id>/card/", views.ActionnerCard.as_view(), name="actionner_card"),
    path("<int:actionner_id>/delete/", views.ActionnerDelete.as_view(), name="delete_actionner"),
]
