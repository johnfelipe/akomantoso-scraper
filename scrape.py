#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import zipfile
import xml.dom.minidom
import sys, os, re, lxml.html, lxml.etree, urllib2
from xml.etree.ElementTree import Element, SubElement, tostring, parse, XML
from urlparse import urlparse
import unicodedata, string
from datetime import datetime
from subprocess import call, Popen, PIPE

from cStringIO import StringIO
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage


_persons = {}
_domain = 'senado.felipeurrego.com'
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
    # [r'\S*\s*\S*\s*\n\S*\s*\d*\s*/\d*\s*(-|–)*\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*\d*-\d*\s*\n\S*.*', r''],
    # [r'\S*\s*\d*\s*/\d*\s*(-|–)*\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*\d*-\d*\s*\n\S*.*', r''],
    # [r'\S*\s*\d*/\d*\s*(-|–)*\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*\d*-\d*\s*\n\S*.*', r''],
    # [r'\S*\s*\d*-\d*\s*/\s*\S*\s*\d*-\d*\s*\n\S*.*\n\S*.*', r''],
    # [r'\S*\s*\d*/\d*\s*–\s*\S*\s*\d*/\d*\s*–\s*.*\n\s*\S*\s*\S*\s*\d*-\d*', r''],
    # [r'\S*\s*\S*\s*\d*\s*/\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*/\d*-\d*\s*\n\S*.*', r''],
    # [r'\S*\s*\S*\s*\d*\s*/\d*\s*(-|–)*\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*/\S*\s*', r''],
    # [r'\S*\s*\d*\s*/\d*\s*(-|–)*\s*\S*\s*\d*/\d*\s*\n\S*\s*\S*\s*', r''],
    # [r'Para la [sS]esión del (\S*)(\s*)([0-9]*)(\s*)de(\s*)(\S*)(\s*)de(\s*)([0-9]*)(.*)', r''],
    # [r'Llamada a lista.', r''],
    # [r'\n\nPresidente\.', '\n\nPresidente:'],
    # [r'Presdiente', 'Presidente'],
    [r'Leído el orden del día señor Presidente\.', r''],
    [r'H\.R\. ', r'H. R. '],
    [r'H\.R ', r'H. R. '],
    [r'H\. R ', r'H. R. '],
    [r'INTERVENCIÓN\s*DEL\s*H\.\s*R\.\s*', r'H. R. '],
    [r'Intervención\s*del\s*H\.\s*R\.\s*', r'H. R. '],
    [r'Intervención\s*H\.\s*R\.\s*', r'H. R. '],
    # [r'Página\s*\d*', r''],
    # [r'\nI\s{0,1}\n', r''],
    # [r'\nII\s{0,1}\n', r''],
    # [r'\nIII\s{0,1}\n', r''],
    # [r'\nIV\s{0,1}\n', r''],
    # [r'\nV\s{0,1}\n', r''],
    # [r'\nVI\s{0,1}\n', r''],
    [r'\n\s{0,1}\d{1,2}\s{0,1}\n', r''],
    # [r'([\*]*)', ''],
    [r'^\.\s{0,1}\n', ''],
    [r'\f', r''],
    [r'“', '"'],
    [r'”', '"'],
    [r'\s*–\s*', '-'],
    [r'\s*-\s*', '-'],
    [r'\s*-\s*', '-'],
    [r'\s{2,}', ' '],
    [r'\n', ' '],
    [r'\s{2,}', ' '],
    # [r':\.', ':'],
    # [r'(?<!A LA )PROPOSICIÓN\s*No\.\s*(\d*)/(\d*)\s*', r'PROPOSICIÓN No. \1/\2. '],
    [r'Hace\s*(?:el)*uso\s*de\s*la\s*palabra\s*el\s*señor\s*([^:]*?),*\s*(H\. R\.)\s*([^:]*?):', r'\1-\2 \3:'],
    [r'Presidente-H\. R\.', r'H. R.'],
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
    for i in ['Dr.', 'Dra.', 'Sr.', 'Sra.', 'H. S.']:
        if person.startswith(i):
            return True
    return False


