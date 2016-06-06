from __future__ import absolute_import

from datetime import timedelta

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from sentry.db.models import FlexibleForeignKey, Model, sane_repr
from sentry.utils.http import absolute_uri


class Email(Model):
    __core__ = True

    user = FlexibleForeignKey(settings.AUTH_USER_MODEL,
                              unique=False,
                              related_name='emails')
    email = models.EmailField(_('email address'))
    validation_hash = models.CharField(max_length=32)
    date_hash_added = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(
        _('verified'), default=False,
        help_text=_('Designates whether this user has confirmed their email.'))

    unique_together = ((user, email),)

    class Meta:
        app_label = 'sentry'
        db_table = 'sentry_email'

    __repr__ = sane_repr('user_id', 'hash')

    def set_hash(self):
        import hashlib
        import random

        self.date_hash_added = timezone.now()
        self.validation_hash = hashlib.md5(str(random.randint(1, 10000000))).hexdigest()

    def hash_is_valid(self):
        return self.validation_hash and self.date_hash_added > timezone.now() - timedelta(hours=48)

    def send_confirm_email(self):
        from sentry import options
        from sentry.utils.email import MessageBuilder

        if not self.hash_is_valid():
            self.set_hash()
            self.save()

        context = {
            'user': self.user,
            'url': absolute_uri(reverse(
                'sentry-account-confirm-email',
                args=[self.user.id, self.validation_hash]
            )),
        }
        msg = MessageBuilder(
            subject='%sConfirm Email' % (options.get('mail.subject-prefix'),),
            template='sentry/emails/confirm_email.txt',
            context=context,
        )
        msg.send_async([self.user.email])
