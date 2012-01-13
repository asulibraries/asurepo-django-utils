import os
import errno

from django.conf import settings
from django.core.files import storage, locks
from django.core.files.move import file_move_safe


class HashedFileSystemStorage(storage.FileSystemStorage):
    '''
    Storage class supporting a hashed file system in which files with identical
    names are considered to be identical.  The following changes are made to
    the base FileSystemStorage behavior:

     + get_available_name() does not alter the name (content hash) it is passed

     + save() only writes new content if exists() returns False.  Otherwise,
       it is assumed that no write is necessary, since the content already
       exists.

    '''
    
    def __init__(self, location=None, base_url=None):
        '''
        Do nothing here - override default behavior in favor of providing
        location and base_url as properties reading directly from settings.
        This is limiting in that location and base_url can only be provided by
        the settings module, but this is our normal use case and it seems to be
        the only way to effectively test our models with FileFields that use
        this storage.
        '''
        pass
    
    @property
    def location(self):
        return settings.MEDIA_ROOT

    @property
    def base_url(self):
        return settings.MEDIA_URL

    def get_available_name(self, name):
        return name

    def save(self, name, content):
        if name is None:
            raise ValueError('HashedFileSystemStorage.save() must be provided with a name')
        return super(HashedFileSystemStorage, self).save(name, content)

    def _save(self, name, content):
        '''
        Copied from super and lightly modified - Unfortunately, the default 
        race condition handling will lead to an infinite loop here, since 
        get_available_name() doesn't return unique names for identical hashes.
        '''
        full_path = self.path(name)
        if os.path.exists(full_path):
            return name

        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            # handle concurrency issue where the directory is created while
            # by another thread after the call to exists()
            try:
                os.makedirs(directory)
            except OSError as e:
                # ignore EEXIST, since it means that our goal here was already
                # accomplished
                if e.errno != errno.EEXIST:
                    raise
        elif not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)
        
        # There's a potential race condition when saving the file; it's 
        # possible that two threads might try to write the file simultaneously.
        # We need to try to create the file, but abort if we detect that it
        # already exists (in which case we assume that another thread is
        # writing it).
        try:
            # This file has a file path that we can move. 
            if hasattr(content, 'temporary_file_path'):
                file_move_safe(content.temporary_file_path(), full_path)
                content.close()

            # This is a normal uploadedfile that we can stream.
            else:
                # This fun binary flag incantation makes os.open throw an 
                # OSError if the file already exists before we open it.
                fd = os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0))
                try:
                    locks.lock(fd, locks.LOCK_EX)
                    for chunk in content.chunks():
                        os.write(fd, chunk)
                finally:
                    locks.unlock(fd)
                    os.close(fd)
        except OSError, e:
            # abort and continue normally if we detect the existence of the 
            # file we're trying to write, otherwise raise normally
            if e.errno != errno.EEXIST:
                raise

        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

        return name
