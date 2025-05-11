import logging

from asgiref.sync import sync_to_async

from django.contrib.sessions.backends.base import CreateError, SessionBase, UpdateError
from django.core.exceptions import SuspiciousOperation
from django.db import DatabaseError, IntegrityError, router, transaction
from django.utils import timezone
from django.utils.functional import cached_property


class SessionStore(SessionBase):
    """
    Implement database session store.
    """

    def __init__(self, session_key=None):
        super().__init__(session_key)

    @classmethod
    def get_model_class(cls):
        # Avoids a circular import and allows importing SessionStore when
        # django.contrib.sessions is not in INSTALLED_APPS.
        from django.contrib.sessions.models import Session

        return Session

    @cached_property
    def model(self):
        return self.get_model_class()

    def _get_session_from_db(self):
        """
        Retrieve a session from the database based on the session key if it has not expired.

        Raises an exception if the session does not exist or is suspected to be compromised. 
        If the operation is deemed suspicious, a warning is logged before clearing the session key.
        """
        try:
            return self.model.objects.get(
                session_key=self.session_key, expire_date__gt=timezone.now()
            )
        except (self.model.DoesNotExist, SuspiciousOperation) as e:
            if isinstance(e, SuspiciousOperation):
                logger = logging.getLogger("django.security.%s" % e.__class__.__name__)
                logger.warning(str(e))
            self._session_key = None

    async def _aget_session_from_db(self):
        """
        Retrieves a session from the database using the provided session key, 
        checking for session expiration and handling potential security exceptions.
        """
        try:
            return await self.model.objects.aget(
                session_key=self.session_key, expire_date__gt=timezone.now()
            )
        except (self.model.DoesNotExist, SuspiciousOperation) as e:
            if isinstance(e, SuspiciousOperation):
                logger = logging.getLogger("django.security.%s" % e.__class__.__name__)
                logger.warning(str(e))
            self._session_key = None

    def load(self):
        s = self._get_session_from_db()
        return self.decode(s.session_data) if s else {}

    async def aload(self):
        s = await self._aget_session_from_db()
        return self.decode(s.session_data) if s else {}

    def exists(self, session_key):
        return self.model.objects.filter(session_key=session_key).exists()

    async def aexists(self, session_key):
        return await self.model.objects.filter(session_key=session_key).aexists()

    def create(self):
        """
        Creates a new session by generating a unique session key and saving it to the database, retrying if a duplicate key is encountered.
        """
        while True:
            self._session_key = self._get_new_session_key()
            try:
                # Save immediately to ensure we have a unique entry in the
                # database.
                self.save(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            return

    async def acreate(self):
        """
        Create a new session asynchronously, retrying until successful.

        This method generates a new session key and attempts to save the session.
        If the save fails due to a creation error, it will retry with a new session key.
        Once the session is successfully created, it sets the modified flag to True and returns.
        """
        while True:
            self._session_key = await self._aget_new_session_key()
            try:
                # Save immediately to ensure we have a unique entry in the
                # database.
                await self.asave(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            return

    def create_model_instance(self, data):
        """
        Return a new instance of the session model object, which represents the
        current session state. Intended to be used for saving the session data
        to the database.
        """
        return self.model(
            session_key=self._get_or_create_session_key(),
            session_data=self.encode(data),
            expire_date=self.get_expiry_date(),
        )

    async def acreate_model_instance(self, data):
        """See create_model_instance()."""
        return self.model(
            session_key=await self._aget_or_create_session_key(),
            session_data=self.encode(data),
            expire_date=await self.aget_expiry_date(),
        )

    def save(self, must_create=False):
        """
        Save the current session data to the database, optionally enforcing creation of a new entry.
        """
        if self.session_key is None:
            return self.create()
        data = self._get_session(no_load=must_create)
        obj = self.create_model_instance(data)
        using = router.db_for_write(self.model, instance=obj)
        try:
            with transaction.atomic(using=using):
                obj.save(
                    force_insert=must_create, force_update=not must_create, using=using
                )
        except IntegrityError:
            if must_create:
                raise CreateError
            raise
        except DatabaseError:
            if not must_create:
                raise UpdateError
            raise

    async def asave(self, must_create=False):
        """
        Asynchronously saves the model instance to the database.

        If the instance does not exist in the database and `must_create` is True, 
        it will be created. If `must_create` is False and the instance does not exist, 
        it will be created instead of raising an error. If the instance already exists 
        and `must_create` is True, a CreateError is raised. If `must_create` is False and 
        the instance exists, it will be updated.

        Raises:
            CreateError: If must_create is True and the instance already exists.
            UpdateError: If must_create is False and the instance does not exist but the update fails.

        """
        if self.session_key is None:
            return await self.acreate()
        data = await self._aget_session(no_load=must_create)
        obj = await self.acreate_model_instance(data)
        using = router.db_for_write(self.model, instance=obj)
        try:
            # This code MOST run in a transaction, so it requires
            # @sync_to_async wrapping until transaction.atomic() supports
            # async.
            @sync_to_async
            def sync_transaction():
                with transaction.atomic(using=using):
                    obj.save(
                        force_insert=must_create,
                        force_update=not must_create,
                        using=using,
                    )

            await sync_transaction()
        except IntegrityError:
            if must_create:
                raise CreateError
            raise
        except DatabaseError:
            if not must_create:
                raise UpdateError
            raise

    def delete(self, session_key=None):
        """
        Deletes a database object associated with the given session key or the object's default session key if none is provided.
        """
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        try:
            self.model.objects.get(session_key=session_key).delete()
        except self.model.DoesNotExist:
            pass

    async def adelete(self, session_key=None):
        """

        Deletes an object from the database asynchronously.

        This method retrieves an object from the database using the provided session key 
        (or the instance's session key if none is provided) and then deletes it. If the 
        object does not exist, the operation is silently ignored.

        """
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        try:
            obj = await self.model.objects.aget(session_key=session_key)
            await obj.adelete()
        except self.model.DoesNotExist:
            pass

    @classmethod
    def clear_expired(cls):
        cls.get_model_class().objects.filter(expire_date__lt=timezone.now()).delete()

    @classmethod
    async def aclear_expired(cls):
        await cls.get_model_class().objects.filter(
            expire_date__lt=timezone.now()
        ).adelete()
