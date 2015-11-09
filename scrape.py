#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import fnmatch
import shutil
import zipfile
import xml.dom.minidom
import sys, os, re, lxml.html, lxml.etree, urllib2
from xml.etree.ElementTree import Element, SubElement, tostring, parse, XML
from urlparse import urlparse
import unicodedata, string
from datetime import datetime
from subprocess import call, Popen, PIPE

from cStringIO import StringIO
# from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
# from pdfminer.converter import TextConverter
# from pdfminer.layout import LAParams
# from pdfminer.pdfpage import PDFPage


_persons = {}
_domain = 'actas.asambleadelosaraucanos.co'
_months = {
    'enero': '01',
    'febrero': '02',
    'marzo': '03',
    'abril': '04',
    'mayo': '05',
    'junio': '06',
    'julio': '07',
    'agosto': '08',
    'septiembre': '09',
    'octubre': '10',
    'noviembre': '11',
    'diciembre': '12',
}
_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')
_remove_paragraphs_re = [
    [r'\n', r'######'],
    [r'\f', r''],
    [r'“', '"'],
    [r'”', '"'],
    [r'\s*–\s*', '-'],
    [r'\s*-\s*', '-'],
    [r'\s*-\s*', '-'],
    [r'\s{2,}', ' '],
    [r'\n', ' '],
    [r'\s{2,}', ' '],
]
_speech_re = [
    # [r'(\d)\.\-', r'######\1.-'],
    # [r'(?<!Dr)(?<!DR)(?<!Dra)(?<!DRA)(?<!No)(?<!NO)(?<!Sr)(?<!SR)(?<!Sra)(?<!SRA)(?<! D)(?<! H)(?<! S)(?<!-H)\.\s', r'.######'],
    # [r'\s(?<!#)(?<!-)H\. S\.', r'.######H. S.'],
    # [r'La\s*Secretaria\s*(–|-|,)\s*Dra\.', 'Secretaria-Dra.'],
    # [r'######La\s*Secretaria\s*:', '######Secretaria:'],
    # [r'(El|La){0,1}\s*(Presidente|Presidenta)\s*(–|-|,)\s*H\.\s*S\.', 'Presidente-H. S.'],
    # [r'######(El|La){0,1}\s*(Presidente|Presidenta)\s*:', '######Presidente:'],
    # [r'\s*(?<!#)(Presidente|Presidenta|Secretaria)(:|-)', r'.######\1\2'],
    # [r'Presidente-([^:]*?),*\s(solicita|declara)', r'Presidente-\1: \2'],
    # [r'Secretaria-([^:]*?),*\s(realiza)', r'Secretaria-\1: \2'],
    # [r'\sH\.\sS\.([^#]*?):', r'.######H. S.\1:'],
    # [r'######((H\. S\.|Dra\.|Dr\.|Sr\.|Sra\.|Srta\.)[^#]*?):', r'######\1:'],
    # [r'EUGENIO PRIETO SOTO Presidente Vicepresidente JORGE ELI(E|É|)CER GUEVARA SANDRA OVALLE GARC(I|Í|)A Secretaria General', r''],
    # [r'EUGENIO PRIETO SOTO Presidente Vicepresidente JORGE ELI(E|É|)CER GUEVARA SANDRA OVALLE GARC(I|Í|)A', r''],
    # [r'EUGENIO PRIETO SOTO Presidente JORGE ELI(E|É|)CER GUEVARA Vicepresidente SANDRA OVALLE GARC(I|Í|)A Secretaria General', r''],
    # [r'EUGENIO PRIETO SOTO Presidente JORGE ELI(E|É|)CER GUEVARA Vicepresidente SANDRA OVALLE GARC(I|Í|)A', r''],
    # [r'EUGENIO PRIETO SOTO JORGE ELI(E|É|)CER GUEVARA Presidente Vicepresidente SANDRA OVALLE GARC(I|Í|)A Secretaria General', r''],
    # [r'EUGENIO PRIETO SOTO JORGE ELI(E|É|)CER GUEVARA Presidente Vicepresidente SANDRA OVALLE GARC(I|Í|)A', r''],
    # [r'EUGENIO PRIETO SOTO JORGE ELI(E|É|)CER GUEVARA SANDRA OVALLE', r''],
    # [r'EUGENIO PRIETO SOTO Presidente JORGE ELI(E|É|)CER GUEVARA Vicepresidente interesantes en representación de SANDRA OVALLE GARC(I|Í|)A', r''],
]
_cuestionario_re = [
    # r'^(.*)\ncuestionario\s*?(:|al|para|adjunto|\n|ADITIVO A LA PROPOSICIÓN|ANEXO A LA PROPOSICIÓN)(.*)$',
    # r'^(.*)siguiente\s*cuestionario\s*?(:|al|para|adjunto|\n|ADITIVO A LA PROPOSICIÓN|ANEXO A LA PROPOSICIÓN)(.*)$',
    # r'^(.*)ADICIÓNESE\s*A\s*LA\s*PROPOSICIÓN(.*)EL\s*CUESTIONARIO(.*)$',
    # r'^(.*)cuestionario(\s*)adjunto(.*)$'
    r'^(.*)preguntas(\s*)objeto(.*)$'
]
_questions_re = [
    [r'(?<!\.)(?<!\$)\s(\d{1,2})\.(?!\d)', r'. \1.'],
    [r'\.\s(\d{1,2})\.\-', r'. \1.'],
    [r'\.\s(\d{1,2})\.', r'.######\1.'],
    [r':\.######(\d)\.\s', r':######\1. '],
    [r'', r'Para el'],
    [r'(?<!\.)\sPara el', r'. Para el'],
    [r'\.\sPara el', r'.######Para el'],
]