def get_narratives(text):
    match = re.search(r'^(.*)ORDEN\s*DEL\s*D(Í|I)A(.*)$', text, flags=re.S)
    return (match.group(1), match.group(3))


def get_date_object(text):
    m = (re.search(r'De la [sS]esión Ordinaria del (\S*)(\s*)([0-9]*)(\s*)de(\s*)(\S*)(\s*)de(\s*)([0-9]*)', text) or
         re.search(r'(\S*)(\s*)([0-9]{1,2})(\s*)de(\s*)(\S*)(\s*)de(\s*)([0-9]{4})', text))
    return datetime.strptime(m.group(3)+'-'+_months[m.group(6).lower()]+'-'+m.group(9), '%d-%m-%Y')


def get_acta_intro(text):
    m = re.search(r'ACTA No\. ([0-9]*)(.*)', text, flags=re.S|re.I)
    return (m.group(1), m.group(2))


def get_questions_match(text):
    return re.search(_cuestionario_re[0], text, flags=re.S|re.I)
    # return (re.search(_cuestionario_re[0], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[1], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[2], text, flags=re.S|re.I)
    #         or re.search(_cuestionario_re[3], text, flags=re.S|re.I))


def get_narrative_questions_speech(text):

    match = get_questions_match(text)

    if match:
        narrative = match.group(1)
        questions = match.group(3)

        while True:
            match = get_questions_match(narrative)

            if match:
                narrative = match.group(1)
                questions = match.group(3)+questions

            else:
                break

        match = re.search(r'^(.*)\nLo\s*que\s*propongan\s*los\s*Honorables\s*Representantes(?:\s*a\s*la\s*C(?:á|a)mara)*\.*(.*)$', questions, flags=re.S|re.I)
        questions = match.group(1)
        speech = match.group(2)

    else:
        match = re.search(r'^(.*)\nLo\s*que\s*propongan\s*los\s*Honorables\s*Representantes(?:\s*a\s*la\s*C(?:á|a)mara)*\.*(.*)$', text, flags=re.S|re.I)
        narrative = match.group(1)
        speech = match.group(2)
        questions = ''

    return (narrative, questions, speech)


def process_narratives(text):
    for r, f in _remove_paragraphs_re:
        text = re.sub(r, f, text)

    return text.strip()

def process_speech(text):
    for r, f in _remove_paragraphs_re+_speech_re:
        text = re.sub(r, f, text)

    # text = text.strip()
    # text = text.split('Presidente-')

    # for i, p in enumerate(text):
    #     if i != 0:
    #         presidente = text[i].split(':')[0]
    #         text[i] = re.sub('######Presidente:', '######'+presidente+':', text[i])

    # text = ''.join(text)
    # text = text.split('Secretaria-')

    # for i, s in enumerate(text):
    #     if i != 0:
    #         secretaria = text[i].split(':')[0]
    #         text[i] = re.sub('######Secretaria:', '######'+secretaria+':', text[i])

    # text = ''.join(text)

    # _persons_titles = []
    # for t, p in re.findall(r'######([^:#,]*?)-([^:#,]*?):', text):
    #     if (p == 'Madre Comunitaria' or
    #         p == 'Madre Comunitria' or
    #         p == 'Investigadora Instituto Latinoamericano de Servicios Legales Alternativos (ILSA)' or
    #         p == 'Miembro Junta Directiva de la Autoridad Nacional de Televisión (ANTV)' or
    #         p == 'Miembro Junta Directiva de la ANTV' or
    #         p == 'Miembro Junta Directiva ANTV'):
    #         _persons_titles.append([_sanitize(p), _sanitize(t)])
    #     elif (p == '(Cundinamarca)' or
    #         p == 'fondo del Gobierno Nacional Municipio de' or
    #         p == 'La cultura es prosperidad para todos." Ministra de Cultura' or
    #         p == 'Yo me quiero otra vez referir a la sentencia C' or
    #         p == 'Sigue allí la Malla Vial del Valle y sigue la vía Buga' or
    #         p == 'Otro de los corredores importantes es el corredor Bogotá'):
    #         pass
    #     else:
    #         _persons_titles.append([_sanitize(t), _sanitize(p)])

    # important = (re.findall(r'######((?:H\. S\.|Dra\.|Dr\.|Sr\.|Sra\.|Srta\.)[^:#,]*?),([^:#,]*?):', text) +
    #              re.findall(r'######((?:H\. S\.|Dra\.|Dr\.|Sr\.|Sra\.|Srta\.)[^:#,]*?)\s*\(([^:#,]*?)\):', text))

    # for t, p in important:
    #     _persons_titles.append([_sanitize(p), _sanitize(t)])

    # for t, p in _persons_titles:
    #     print t+'----'+p
    #     text = re.sub(t+'-'+p+':', p+':', text)
    #     text = re.sub(p+', '+t+':', p+':', text)
    #     text = re.sub(p+'[^:]', p+': ', text)
    #     text = re.sub(t+':', p+':', text)

    # text = re.sub(r'######((H\. S\.|Dra\.|Dr\.|Sr\.|Sra\.|Srta\.)[^#]*?):', r'\n\1:', text, flags=re.S)
    # return re.sub(r'\n(Sr|Sra)\.([^:]*?)(;|,)', r'\n\1:', text, flags=re.S)
    return text

