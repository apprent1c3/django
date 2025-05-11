import mimetypes
from collections import namedtuple
from email import charset as Charset
from email import encoders as Encoders
from email import generator, message_from_string
from email.errors import HeaderParseError
from email.header import Header
from email.headerregistry import Address, parser
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, getaddresses, make_msgid
from io import BytesIO, StringIO
from pathlib import Path

from django.conf import settings
from django.core.mail.utils import DNS_NAME
from django.utils.encoding import force_str, punycode

# Don't BASE64-encode UTF-8 messages so that we avoid unwanted attention from
# some spam filters.
utf8_charset = Charset.Charset("utf-8")
utf8_charset.body_encoding = None  # Python defaults to BASE64
utf8_charset_qp = Charset.Charset("utf-8")
utf8_charset_qp.body_encoding = Charset.QP

# Default MIME type to use on attachments (if it is not explicitly given
# and cannot be guessed).
DEFAULT_ATTACHMENT_MIME_TYPE = "application/octet-stream"

RFC5322_EMAIL_LINE_LENGTH_LIMIT = 998


class BadHeaderError(ValueError):
    pass


# Header names that contain structured address data (RFC 5322).
ADDRESS_HEADERS = {
    "from",
    "sender",
    "reply-to",
    "to",
    "cc",
    "bcc",
    "resent-from",
    "resent-sender",
    "resent-to",
    "resent-cc",
    "resent-bcc",
}


def forbid_multi_line_headers(name, val, encoding):
    """
    Validate and sanitize HTTP header values to prevent header injection attacks, ensuring they do not contain newline characters and are properly encoded.
    """
    encoding = encoding or settings.DEFAULT_CHARSET
    val = str(val)  # val may be lazy
    if "\n" in val or "\r" in val:
        raise BadHeaderError(
            "Header values can't contain newlines (got %r for header %r)" % (val, name)
        )
    try:
        val.encode("ascii")
    except UnicodeEncodeError:
        if name.lower() in ADDRESS_HEADERS:
            val = ", ".join(
                sanitize_address(addr, encoding) for addr in getaddresses((val,))
            )
        else:
            val = Header(val, encoding).encode()
    else:
        if name.lower() == "subject":
            val = Header(val).encode()
    return name, val


def sanitize_address(addr, encoding):
    """
    Sanitizes and formats an address string, which can be either an email address or a tuple containing a name and an address, into a standardized format. 
    The function checks for valid address structure, encodes non-ASCII characters, and handles potential encoding errors, ultimately returning a formatted address string.
    """
    address = None
    if not isinstance(addr, tuple):
        addr = force_str(addr)
        try:
            token, rest = parser.get_mailbox(addr)
        except (HeaderParseError, ValueError, IndexError):
            raise ValueError('Invalid address "%s"' % addr)
        else:
            if rest:
                # The entire email address must be parsed.
                raise ValueError(
                    'Invalid address; only %s could be parsed from "%s"' % (token, addr)
                )
            nm = token.display_name or ""
            localpart = token.local_part
            domain = token.domain or ""
    else:
        nm, address = addr
        if "@" not in address:
            raise ValueError(f'Invalid address "{address}"')
        localpart, domain = address.rsplit("@", 1)

    address_parts = nm + localpart + domain
    if "\n" in address_parts or "\r" in address_parts:
        raise ValueError("Invalid address; address parts cannot contain newlines.")

    # Avoid UTF-8 encode, if it's possible.
    try:
        nm.encode("ascii")
        nm = Header(nm).encode()
    except UnicodeEncodeError:
        nm = Header(nm, encoding).encode()
    try:
        localpart.encode("ascii")
    except UnicodeEncodeError:
        localpart = Header(localpart, encoding).encode()
    domain = punycode(domain)

    parsed_address = Address(username=localpart, domain=domain)
    return formataddr((nm, parsed_address.addr_spec))


