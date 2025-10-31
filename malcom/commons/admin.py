import logging
from typing import TypeVar

from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.db.models import Model
from django.forms import BaseFormSet, Form
from django.http import HttpRequest

logger = logging.getLogger(__name__)

ModelInstance = TypeVar("ModelInstance", bound=Model)


class AutoPopulateUserCreatedFieldsMixIn:
    """
    Expects the following fields in model and related inline models for expected updates to take place:
    - created_by
    - updated_by
    - created_datetime

    Assigns request.user to model.created_by/model.updated_by on save/update.
    Assigns request.user to inline_model.created_by/inline_model.updated_by
    """

    def save_model(self, request: HttpRequest, obj: ModelInstance, form: Form, change: bool) -> None:
        has_created_by = any(True for f in obj._meta.get_fields() if f.name == "created_by")
        if obj._state.adding and has_created_by:
            obj.created_by = request.user
        has_updated_by = any(True for f in obj._meta.get_fields() if f.name == "updated_by")
        if has_updated_by:
            obj.updated_by = request.user

        obj.save()

    def save_formset(self, request: HttpRequest, form: Form, formset: BaseFormSet, change: bool) -> None:
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()

        formset_save_errors = []
        for instance in instances:
            has_created_by = any(True for f in instance._meta.get_fields() if f.name == "created_by")
            if instance._state.adding and has_created_by:
                instance.created_by = request.user  # only update created_by once!
            has_updated_by = any(True for f in instance._meta.get_fields() if f.name == "updated_by")
            if has_updated_by:
                instance.updated_by = request.user
            try:
                instance.save()
            except ValueError as e:
                logger.exception(f"can't save formset instances: {e.args}")
                formset_save_errors.append(", ".join(e.args))

        if not formset_save_errors:
            formset.save_m2m()
        else:
            logger.warning(f"errors occured, formset.save_m2m(): {formset_save_errors}")
            errors_display = ", ".join(formset_save_errors)
            message = f"保存ができません: {errors_display}"
            self.message_user(request, message, level=messages.ERROR)


class UserCreatedBaseModelAdmin(AutoPopulateUserCreatedFieldsMixIn, admin.ModelAdmin):
    pass


admin.site.unregister(Group)  # remove Group from admin