_correct_speakers = [
    [r'\bel\s*uso\s*de\s*la\s*palabra\b', r'######'],
    [r'\buso\s*de\s*la\s*palabra\b', r'######'],
    [r'\btoma\s*la\s*palabra\b', r'######'],
    [r'\bpide\s*la\s*palabra\b', r'######'],
    [r'\bda\s*la\s*palabra\b', r'######'],
]

_extract_speakers = [
    r'Diputado(?!s)(\s*\S*\s*\S*)(?:[^.,]*?)######([^#]*)',
    r'######(?:\s*(?:al*|el*)\s*Diputado)(\s*\S*\s*\S*)([^#]*)',
]



WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PARA = WORD_NAMESPACE + 'p'
TEXT = WORD_NAMESPACE + 't'


class CustomHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        return urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_302


class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"


def find_files(path=None, pattern='*'):
    d = []
    for directory, subdirs, files in os.walk(os.path.normpath(path)):
        for filename in fnmatch.filter(files, pattern):
            if os.path.isfile(os.path.join(directory, filename)):
                if os.path.islink(os.path.join(directory, filename)):
                    d.append(os.path.join(get_path([directory]), filename))
                else:
                    d.append(get_path([directory, filename]))
    return d


def get_status_code(url):
    try:
        cookieprocessor = urllib2.HTTPCookieProcessor()
        opener = urllib2.build_opener(CustomHTTPRedirectHandler, cookieprocessor)
        urllib2.install_opener(opener)
        response = urllib2.urlopen(url)
        return response.getcode()
    except Exception:
        return 404


def execute_process(cmd):
    p = Popen(cmd.split(), stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()
    return output


def _slugify(value):
    if not isinstance(value, unicode):
        value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)


def _sanitize(value):
    return value.replace('(', '\(').replace(')', '\)').strip()


def is_valid_person(person):
#     for i in ['Dr.', 'Dra.', 'Sr.', 'Sra.', 'H. S.']:
#         if person.startswith(i):
#             return True
    # return False
    return True


def get_narratives(text):
    match = re.search(r'^(.*)ORDEN\s*DEL\s*D(Í|I)A(.*)$', text, flags=re.S)
    return (match.group(1), match.group(3))


def get_date_object(text):
    d = re.search(r'SESI.*N\s*(?:EXTRAORDINARIA|ORDINARIA)\s*DEL\s*(?:\S*)(?:\s*)(\S*)(\s*)([0-9]*)(\s*)de(\s*)(\S*)(\s*)de(\s*)([0-9]*)', text, flags=re.S|re.I)
    h = re.search(r'hora\s*inicio:\s*(\d*)\s*:\s*(\d*)\s*(AM|PM|A.M.|P.M.|Am.|Pm.)', text, flags=re.S|re.I)
    day = d.group(3)
    month = _months[d.group(6).lower()]
    year = d.group(9)
    hour = h.group(1)+':'+h.group(2)+h.group(3).replace('.', '').lower()
    if not day:
        day = '01'
    return datetime.strptime(day+'-'+month+'-'+year+' '+hour, '%d-%m-%Y %I:%M%p')


def get_acta_intro(text):
    m = re.search(r'ACTA(:?\s*)No\.(:?\s*)([0-9]*)(.*)', text, flags=re.S|re.I)
    return (m.group(3), m.group(4))


def get_questions_match(text):
    return re.search(_cuestionario_re[0], text, flags=re.S|re.I)
    # return (re.search(_cuestionario_re[0], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[1], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[2], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[3], text, flags=re.S|re.I))


