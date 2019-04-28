from bs4 import BeautifulSoup
import re
import os

from elasticsearch import Elasticsearch
from sqlalchemy import create_engine, Column, Integer, String, Date, Text, Boolean, ForeignKey, Table, case
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

engine = create_engine('sqlite:///tours.db')
Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()

es = Elasticsearch('http://media-server:9200')


def add_to_index(index, model: Base):
    payload = {}
    for field in model.__searchable__:
        payload[field] = getattr(model, field)
    print("Indexing " + str(model.dgm_id))
    es.index(index=index, doc_type=index, id=model.id, body=payload)


def remove_from_index(index, model: Base):
    es.delete(index=index, doc_type=index, id=model.id)


def query_index(index, query):
    body = {'query': {'query_string': {'query': query}}, 'from': 0, 'size': 100}

    search = es.search(
        index=index,
        body=body)

    ids = [int(hit['_id']) for hit in search['hits']['hits']]
    return ids, search['hits']['total']


class Show(Base):
    __tablename__ = 'shows'
    __searchable__ = ['venue', 'location', 'date_friendly', 'description']
    # __analyzer__ = StemmingAnalyzer()

    id = Column(Integer, primary_key=True)
    venue = Column(String)
    location = Column(String)
    quality_rating = Column(Integer)
    date = Column(Date)
    date_friendly = Column(String)
    description = Column(Text)
    source = Column(String)
    cover = Column(String)
    dgm_id = Column(Integer)
    has_download = Column(Boolean)

    members: list = relationship('Member', back_populates='show')
    tracks: list = relationship('Track', back_populates='show')

    @classmethod
    def search(cls, expression,):
        ids, total = query_index('dgm_shows', expression)
        if total == 0:
            return session.query(Show).filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return session.query(Show).filter(cls.id.in_(ids)).order_by(
            case(when, value=cls.id)).all(), total


member_instrument = Table('member_instrument', Base.metadata,
                          Column('member_id', Integer, ForeignKey('members.id')),
                          Column('instrument_id', Integer, ForeignKey('instruments.id')))


class Member(Base):
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    show_id = Column(Integer, ForeignKey('shows.id'))

    show = relationship('Show', back_populates='members')
    instruments = relationship('Instrument', secondary=member_instrument, back_populates='members')


class Instrument(Base):
    __tablename__ = 'instruments'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

    members = relationship('Member', secondary=member_instrument, back_populates='instruments')


class Track(Base):
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True)
    pos = Column(Integer)
    name = Column(String)
    length = Column(Integer)
    show_id = Column(Integer, ForeignKey('shows.id'))

    show = relationship('Show', back_populates='tracks')


Base.metadata.create_all(engine)


def get_description(soup: BeautifulSoup):
    node = soup.find(id='description')
    if node:
        if not node.string:
            string = ''.join(filter(lambda x: x.string, node.contents)).strip()
            return string
        return node.string.strip()


def get_audio_source(soup: BeautifulSoup):
    node = soup.find(id='audio-source')
    if node and node.contents:
        return node.contents[1].strip()


def get_location(soup: BeautifulSoup):
    location_box = soup.find(class_='content-past')
    if not location_box:
        location_box = soup.find(class_='content col-xs-7 col-xs-7')

    venue = location_box.a.contents[1].string
    location = location_box.a.contents[3].string

    return venue, location


def get_cover(soup: BeautifulSoup):
    node = soup.find(class_='album-cover')
    if node:
        return node.img.get('src')


def get_track_length(string: str):
    if string == '--':
        return
    m, s = track_length.split(':')
    return int(m) * 60 + int(s)


def get_instrument(name: str):
    existing = session.query(Instrument).filter(Instrument.name == name).first()
    if existing:
        return existing
    return Instrument(name=name)


if __name__ == '__main__':
    for file in sorted(os.listdir('html'), key=lambda x: int(x.split('.')[0])):
        print(file)
        with open('html/' + file, 'r') as f:
            html = f.read()

        if '<h1>404 :(</h1>' in html:
            continue

        show = Show(dgm_id=int(file.split('.')[0]))

        soup = BeautifulSoup(html, 'html.parser')

        date_box = soup.find(class_='date-box')

        day = date_box.find(class_='part-left').string
        month = date_box.find(class_='part-right').contents[1].string
        year = date_box.find(class_='part-right').contents[3].string

        date_str = '%s %s %s' % (day, month, year)
        date = datetime.strptime(date_str, '%d %b %Y')

        show.date = date
        show.date_friendly = date_str

        venue, location = get_location(soup)

        show.venue = venue
        show.location = location

        quality_rating_img = 'https://www.dgmlive.com/img/assets/albums//audio-rating-white.png'
        rating = len(soup.find_all(src=quality_rating_img))

        show.quality_rating = rating if rating > 0 else None

        description = get_description(soup)

        show.description = description

        members_list = soup.find_all(href=re.compile('https://www.dgmlive.com/biographies/'))
        for member in list(set(members_list)):
            name = member.span.string.replace('-', '').strip()
            instruments = member.contents[1].split(', ')

            member_data = Member(name=name, show=show)

            for instrument in instruments:
                instrument_data = get_instrument(instrument)
                instrument_data.members.append(member_data)
                instrument_data.members = list(set(instrument_data.members))

                session.add(instrument_data)

            session.add(member_data)

        source = get_audio_source(soup)
        show.source = source

        track_list = soup.find_all(class_='album-content-line')

        for track in track_list:
            track_num = track.find(class_='track-number').string.strip()
            track_title = track.find(class_='track-title').contents[0].string.strip()
            track_length = track.find(class_='col-sm-2 hide-on-mobile').string.strip()

            length_int = get_track_length(track_length)

            track_data = Track(pos=track_num, name=track_title, length=length_int, show=show)
            session.add(track_data)

        cover = get_cover(soup)
        show.cover = cover

        download_image_url = 'https://www.dgmlive.com/img/assets/albums/download-black.png'
        download_button = soup.find_all(src=download_image_url)
        show.has_download = len(download_button) > 0

        session.add(show)

    session.commit()

    for show in session.query(Show).all():
        add_to_index('dgm_shows', show)