def process_questions(text):
    for r, f in _remove_paragraphs_re+_questions_re:
        text = re.sub(r, f, text)

    text = text.strip()

    match = (re.search('(Presentada a consideración)(.*?\.)', text) or
             re.search('(Presentado por)(.*?\.)', text))

    speaker = ''

    if match:
        match = re.search(r'Honorable(s)*\s*Senador(es)*(.*?)(;|,|\.|\sy)', match.group(2))
        speaker = match.group(3).strip().title().split()

        if len(speaker) > 1:
            speaker = ' '.join(speaker)
        else:
            speaker = ''

    if not speaker:
        speaker = 'Eugenio Prieto Soto'

    text = re.sub(r'(.*)(Presentada a consideración|Presentado por).*', r'\1', text, flags=re.S)
    text = re.sub(r'\.######(\d{1,2})\.\s', r'.\n\1. ', text, flags=re.S)
    text = re.sub(r'######', r'\n', text, flags=re.S|re.M)
    return (text, 'H. S. '+speaker)


def text_to_xml(fname, url):
    print 'Convirtiendo TXT a XML '+fname

    f = open(fname)
    fcontent = f.read()

    dateobject = get_date_object(fcontent)
    acta, intro = get_acta_intro(fcontent)
    narrative, questions, speech = get_narrative_questions_speech(intro)
    q_narrative, s_narrative = get_narratives(narrative)

    speech = process_speech(speech)
    # questions, questioner = process_questions(questions)
    # q_narrative = process_narratives(q_narrative)
    # s_narrative = process_narratives(s_narrative)

    f = open('xml/'+os.path.splitext(os.path.basename(fname))[0]+'.txt', 'w')
    f.write(speech)
    f.close()

    # flist = filter(None, speech.decode('utf-8').split('\n'))
    # qlist = filter(None, questions.decode('utf-8').split('\n'))

    # akoman = Element('akomaNtoso')
    # debate = SubElement(akoman, 'debate')

    # # META
    # meta = SubElement(debate, 'meta')
    # references = SubElement(meta, 'references')

    # # PREFACE
    # preface = SubElement(debate, 'preface')
    # doctitle = SubElement(preface, 'docTitle')
    # doctitle.text = unicode('Comisión Sexta Senado'.decode('utf-8'))
    # link = SubElement(preface, 'link', href=url)

    # # DEBATE BODY
    # debate_body = SubElement(debate, 'debateBody')
    # debate_section_1 = SubElement(debate_body, 'debateSection')
    # heading_1 = SubElement(debate_section_1, 'heading')
    # heading_1.text = unicode(dateobject.strftime('%Y'))
    # debate_section_2 = SubElement(debate_section_1, 'debateSection')
    # heading_2 = SubElement(debate_section_2, 'heading')
    # heading_2.text = unicode(_months.keys()[_months.values().index(dateobject.strftime('%m'))].title())
    # debate_section_3 = SubElement(debate_section_2, 'debateSection')
    # heading_3 = SubElement(debate_section_3, 'heading')
    # heading_3.text = unicode('ACTA No. '+acta+' / '+dateobject.strftime('%d-%m-%Y'))

    # nq = SubElement(debate_section_3, 'speech', by='', startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
    # sef = SubElement(nq, 'from')
    # sef.text = unicode('OTROS')
    # sep = SubElement(nq, 'p')
    # sep.text = unicode(q_narrative.decode('utf-8').strip())

    # if qlist:
    #     qss = SubElement(debate_section_3, 'questions')
    #     qssh = SubElement(qss, 'heading')
    #     qssh.text = 'CUESTIONARIO'

    #     for q in qlist:
    #         if q and q != '.':
    #             if q[0].isdigit():
    #                 qs = SubElement(qss, 'question', by='#'+_slugify(questioner))
    #                 qs.text = unicode(q.strip())
    #             else:
    #                 qs = SubElement(qss, 'narrative')
    #                 qs.text = unicode(q.strip())

    # na = SubElement(debate_section_3, 'speech', by='', startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
    # sef = SubElement(na, 'from')
    # sef.text = unicode('OTROS')
    # sep = SubElement(na, 'p')
    # sep.text = unicode(s_narrative.decode('utf-8').strip())

    # # _persons = {}
    # for j in flist:
    #     se_person = j.split(':')[0]
    #     se_person_slug = _slugify(se_person)

    #     if se_person_slug and is_valid_person(se_person):
    #         _persons[se_person_slug] = {
    #             'href': '/ontology/person/'+_domain+'/'+se_person_slug,
    #             'id': se_person_slug,
    #             'showAs': se_person
    #         }

    #         se = SubElement(debate_section_3, 'speech', by='#'+se_person_slug,
    #                         startTime=unicode(dateobject.strftime('%Y-%m-%dT%H:%M:%S')))
    #         sef = SubElement(se, 'from')
    #         sef.text = unicode(se_person.strip())
    #         sep = SubElement(se, 'p')

    #         for i, br in enumerate(j[len(se_person+':'):].split('######')):
    #             if i == 0:
    #                 sep.text = br.strip()
    #             else:
    #                 sebr = SubElement(sep, 'br')
    #                 sebr.tail = br.strip()

    # for key, value in _persons.iteritems():
    #     se_person_tag = SubElement(references, 'TLCPerson', **value)

    # xml_content = xml.dom.minidom.parseString(tostring(akoman))

    # f = open('xml/'+os.path.splitext(os.path.basename(fname))[0]+'.xml', 'w')
    # f.write(xml_content.toprettyxml().encode('utf-8'))
    # f.close()


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
    call('catdoc '+path+' > text/'+os.path.splitext(os.path.basename(path))[0]+'.txt', shell=True)


