#!/usr/bin/python3
#
# imap2thehive.py - Poll a IMAP mailbox and create new cases/alerts in TheHive
#
# Author: Xavier Mertens <xavier@rootshell.be>
# Copyright: GPLv3 (http://gplv3.fsf.org)
# Fell free to use the code, but please share the changes you've made
#
# Todo:
# - Configuration validation
# - Support for GnuPG
#

from __future__ import print_function
from __future__ import unicode_literals
import argparse
import configparser
import imaplib
import os,sys
import email
import email.header
import gnupg
import io
import chardet
import time,datetime
import json
import requests
import uuid
import tempfile
import re

try:
    from thehive4py.api import TheHiveApi
    from thehive4py.models import Case, CaseTask, CaseObservable, CustomFieldHelper
    from thehive4py.models import Alert, AlertArtifact
except:
    print("[ERROR] Please install thehive4py.")
    sys.exit(1)

__author__     = "Xavier Mertens"
__license__    = "GPLv3"
__version__    = "1.0.1"
__maintainer__ = "Xavier Mertens"
__email__      = "xavier@rootshell.be"
__name__       = "imap2thehive"

# Default configuration 
args = ''
config = {
    'imapHost'        : '',
    'imapPort'        : 993,
    'imapUser'        : '',
    'imapPassword'    : '',
    'imapFolder'      : '',
    'imapExpunge'     : False,
    'thehiveURL'      : '',
    'thehiveUser'     : '',
    'thehivePassword' : '',
    'caseTLP'         : '',
    'caseTags'        : ['email'],
    'caseTasks'       : [],
    'caseFiles'       : [],
    'caseTemplate'    : '',
    'caseObservables' : False,
    'alertTLP'        : '',
    'alertTags'       : ['email'],
    'alertKeyword'    : '\S*\[ALERT\]\S*'
}

def slugify(s):
    '''
    Sanitize filenames
    Source: https://github.com/django/django/blob/master/django/utils/text.py
    '''
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)

def searchObservables(buffer, observables):
    '''
    Search for observables in the buffer and build a list of found data
    '''
    # Observable types
    # Source: https://github.com/armbues/ioc_parser/blob/master/iocp/data/patterns.ini
    observableTypes = [
         { 'type': 'filename', 'regex': r'\b([A-Za-z0-9-_\.]+\.(exe|dll|bat|sys|htm|html|js|jar|jpg|png|vb|scr|pif|chm|zip|rar|cab|pdf|doc|docx|ppt|pptx|xls|xlsx|swf|gif))\b' },
         { 'type': 'url',      'regex': r'\b([a-z]{3,}\:\/\/[a-z0-9.\-:/?=&;]{16,})\b' },
         { 'type': 'ip',       'regex': r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b' },
         { 'type': 'fqdn',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){2,}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'domain',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){1}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'mail',   'regex': r'\b([a-z][_a-z0-9-.+]+@[a-z0-9-.]+\.[a-z]+)\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{32}|[A-F0-9]{32})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{40}|[A-F0-9]{40})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{64}|[A-F0-9]{64})\b' }
         ]

    for o in observableTypes:
        for match in re.findall(o['regex'], buffer, re.MULTILINE|re.IGNORECASE):
            # Bug: If match is a tuple (example for domain or fqdn), use the 1st element
            if type(match) is tuple:
                match = match[0]

            # Bug: Avoid duplicates!
            if not {'type': o['type'], 'value': match } in observables:
                observables.append({ 'type': o['type'], 'value': match })
                if args.verbose:
                    print('[INFO] Found observable %s: %s' % (o['type'], match))
            else:
                print('[INFO] Ignoring duplicate observable: %s' % match)
    return observables

def mailConnect():
    '''
    Connection to mailserver and handle the IMAP connection
    '''

    try:
        mbox = imaplib.IMAP4_SSL(config['imapHost'], config['imapPort'])
    except:
        typ,val = sys.exc_info()[:2]
        print("[ERROR] Cannot connect to IMAP server %s: %s" % (config['imapHost'],str(val)))
        mbox = None
        return

    try:
        typ,dat = mbox.login(config['imapUser'],config['imapPassword'])
    except:
        typ,dat = sys.exc_info()[:2]

    if typ != 'OK':
        print("[ERROR] Cannot open %s for %s@%s: %s" % (config['imapFolder'], config['imapUser'], config['imapHost'], str(dat)))
        mbox = None
        return

    if args.verbose:
        print('[INFO] Connected to IMAP server.')

    return mbox

