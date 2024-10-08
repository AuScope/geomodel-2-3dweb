#!/usr/bin/env python3

import os
import sys
import logging

"""
Uses 'sqlalchemy' library to create a simple 'sqlite' db to hold query results for models
"""
from sqlalchemy import create_engine
from sqlalchemy import Integer
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.schema import ForeignKey, MetaData, PrimaryKeyConstraint
from sqlalchemy.exc import DatabaseError

LOGGER = logging.getLogger(__name__)
# Add handler to logger
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(LOCAL_HANDLER)
LOGGER.setLevel(logging.INFO)  # logging.DEBUG


QUERY_DB_FILE = 'query_data.db'

# Declarative Base class
class Base(DeclarativeBase):
    pass

# pylint: disable=R0903
class Query(Base):
    ''' **Query table**

        Basic idea is to have a "query" table that points to the various parts of the model.
        A website query will provide the name of the model and a label from within the model.
        This can be used as an index to a row of the table.

        The "query" table points to the "info" tables. These point to information at various
        levels of the model: \
            segments, parts, model, and independent user notes.

        At the moment only a simple json string is stored in each of the "info" tables.
    '''
    __tablename__ = "query"

    model_name: Mapped[str]
    label: Mapped[str]

    segment_info_id = mapped_column(Integer, ForeignKey("segment_info.id"))
    part_info_id = mapped_column(Integer, ForeignKey("part_info.id"))
    model_info_id = mapped_column(Integer, ForeignKey("model_info.id"))
    user_info_id = mapped_column(Integer, ForeignKey("user_info.id"))

    segment_info = relationship("SegmentInfo", foreign_keys=[segment_info_id])
    part_info = relationship('PartInfo', foreign_keys=[part_info_id])
    model_info = relationship('ModelInfo', foreign_keys=[model_info_id])
    user_info = relationship('UserInfo', foreign_keys=[user_info_id])

    __table_args__ = (PrimaryKeyConstraint('model_name', 'label', name='_query_uc'),)


    def __repr__(self):
        result = "Query:" + \
                 "\n    model_name={0}".format(self.model_name) + \
                 "\n    label={0}".format(self.label) + \
                 "\n    segment_info={0}".format(self.segment_info) + \
                 "\n    part_info={0}".format(self.part_info) + \
                 "\n    model_info={0}".format(self.model_info) + \
                 "\n    user_info={0}".format(self.user_info)
        return result


class SegmentInfo(Base):
    ''' **Segment_Info table**

        Any information derived from a segment within a 3d model part,
        e.g. a single triangle on a fault surface made of lots of triangles
    '''
    __tablename__ = "segment_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    json: Mapped[str] = mapped_column(unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)



class PartInfo(Base):
    ''' **Part_Info table**

        Any information derived from a model part
        e.g. fault surface, borehole
    '''
    __tablename__ = "part_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    json: Mapped[str] = mapped_column(unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class ModelInfo(Base):
    ''' **Model_Info table**

        Any information that comes from the model as a whole,
        e.g. CRS of the model
    '''
    __tablename__ = "model_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    json: Mapped[str] = mapped_column(unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class UserInfo(Base):
    ''' **User_Info table**

        Any user notes that must be kept separate from the model data update process
        e.g. links to external databases
    '''
    __tablename__ = "user_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    json: Mapped[str] = mapped_column(unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class KeyValuePairs(Base):
    ''' **KeyValuePairs table**

        Stores key value pairs
    '''
    __tablename__ = "keyvaluepairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str]
    value: Mapped[str] = mapped_column(nullable=False)
    is_url: Mapped[bool]