def guess_filetype(path):
    o = execute_process('file -bi '+path)
    return o.split(';')[0].split('/')[1]


def scrape(url):

    pages = 1
    validpages = []

    print 'Obteniendo páginas válidas ...'

    validpages = ['http://www.camara.gov.co/portal2011/actas-comision-tercera']

    for page in validpages:

        page = page.strip('/')
        pagename = os.path.basename(page)
        download_file(page, 'html')

        for session in get_selectors('html/'+pagename+'.html', '.doclink')[:4]:

            link = 'http://www.camara.gov.co/'+session.cssselect('a')[0].get('href').strip('/')
            linkname = os.path.basename(link)
            download_file(link, 'doc')

            if guess_filetype('doc/'+linkname+'.doc') == 'pdf':
                pdf_to_text('doc/'+linkname+'.doc')
            elif guess_filetype('doc/'+linkname+'.doc') == 'msword':
                doc_to_text('doc/'+linkname+'.doc')

            # text_to_xml('text/'+linkname+'.txt', link)


if __name__ == "__main__":

    base_dir = '/home/notroot/sayit/sayit.mysociety.org'
    url = 'https://comision6senado.wordpress.com/category/actas/'
    scrape(url)

    # xmldir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'xml')

    # for f in os.listdir(xmldir):
    #     if f.endswith('.xml'):
    #         xmlpath = os.path.join(xmldir, f)
    #         execute_process(base_dir+'/manage.py load_akomantoso --file='+xmlpath+' --instance='+_domain.split('.')[0]+' --commit --merge-existing')