def submitTheHive(message):

    '''
    Create a new case in TheHive based on the email
    Return 'TRUE' is successfully processed otherwise 'FALSE'
    '''

    # Decode email
    msg = email.message_from_bytes(message)
    decode = email.header.decode_header(msg['From'])[0]
    fromField = str(decode[0])
    decode = email.header.decode_header(msg['Subject'])[0]
    subjectField = str(decode[0])
    if args.verbose:
        print("[INFO] From: %s Subject: %s" % (fromField, subjectField))
    attachments = []
    observables = []
    body = ''
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode()
            observables = searchObservables(body, observables)
        elif part.get_content_type() == "text/html":
            if args.verbose:
                print("[INFO] Searching for observable in HTML code")
            html = part.get_payload(decode=True).decode()
            observables = searchObservables(html, observables)
        else:
            # Extract MIME parts
            filename = part.get_filename()
            mimetype = part.get_content_type()
            if filename and mimetype:
                if mimetype in config['caseFiles'] or not config['caseFiles']:
                    print("[INFO] Found attachment: %s (%s)" % (filename, mimetype))
                    # Decode the attachment and save it in a temporary file
                    charset = part.get_content_charset()
                    if charset is None:
                        charset = chardet.detect(bytes(part))['encoding']
                    fd, path = tempfile.mkstemp(prefix=slugify(filename) + "_")
                    try:
                        with os.fdopen(fd, 'w+b') as tmp:
                            tmp.write(part.get_payload(decode=1))
                        attachments.append(path)
                    except OSError as e:
                        print("[ERROR] Cannot dump attachment to %s: %s" % (path,e.errno))
                        return False

    api = TheHiveApi(config['thehiveURL'], config['thehiveUser'], config['thehivePassword'], {'http': '', 'https': ''})

    # if '[ALERT]' in subjectField:
    if re.match(config['alertKeywords'], subjectField, flags=0):
        # Prepare the alert
        sourceRef = str(uuid.uuid4())[0:6]
        alert = Alert(title=subjectField.replace('[ALERT]', ''),
                      tlp = int(config['alertTLP']),
                      tags = config['alertTags'],
                      description=body,
                      type='external',
                      source=fromField,
                      sourceRef=sourceRef)

        # Create the Alert
        id = None
        response = api.create_alert(alert)
        if response.status_code == 201:
            if args.verbose:
                print('[INFO] Created alert %s' % response.json()['sourceRef'])
        else:
            print('[ERROR] Cannot create alert: %s (%s)' % (response.status_code, response.text))
            return False

    else:
        # Prepare the sample case
        tasks = []
        for task in config['caseTasks']:
             tasks.append(CaseTask(title=task))

        # Prepare the custom fields
        customFields = CustomFieldHelper()\
            .add_string('from', fromField)\
            .add_string('attachment', str(attachments))\
            .build()

        # If a case template is specified, use it instead of the tasks
        if len(config['caseTemplate']) > 0:
            case = Case(title=subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        template     = config['caseTemplate'],
                        customFields = customFields)
        else:
            case = Case(title        = subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        tasks        = tasks,
                        customFields = customFields)

        # Create the case
        id = None
        response = api.create_case(case)
        if response.status_code == 201:
            newID = response.json()['id']
            if args.verbose:
                print('[INFO] Created case %s' % response.json()['caseId'])
            if len(attachments) > 0:
                for path in attachments:
                   observable = CaseObservable(dataType='file',
                        data    = [path],
                        tlp     = int(config['caseTLP']),
                        ioc     = False,
                        tags    = config['caseTags'],
                        message = 'Found as email attachment'
                        )
                   response = api.create_case_observable(newID, observable)
                   if response.status_code == 201:
                       if args.verbose:
                           print('[INFO] Added observable %s to case ID %s' % (path, newID))
                           os.unlink(path)
                   else:
                       print('[WARNING] Cannot add observable: %s - %s (%s)' % (path, response.status_code, response.text))
            #
            # Add observables found in the mail body
            #
            if config['caseObservables'] and len(observables) > 0:
                for o in observables:
                    observable = CaseObservable(
                        dataType = o['type'],
                        data     = o['value'],
                        tlp      = int(config['caseTLP']),
                        ioc      = False,
                        tags     = config['caseTags'],
                        message  = 'Found in the email body'
                        )
                    response = api.create_case_observable(newID, observable)
                    if response.status_code == 201:
                        if args.verbose:
                            print('[INFO] Added observable %s: %s to case ID %s' % (o['type'], o['value'], newID))
                    else:
                         print('[WARNING] Cannot add observable %s: %s - %s (%s)' % (o['type'], o['value'], response.status_code, response.text))
        else:
            print('[ERROR] Cannot create case: %s (%s)' % (response.status_code, response.text))
            return False
    return True