#
class QueryDB():
    ''' A simple database class to manage the creation, writing and reading of the query database

    '''
    def __init__(self, overwrite=False, db_name='query_data.db'):
        LOGGER.debug(f"__init__ db {overwrite=} {db_name=}")
        self.error = ''
        try:
            db_name = 'sqlite:///' + db_name
            eng = create_engine(db_name, echo=False)
            if overwrite:
                Base.metadata.drop_all(bind=eng)
            Base.metadata.create_all(bind=eng)
            # 'scoped_session()' makes a thread-safe cache of session objects
            #  NOTE: Would like to eventually make scope_session() more global
            self.session_obj = scoped_session(sessionmaker(eng))
            self.ses = self.session_obj()
            self.metadata_obj = MetaData()
            self.metadata_obj.reflect(bind=eng)
        except DatabaseError as db_exc:
            self.error = str(db_exc)
            LOGGER.debug(f"Error creating db {db_exc}")

    def get_error(self):
        """
        :returns: the current error message
        """
        return self.error

    def add_segment(self, json_str):
        """
        Adds a segment object to database

        :param json_str: segment object as a JSON string
        :returns: a tuple (True, seginfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            seginfo_obj = None
            if 'segment_info' not in self.metadata_obj.tables.keys():
                seginfo_obj = SegmentInfo(json=json_str)
                self.ses.add(seginfo_obj)
                self.ses.commit()
                return True, seginfo_obj
            seginfo_obj = self.ses.scalars(select(SegmentInfo).filter_by(json=json_str).limit(1)).first()
            if seginfo_obj is None:
                seginfo_obj = SegmentInfo(json=json_str)
                self.ses.add(seginfo_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, seginfo_obj

    def add_part(self, json_str):
        """
        Adds a part object to database

        :param json_str: part object as a JSON string
        :returns: a tuple (True, partinfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            if 'part_info' not in self.metadata_obj.tables.keys():
                part_obj = PartInfo(json=json_str)
                self.ses.add(part_obj)
                self.ses.commit()
                return True, part_obj
            part_obj = self.ses.scalars(select(PartInfo).filter_by(json=json_str).limit(1)).first()
            if part_obj is None:
                part_obj = PartInfo(json=json_str)
                self.ses.add(part_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, part_obj

    def add_model(self, json_str):
        """
        Adds a model object to database

        :param json_str: model object as a JSON string
        :returns: a tuple (True, model_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            if 'model_info' not in self.metadata_obj.tables.keys():
                model_obj = ModelInfo(json=json_str)
                self.ses.add(model_obj)
                self.ses.commit()
                return True, model_obj
            model_obj = self.ses.scalars(select(ModelInfo).filter_by(json=json_str).limit(1)).first()
            if model_obj is None:
                model_obj = ModelInfo(json=json_str)
                self.ses.add(model_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, model_obj

    def add_user(self, json_str):
        """
        Adds a user info object to database

        :param json_str: user info object as a JSON string
        :returns: a tuple (True, userinfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            if 'user_info' not in self.metadata_obj.tables.keys():
                userinfo_obj = UserInfo(json=json_str)
                self.ses.add(userinfo_obj)
                self.ses.commit()
                return True, userinfo_obj
            userinfo_obj = self.ses.scalars(select(UserInfo).filter_by(json=json_str).limit(1)).first()
            if userinfo_obj is None:
                userinfo_obj = UserInfo(json=json_str)
                self.ses.add(userinfo_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, userinfo_obj

    def add_query(self, label, model_name, segment, part, model, user):
        """
        Adds a query object to database

        :param json_str: query object as a JSON string
        :returns: a tuple (True, query_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            query_obj = Query(label=label, model_name=model_name, segment_info=segment,
                              part_info=part, model_info=model, user_info=user)
            self.ses.merge(query_obj)
            self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, None

    def query(self, label, model_name):
        """
        Use this to query the database

        :param label: model part label
        :param model_name: name of model
        :returns: a tuple, format is (True, label str, model_name, seg_info_dict, part_info_dict, \
                      model_info_dict, user_info_dict) if successful \
                else (False, exception string)
        """
        try:
            result = self.ses.scalars(select(Query).filter_by(label=label) \
                                          .filter_by(model_name=model_name).limit(1)).first()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        if result is None:
            filter_str = label.rpartition('_')[0]
            try:
                result = self.ses.scalars(select(Query).filter_by(model_name=model_name) \
                                              .filter_by(label=filter_str).limit(1)).first()
            except DatabaseError as db_exc:
                return False, str(db_exc)
        if result is None:
            return True, (None, None, None, None, None, None)
        return True, (result.label, result.model_name, getattr(result.segment_info, 'json', None),
                      getattr(result.part_info, 'json', None),
                      getattr(result.model_info, 'json', None),
                      getattr(result.user_info, 'json', None))

    def __del__(self):
        try:
            if hasattr(self, 'session_obj'):
                self.session_obj.remove()
        except DatabaseError:
            pass



if __name__ == "__main__":
    print("Testing query db")
    # Basic unit testing
    QUERY_DB = QueryDB(overwrite=True, db_name=':memory:')
    MSG = QUERY_DB.get_error()
    if MSG != '':
        print(MSG)
    assert MSG == ''
    OK, S = QUERY_DB.add_segment('seg')
    assert OK
    assert S is not None
    OK, S2 = QUERY_DB.add_segment('seg')
    assert OK
    assert S2 is not None

    # Test for no duplicates
    assert QUERY_DB.ses.scalar(select(func.count(SegmentInfo.id))) == 1

    OK, S3 = QUERY_DB.add_segment('seg3')
    assert OK
    assert S3 is not None
    OK, P = QUERY_DB.add_part('part')
    assert OK
    assert P is not None
    OK, M = QUERY_DB.add_model('model')
    assert OK
    assert M is not None
    OK, U = QUERY_DB.add_user('user')
    assert OK
    assert U is not None
    OK, MSG = QUERY_DB.add_query('label', 'model_name', S, P, M, U)
    assert OK
    OK, MSG = QUERY_DB.add_query('label2', 'model_name2', S3, P, M, U)
    assert OK
    OK, MSG = QUERY_DB.add_query('label_3_i', 'model_name3', S3, P, None, None)
    assert OK

    # Have added three 'Query' objs? two 'Segment_Info' objs ? etc.
    assert QUERY_DB.ses.scalar(select(func.count(Query.model_name))) == 3
    assert QUERY_DB.ses.scalar(select(func.count(SegmentInfo.id))) == 2
    assert QUERY_DB.ses.scalar(select(func.count(PartInfo.id))) == 1
    assert QUERY_DB.ses.scalar(select(func.count(ModelInfo.id))) == 1
    assert QUERY_DB.ses.scalar(select(func.count(UserInfo.id))) == 1

    # Look for a 'Query' with all info tables
    OK, Q1 = QUERY_DB.query('label2', 'model_name2')
    assert(OK and Q1 is not None and Q1[0] == 'label2' and Q1[1] == 'model_name2' \
           and Q1[2] == 'seg3')

    # Look for 'Query' containing Nones
    OK, Q2 = QUERY_DB.query('label_3_i', 'model_name3')
    assert(OK and Q2[0] == 'label_3_i' and Q2[1] == 'model_name3' and Q2[5] is None)

    # Look for 'Query' with trailling number in label
    OK, Q2 = QUERY_DB.query('label_3_i_44', 'model_name3')
    assert(OK and Q2[0] == 'label_3_i' and Q2[1] == 'model_name3' and Q2[5] is None)

    # Non existing 'Query'
    assert QUERY_DB.query('label1_6', 'model_name5') == (True, (None, None, None, None, None, None))
    assert QUERY_DB.query('_label6', 'model_name5') == (True, (None, None, None, None, None, None))

    print("PASSED QUERY DB TESTS")