def get_narrative_questions_speech(text):

    speech = re.findall(r'\d*(?:\.|\))\s*proposiciones\s*y\s*varios(.*)', text, flags=re.S|re.I)

    if not speech:
        speech = re.findall(r'(.*)\d*(?:\.|\))\s*aprobaci.*n\s*del\s*orden\s*del\s*d.*a(.*)', text, flags=re.S|re.I)

    if not speech:
        speech = ['']

    if isinstance(speech, list):
        speech = speech[0]

    if isinstance(speech, list):
        speech = speech[0]

    prenarrative = re.findall(r'(.*)\d*(?:\.|\))\s*proposiciones\s*y\s*varios', text, flags=re.S|re.I)

    if not prenarrative:
        prenarrative = re.findall(r'(.*)nota\s*secretarial:', text, flags=re.S|re.I)

    if isinstance(prenarrative, list):
        prenarrative = prenarrative[0]

    if isinstance(prenarrative, list):
        prenarrative = prenarrative[0]

    narrative = re.findall(r'\s*saludo\s*protocolario(.*)', prenarrative, flags=re.S|re.I)

    if not narrative:
        narrative = re.findall(r'\s*inicio\s*a\s*la\s*sesi.*n\s*(?:extraordinaria|ordinaria)(.*)', prenarrative, flags=re.S|re.I)

    if not narrative:
        narrative = re.findall(r'\s*saluda\s*a\s*todas\s*las\s*personas(.*)', prenarrative, flags=re.S|re.I)

    if not narrative:
        narrative = re.findall(r'(?:preside|abrir)\s*la\s*sesi.*n(.*)', prenarrative, flags=re.S|re.I)

    if isinstance(narrative, list):
        narrative = narrative[0]

    if isinstance(narrative, list):
        narrative = narrative[0]

    nota = re.findall(r'(.*)nota\s*secretarial:(.*)', speech, flags=re.S|re.I)
    if nota:
        speech = nota[0][0]
        nota = nota[0][1]
    else:
        nota = ''

    return (narrative, speech, nota)


def process_narratives(text):
    for r, f in _remove_paragraphs_re:
        text = re.sub(r, f, text)

    return text.strip()


def process_speech(text):
    speech = ''

    for r, f in _correct_speakers:
        text = re.sub(r, f, text)

    for i in _extract_speakers:
        for j in re.findall(i, text, flags=re.S|re.I):
            speaker = j[0]
            speaker_speech = j[1]
            for r, f in _remove_paragraphs_re:
                speaker_speech = re.sub(r, f, speaker_speech)
            speech = speech+speaker.strip().title()+': '+speaker_speech+'\n'

    return speech