def readMail(mbox):
    '''
    Search for unread email in the specific folder
    '''

    if not mbox:
        return

    mbox.select(config['imapFolder'])
    # DEBUG typ, dat = mbox.search(None, '(ALL)')
    typ, dat = mbox.search(None, '(UNSEEN)')
    newEmails = len(dat[0].split())
    if args.verbose:
        print("[INFO] %d unread messages to process" % newEmails)
    for num in dat[0].split():
        typ, dat = mbox.fetch(num, '(RFC822)')
        if typ != 'OK':
            error(dat[-1])
        message = dat[0][1]
        if submitTheHive(message) == True:
            # If message successfully processed, flag it as 'Deleted' otherwise restore the 'Unread' status
            if config['imapExpunge']:
                mbox.store(num, '+FLAGS', '\\Deleted')
                if args.verbose:
                    print("[INFO] Message %d successfully processed and deleted" % int(num))
            else:
                if args.verbose:
                    print("[INFO] Message %d successfully processed and flagged as read" % int(num))
        else:
            mbox.store(num, '-FLAGS', '\\Seen')
            print("[WARNING] Message %d not processed and flagged as unread" % int(num))
    mbox.expunge() 
    return newEmails

def main():
    global args
    global config

    parser = argparse.ArgumentParser(
        description = 'Process an IMAP folder to create TheHive alerts/cased.')
    parser.add_argument('-v', '--verbose',
        action = 'store_true',
        dest = 'verbose',
        help = 'verbose output',
        default = False)
    parser.add_argument('-c', '--config',
        dest = 'configFile',
        help = 'configuration file (default: /etc/imap2thehive.conf)',
        metavar = 'CONFIG')
    args = parser.parse_args()

    # Default values
    if not args.configFile:
        args.configFile = '/etc/imap2thehive.conf'
    if not args.verbose:
        args.verbose = False

    if not os.path.isfile(args.configFile):
        print('[ERROR] Configuration file %s is not readable.' % args.configFile)
        sys.exit(1);

    try:
        c = configparser.ConfigParser()
        c.read(args.configFile)
    except OSError as e:
        print('[ERROR] Cannot read config file %s: %s' % (args.configFile, e.errno))
        sys.exit(1)

    # IMAP Config
    config['imapHost']          = c.get('imap', 'host')
    if c.has_option('imap', 'port'):
        config['imapPort']          = int(c.get('imap', 'port'))
    config['imapUser']          = c.get('imap', 'user')
    config['imapPassword']      = c.get('imap', 'password')
    config['imapFolder']        = c.get('imap', 'folder')
    if c.has_option('imap', 'expunge'):
        value = c.get('imap', 'expunge')
        if value == '1' or value == 'true' or value == 'yes':
             config['imapExpunge']   = True

    # TheHive Config
    config['thehiveURL']        = c.get('thehive', 'url')
    config['thehiveUser']       = c.get('thehive', 'user')
    config['thehivePassword']   = c.get('thehive', 'password')

    # New case config
    config['caseTLP']           = c.get('case', 'tlp')
    config['caseTags']          = c.get('case', 'tags').split(',')
    if c.has_option('case', 'tasks'):
        config['caseTasks']     = c.get('case', 'tasks').split(',')
    if c.has_option('case', 'template'):
        config['caseTemplate']  = c.get('case', 'template')
    if c.has_option('case', 'files'):
        config['caseFiles']     = c.get('case', 'files').split(',')
    if c.has_option('case', 'observables'):
        value = c.get('case', 'observables')
        if value == '1' or value == 'true' or value == 'yes':
            config['caseObservables'] = True

    # Issue a warning of both tasks & template are defined!
    if len(config['caseTasks']) > 0 and config['caseTemplate'] != '':
        print('[WARNING] Both case template and tasks are defined. Template (%s) will be used.' % config['caseTemplate'])

    # New alert config
    config['alertTLP']          = c.get('alert', 'tlp')
    config['alertTags']         = c.get('alert', 'tags').split(',')
    if c.has_option('alert', 'keywords'):
        config['alertKeywords'] = c.get('alert', 'keywords')
    # Validate the keywords regex
    try:
        re.compile(config['alertKeywords'])
    except re.error:
        print('[ERROR] Regular expression "%s" is invalid.' % config['alertKeywords'])
        sys.exit(1)

    if args.verbose:
        print('[INFO] Processing %s@%s:%d/%s' % (config['imapUser'], config['imapHost'], config['imapPort'], config['imapFolder']))

    readMail(mailConnect())
    return

if __name__ == 'imap2thehive':
	main()
	sys.exit(0)