class MIMEMixin:
    def as_string(self, unixfrom=False, linesep="\n"):
        """
        Return the entire formatted message as a string.

        Parameters
        ----------
        unixfrom : bool, optional
            Include the Unix From_ envelope header if True.
        linesep : str, optional
            Line separator to use (default is newline).

        The returned string preserves lines starting with 'From ' to prevent mangling.

        """
        fp = StringIO()
        g = generator.Generator(fp, mangle_from_=False)
        g.flatten(self, unixfrom=unixfrom, linesep=linesep)
        return fp.getvalue()

    def as_bytes(self, unixfrom=False, linesep="\n"):
        """
        Return the entire formatted message as bytes.

            :param bool unixfrom: Include the Unix From_ envelope header when True.
            :param str linesep: Line separator to use (default is '\\n').

            Generates the message with the specified options, preserving lines starting with 'From '. 

        """
        fp = BytesIO()
        g = generator.BytesGenerator(fp, mangle_from_=False)
        g.flatten(self, unixfrom=unixfrom, linesep=linesep)
        return fp.getvalue()


class SafeMIMEMessage(MIMEMixin, MIMEMessage):
    def __setitem__(self, name, val):
        # message/rfc822 attachments must be ASCII
        name, val = forbid_multi_line_headers(name, val, "ascii")
        MIMEMessage.__setitem__(self, name, val)


class SafeMIMEText(MIMEMixin, MIMEText):
    def __init__(self, _text, _subtype="plain", _charset=None):
        self.encoding = _charset
        MIMEText.__init__(self, _text, _subtype=_subtype, _charset=_charset)

    def __setitem__(self, name, val):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEText.__setitem__(self, name, val)

    def set_payload(self, payload, charset=None):
        if charset == "utf-8" and not isinstance(charset, Charset.Charset):
            has_long_lines = any(
                len(line.encode(errors="surrogateescape"))
                > RFC5322_EMAIL_LINE_LENGTH_LIMIT
                for line in payload.splitlines()
            )
            # Quoted-Printable encoding has the side effect of shortening long
            # lines, if any (#22561).
            charset = utf8_charset_qp if has_long_lines else utf8_charset
        MIMEText.set_payload(self, payload, charset=charset)


class SafeMIMEMultipart(MIMEMixin, MIMEMultipart):
    def __init__(
        self, _subtype="mixed", boundary=None, _subparts=None, encoding=None, **_params
    ):
        self.encoding = encoding
        MIMEMultipart.__init__(self, _subtype, boundary, _subparts, **_params)

    def __setitem__(self, name, val):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEMultipart.__setitem__(self, name, val)


Alternative = namedtuple("Alternative", ["content", "mimetype"])
EmailAttachment = namedtuple("Attachment", ["filename", "content", "mimetype"])


