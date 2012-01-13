import hashlib
import logging
import mimetypes
import re
import types

from django.conf import settings
from django.core.files import File
from django.core.files.uploadhandler import TemporaryFileUploadHandler
import filelike
import magic

LOG = logging.getLogger(__name__)

class AttachmentUploadHandler(TemporaryFileUploadHandler):
    '''
    Calculate checksums on file uploads, scan for viruses (if enabled), and
    try to detect mime types if not specified.
    '''
    def receive_data_chunk(self, raw_data, start):
        self.current_hasher.update(raw_data)
        return super(AttachmentUploadHandler, self).receive_data_chunk(raw_data, start)

    def file_complete(self, file_size):
        ufile = super(AttachmentUploadHandler, self).file_complete(file_size)
        ufile.checksum = self.current_hasher.hexdigest()
    
        # Scan upload for viruses using ClamD
        if settings.CLAM_AV_ENABLED:
            scan_file(ufile.temporary_file_path())

        ufile.content_type = guess_mime(ufile.temporary_file_path(), ufile.name)

        return ufile

    def new_file(self, field_name, file_name, content_type, content_length, charset):
        self.current_hasher = hashlib.md5()
        super(AttachmentUploadHandler, self).new_file(field_name,
                                                      file_name,
                                                      content_type,
                                                      content_length,
                                                      charset)

MIME_PATTERN = re.compile(r'^([^/\s]+/)[^/\s]+$')
MIME_FILE = getattr(settings, 'MIME_FILE', None)
if MIME_FILE:
    mimetypes.init([MIME_FILE])
MAGIC = magic.Magic(mime=True)

def guess_mime(file_, name=None):
    '''
    Try to guess the mimetype of the filepath or filelike object, first by
    extension (with the built-in mimetypes module), then by magic bytes (with
    python-magic, the libmagic python bindings).

    Warning: this function consumes a portion of any filelike stream it is 
    passed.  If your filelike doesn't support seek() and you will need to reset
    it later, you should buffer it with something like filelike.wrappers.Buffer
    before calling this function.
    '''
    filename = getattr(file_, 'name', name) or ''
    mime, encoding = mimetypes.guess_type(filename, strict=False)
    if mime and mime != 'application/octet-stream':
        return mime
    else:
        if type(file_) in types.StringTypes:
            mime = MAGIC.from_file(file_)
        else:
            mime = MAGIC.from_buffer(file_.read(1024))

        return mime if MIME_PATTERN.match(mime) else 'application/octet-stream'

class AttachmentFlaggedAsVirusError(Exception):
    def __init__(self, scanned_file, scan_result):
        self.filepath = scanned_file
        self.scanresult = scan_result

def scan_file(file_):
    '''
    Runs a ClamAV virus scan on the given filepath or filelike object, raising 
    an exception if a virus is detected.
    '''
    import pyclamdplus

    # Identify the input parameter, copying 
    if type(file_) in types.StringTypes:  
        filepath = file_
    else:  # assume filelike
        if os.path.isfile(getattr(file_, 'name', '')):
            filepath = file_.name
        else:  # write buffer to a temp file
            tmpfd, tmpfilepath = tempfile.mkstemp()
            with os.fdopen(tmpfd, 'wb') as tmpout:
                for chunk in chunk_input_stream(file_):
                    tmpout.write(chunk)
            filepath = tmpfilepath

    av_socket = settings.CLAM_AV_SOCKET
    av_conn = pyclamdplus.ClamdUNIXConnection(filename=av_socket)
    scan_result = av_conn.scan_file(filepath)
    
    if scan_result:
        raise AttachmentFlaggedAsVirusError(filepath, scan_result)

def create_from_file(file_, name=None, scan=False):
    '''
    Creates a django.core.files.base.File instance from a filepath or filelike
    object, optionally performing a virus scan on it.  The created File object
    will have the following additional properties:
      checksum -- the file's computed MD5 checksum
      content_type -- MIME type guessed from file extension and magic bytes

    Parameters:
      file_ -- File path or filelike object to create the File from.  This 
              function requires a seekable filelike object, so if one is
              provided that doesn't support seek(), it will be automatically
              wrapped in a buffering object.  For best result, provide an
              object that supports seek().
      name -- Original filename of the provided file.  If a file path is 
              provided, os.path.basename(path) will take precedence.
      scan -- Boolean, whether or not to scan for viruses.
    '''
    # Identify input file object and normalize to create fileobj
    if type(file_) in types.StringTypes:
        fileobj = open(file_, 'rb')
    else:
        seek = getattr(file_, 'seek', None)
        if not type(seek) is types.MethodType:
            fileobj = filelike.wrappers.Buffer(file_)
        else:
            fileobj = file_

    # Scan upload for viruses using ClamD
    if scan and settings.CLAM_AV_ENABLED:
        scan_file(fileobj)

    # Calculate file's md5 sum
    fileobj.seek(0)
    md5 = hashlib.md5()
    for chunk in chunk_input_stream(fileobj):
        md5.update(chunk)
    checksum = md5.hexdigest()

    # Guess content type
    fileobj.seek(0)
    content_type = guess_mime(fileobj, name)

    # Construct File object result
    fileobj.seek(0)
    ufile = File(fileobj, name=name)
    ufile.checksum = checksum
    ufile.content_type = content_type
    return ufile

def chunk_input_stream(input_stream, buffer_size=2**16):
    '''
    Generator method yielding chunks of data read from @input_stream.  Each 
    chunk will be no larger than @buffer_size.
    '''
    while True:
        chunk = input_stream.read(buffer_size)
        if len(chunk) == 0:
            break
        yield chunk