def text_to_xml(fname):
    print 'Convirtiendo TXT a XML '+fname

    f = open(fname)
    fcontent = f.read()

    dateobject = get_date_object(fcontent)
    acta, intro = get_acta_intro(fcontent)
    narrative, speech, nota = get_narrative_questions_speech(intro)
    speech = process_speech(speech)

    flist = filter(None, speech.decode('utf-8').split('\n'))

    akoman = Element('akomaNtoso')
    debate = SubElement(akoman, 'debate')

    # META
    meta = SubElement(debate, 'meta')
    references = SubElement(meta, 'references')

    # PREFACE
    preface = SubElement(debate, 'preface')
    doctitle = SubElement(preface, 'docTitle')
    doctitle.text = unicode('Asamblea de Arauca'.decode('utf-8'))
    link = SubElement(preface, 'link', href='#')

    # DEBATE BODY
    debate_body = SubElement(debate, 'debateBody')
    debate_section_1 = SubElement(debate_body, 'debateSection')
    heading_1 = SubElement(debate_section_1, 'heading')
    heading_1.text = unicode(dateobject.strftime('%Y'))
    debate_section_2 = SubElement(debate_section_1, 'debateSection')
    heading_2 = SubElement(debate_section_2, 'heading')
    heading_2.text = unicode(_months.keys()[_months.values().index(dateobject.strftime('%m'))].title())
    debate_section_3 = SubElement(debate_section_2, 'debateSection')
    heading_3 = SubElement(debate_section_3, 'heading')
    heading_3.text = unicode('ACTA No. '+acta+' / '+dateobject.strftime('%d-%m-%Y'))

    na = SubElement(debate_section_3, 'speech', by='', startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
    sef = SubElement(na, 'from')
    sef.text = unicode('OTROS')
    sep = SubElement(na, 'p')
    sep.text = unicode(narrative.decode('utf-8').strip())

    _persons = {}
    for j in flist:
        se_person = j.split(':')[0]
        se_person_slug = _slugify(se_person)

        if se_person_slug and is_valid_person(se_person):
            _persons[se_person_slug] = {
                'href': '/ontology/person/'+_domain+'/'+se_person_slug,
                'id': se_person_slug,
                'showAs': se_person
            }

            se = SubElement(debate_section_3, 'speech', by='#'+se_person_slug,
                            startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
            sef = SubElement(se, 'from')
            sef.text = unicode(se_person.strip())
            sep = SubElement(se, 'p')

            for i, br in enumerate(j[len(se_person+':'):].split('######')):
                if i == 0:
                    sep.text = br.strip()
                else:
                    sebr = SubElement(sep, 'br')
                    sebr.tail = br.strip()

    for key, value in _persons.iteritems():
        se_person_tag = SubElement(references, 'TLCPerson', **value)

    na_1 = SubElement(debate_section_3, 'speech', by='', startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
    sef_1 = SubElement(na_1, 'from')
    sef_1.text = unicode('OTROS')
    sep_1 = SubElement(na_1, 'p')
    sep_1.text = unicode(nota.decode('utf-8').strip())

    xml_content = xml.dom.minidom.parseString(tostring(akoman))

    f = open('xml/'+os.path.splitext(os.path.basename(fname))[0]+'.xml', 'w')
    f.write(xml_content.toprettyxml().encode('utf-8'))
    f.close()


def get_selectors(html, selector):
    file = open(html)
    body = file.read()
    file.close()
    doc = lxml.html.document_fromstring(body)
    sessions = doc.cssselect(selector)
    return sessions


def is_valid_url(url):
    regex = re.compile(
        r'^(http|ftp|file|https):///?'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|[a-zA-Z0-9-]*|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    return regex.search(url)


def is_pdf_attachment(url):
    if is_valid_url(url):
        parse_object = urlparse(url)
        url_basename = os.path.basename(parse_object.path)
        url_ext = os.path.splitext(url_basename)[1]
        url_loc = parse_object.netloc

        if 'files' in url_loc and url_ext == '.pdf' and 'acta' in url_basename:
            return True
    return False


def download_file(url, dest):
    print 'Descargando '+url

    parse_object = urlparse(url)
    response = urllib2.urlopen(url)

    file = open(dest+'/'+os.path.basename(parse_object.path)+'.'+dest, 'w')
    file.write(response.read())
    file.close()


def download_pdf(url):
    print 'Descargando '+url

    parse_object = urlparse(url)
    response = urllib2.urlopen(url)

    file = open('pdf/'+os.path.basename(parse_object.path), 'w')
    file.write(response.read())
    file.close()


def pdf_to_text(fname):
    print 'Convirtiendo '+fname

    pagenums = set()

    output = StringIO()
    manager = PDFResourceManager()
    converter = TextConverter(manager, output, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, converter)

    infile = open(fname, 'rb')

    for page in PDFPage.get_pages(infile, pagenums):
        interpreter.process_page(page)

    infile.close()
    converter.close()
    text = output.getvalue()
    output.close

    file = open('text/'+os.path.splitext(os.path.basename(fname))[0]+'.txt', 'w')
    file.write(text)
    file.close()


def doc_to_text(path):
    print 'Convirtiendo DOC a TXT '+path
    call('catdoc '+path+' > text/'+os.path.splitext(os.path.basename(path))[0]+'.txt', shell=True)


def docx_to_text(path):
    print 'Convirtiendo DOCX a TXT '+path
    call('docx2txt '+path+' text/'+os.path.splitext(os.path.basename(path))[0]+'.txt', shell=True)


def get_path(path=[]):
    return os.path.normpath(os.path.realpath(
        os.path.abspath(os.path.join(*path))))


def guess_filetype(path):
    o = execute_process('file -bi '+path)
    return o.split(';')[0].split('/')[1]


def get_pagename(url, dest):
    u = urlparse(url)
    filename = _slugify(os.path.basename(os.path.splitext(u.path)[0])+u.query)
    extension = os.path.splitext(u.path)[1]
    return dest+'/'+filename+extension


def scrape():

    print 'Obteniendo páginas válidas ...'

    for infile in find_files('input', '*.doc*'):
        doc = get_pagename(infile, 'doc')
        shutil.copy(infile, doc)
        if guess_filetype(doc) == 'msword':
            doc_to_text(doc)
        elif guess_filetype(doc) == 'vnd.openxmlformats-officedocument.wordprocessingml.document':
            docx_to_text(doc)
            text_to_xml('text/'+os.path.splitext(os.path.basename(doc))[0]+'.txt')


if __name__ == "__main__":

    base_dir = '/home/notroot/sayit/sayit.mysociety.org'
    scrape()


    xmldir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'xml')

    for f in os.listdir(xmldir):
        if f.endswith('.xml'):
            xmlpath = os.path.join(xmldir, f)
            execute_process(base_dir+'/manage.py load_akomantoso --file='+xmlpath+' --instance='+_domain.split('.')[0]+' --commit --merge-existing')