class EmailMessage:
    """A container for email information."""

    content_subtype = "plain"
    mixed_subtype = "mixed"
    encoding = None  # None => use settings default

    def __init__(
        self,
        subject="",
        body="",
        from_email=None,
        to=None,
        bcc=None,
        connection=None,
        attachments=None,
        headers=None,
        cc=None,
        reply_to=None,
    ):
        """
        Initialize an email message, defining its recipients, content, and optional parameters such as attachments and custom headers.
        """
        if to:
            if isinstance(to, str):
                raise TypeError('"to" argument must be a list or tuple')
            self.to = list(to)
        else:
            self.to = []
        if cc:
            if isinstance(cc, str):
                raise TypeError('"cc" argument must be a list or tuple')
            self.cc = list(cc)
        else:
            self.cc = []
        if bcc:
            if isinstance(bcc, str):
                raise TypeError('"bcc" argument must be a list or tuple')
            self.bcc = list(bcc)
        else:
            self.bcc = []
        if reply_to:
            if isinstance(reply_to, str):
                raise TypeError('"reply_to" argument must be a list or tuple')
            self.reply_to = list(reply_to)
        else:
            self.reply_to = []
        self.from_email = from_email or settings.DEFAULT_FROM_EMAIL
        self.subject = subject
        self.body = body or ""
        self.attachments = []
        if attachments:
            for attachment in attachments:
                if isinstance(attachment, MIMEBase):
                    self.attach(attachment)
                else:
                    self.attach(*attachment)
        self.extra_headers = headers or {}
        self.connection = connection

    def get_connection(self, fail_silently=False):
        from django.core.mail import get_connection

        if not self.connection:
            self.connection = get_connection(fail_silently=fail_silently)
        return self.connection

    def message(self):
        """
        -message(self)
                Creates a formatted email message with the specified subject, from address, 
                recipient addresses, and message body, while also handling additional 
                headers and date/time settings as necessary.
        """
        encoding = self.encoding or settings.DEFAULT_CHARSET
        msg = SafeMIMEText(self.body, self.content_subtype, encoding)
        msg = self._create_message(msg)
        msg["Subject"] = self.subject
        msg["From"] = self.extra_headers.get("From", self.from_email)
        self._set_list_header_if_not_empty(msg, "To", self.to)
        self._set_list_header_if_not_empty(msg, "Cc", self.cc)
        self._set_list_header_if_not_empty(msg, "Reply-To", self.reply_to)

        # Email header names are case-insensitive (RFC 2045), so we have to
        # accommodate that when doing comparisons.
        header_names = [key.lower() for key in self.extra_headers]
        if "date" not in header_names:
            # formatdate() uses stdlib methods to format the date, which use
            # the stdlib/OS concept of a timezone, however, Django sets the
            # TZ environment variable based on the TIME_ZONE setting which
            # will get picked up by formatdate().
            msg["Date"] = formatdate(localtime=settings.EMAIL_USE_LOCALTIME)
        if "message-id" not in header_names:
            # Use cached DNS_NAME for performance
            msg["Message-ID"] = make_msgid(domain=DNS_NAME)
        for name, value in self.extra_headers.items():
            # Avoid headers handled above.
            if name.lower() not in {"from", "to", "cc", "reply-to"}:
                msg[name] = value
        return msg

    def recipients(self):
        """
        Return a list of all recipients of the email (includes direct
        addressees as well as Cc and Bcc entries).
        """
        return [email for email in (self.to + self.cc + self.bcc) if email]

    def send(self, fail_silently=False):
        """Send the email message."""
        if not self.recipients():
            # Don't bother creating the network connection if there's nobody to
            # send to.
            return 0
        return self.get_connection(fail_silently).send_messages([self])

    def attach(self, filename=None, content=None, mimetype=None):
        """
        Attach a file to an email with optional filename, content, and MIME type.

         The function either attaches a MIMEBase object directly or creates a new
         attachment with guessed or specified MIME type. Text content is decoded as
         UTF-8 if possible, otherwise a default MIME type is used.
        """
        if isinstance(filename, MIMEBase):
            if content is not None or mimetype is not None:
                raise ValueError(
                    "content and mimetype must not be given when a MIMEBase "
                    "instance is provided."
                )
            self.attachments.append(filename)
        elif content is None:
            raise ValueError("content must be provided.")
        else:
            mimetype = (
                mimetype
                or mimetypes.guess_type(filename)[0]
                or DEFAULT_ATTACHMENT_MIME_TYPE
            )
            basetype, subtype = mimetype.split("/", 1)

            if basetype == "text":
                if isinstance(content, bytes):
                    try:
                        content = content.decode()
                    except UnicodeDecodeError:
                        # If mimetype suggests the file is text but it's
                        # actually binary, read() raises a UnicodeDecodeError.
                        mimetype = DEFAULT_ATTACHMENT_MIME_TYPE

            self.attachments.append(EmailAttachment(filename, content, mimetype))

    def attach_file(self, path, mimetype=None):
        """
        Attach a file from the local filesystem to the current object, automatically detecting the file's mimetype if not specified.
        """
        path = Path(path)
        with path.open("rb") as file:
            content = file.read()
            self.attach(path.name, content, mimetype)

    def _create_message(self, msg):
        return self._create_attachments(msg)

    def _create_attachments(self, msg):
        """
        Create a multipart message with attachments.

        Adds attachments from the list to the provided message, handling both MIMEBase 
        instances and attachment data to be constructed into MIMEBase instances. 
        The message encoding is set according to the specified or default charset.

        Returns the resulting multipart message with attachments included.
        """
        if self.attachments:
            encoding = self.encoding or settings.DEFAULT_CHARSET
            body_msg = msg
            msg = SafeMIMEMultipart(_subtype=self.mixed_subtype, encoding=encoding)
            if self.body or body_msg.is_multipart():
                msg.attach(body_msg)
            for attachment in self.attachments:
                if isinstance(attachment, MIMEBase):
                    msg.attach(attachment)
                else:
                    msg.attach(self._create_attachment(*attachment))
        return msg

    def _create_mime_attachment(self, content, mimetype):
        """
        Converts a given content string and MIME type into a MIME attachment object, handling different content types such as text, message/rfc822, and others, and applying necessary encoding and payload settings accordingly.
        """
        basetype, subtype = mimetype.split("/", 1)
        if basetype == "text":
            encoding = self.encoding or settings.DEFAULT_CHARSET
            attachment = SafeMIMEText(content, subtype, encoding)
        elif basetype == "message" and subtype == "rfc822":
            # Bug #18967: Per RFC 2046 Section 5.2.1, message/rfc822
            # attachments must not be base64 encoded.
            if isinstance(content, EmailMessage):
                # convert content into an email.Message first
                content = content.message()
            elif not isinstance(content, Message):
                # For compatibility with existing code, parse the message
                # into an email.Message object if it is not one already.
                content = message_from_string(force_str(content))

            attachment = SafeMIMEMessage(content, subtype)
        else:
            # Encode non-text attachments with base64.
            attachment = MIMEBase(basetype, subtype)
            attachment.set_payload(content)
            Encoders.encode_base64(attachment)
        return attachment

    def _create_attachment(self, filename, content, mimetype=None):
        """
        Converts a file's metadata and content into a MIME attachment object, suitable for inclusion in an email or other message, with optional support for non-ASCII filenames.
        """
        attachment = self._create_mime_attachment(content, mimetype)
        if filename:
            try:
                filename.encode("ascii")
            except UnicodeEncodeError:
                filename = ("utf-8", "", filename)
            attachment.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
        return attachment

    def _set_list_header_if_not_empty(self, msg, header, values):
        """
        Sets a message header with a value from self.extra_headers or a comma-separated string of values if the header is not preset and values are provided.
        """
        try:
            msg[header] = self.extra_headers[header]
        except KeyError:
            if values:
                msg[header] = ", ".join(str(v) for v in values)


class EmailMultiAlternatives(EmailMessage):
    """
    A version of EmailMessage that makes it easy to send multipart/alternative
    messages. For example, including text and HTML versions of the text is
    made easier.
    """

    alternative_subtype = "alternative"

    def __init__(
        self,
        subject="",
        body="",
        from_email=None,
        to=None,
        bcc=None,
        connection=None,
        attachments=None,
        headers=None,
        alternatives=None,
        cc=None,
        reply_to=None,
    ):
        """
        Initialize a single email message (which can be sent to multiple
        recipients).
        """
        super().__init__(
            subject,
            body,
            from_email,
            to,
            bcc,
            connection,
            attachments,
            headers,
            cc,
            reply_to,
        )
        self.alternatives = [
            Alternative(*alternative) for alternative in (alternatives or [])
        ]

    def attach_alternative(self, content, mimetype):
        """Attach an alternative content representation."""
        if content is None or mimetype is None:
            raise ValueError("Both content and mimetype must be provided.")
        self.alternatives.append(Alternative(content, mimetype))

    def _create_message(self, msg):
        return self._create_attachments(self._create_alternatives(msg))

    def _create_alternatives(self, msg):
        """
        Creates an email message with alternative content types.

        If alternative content is provided, a multipart message is created with the
        main body and each alternative attached, allowing email clients to choose
        the best format to display. The message is encoded using the specified or
        default encoding.

        :param msg: The main message body.
        :return: The created message with alternative content attached if applicable.
        """
        encoding = self.encoding or settings.DEFAULT_CHARSET
        if self.alternatives:
            body_msg = msg
            msg = SafeMIMEMultipart(
                _subtype=self.alternative_subtype, encoding=encoding
            )
            if self.body:
                msg.attach(body_msg)
            for alternative in self.alternatives:
                msg.attach(
                    self._create_mime_attachment(
                        alternative.content, alternative.mimetype
                    )
                )
        return msg

    def body_contains(self, text):
        """
        Checks if a given text occurs in the email body and all attached text alternatives.
        """
        if text not in self.body:
            return False

        for content, mimetype in self.alternatives:
            if mimetype.startswith("text/") and text not in content:
                return False
        return True
